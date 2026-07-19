"""
engine/runtime.py

Runtime coordinator.

Responsibilities:

    - Own asyncio event loop thread
    - Start backend async services
    - Consume EventBus events
    - Bridge async world -> Tk world
    - Submit GUI commands into EventBus

Does NOT:

    - Own trading logic
    - Own broker API logic
    - Own GUI widgets
"""

from __future__ import annotations

import asyncio
import threading
import queue
import math
from dataclasses import replace
from typing import Optional


from trading_app.bus import (
    CommandEvent,
    CommandType,
    SystemEvent,
)
from trading_app.models.trade_instruction import TradeInstruction
from trading_app.models.order import OrderRequest, OrderType, Side, TimeInForce
from trading_app.trading_config import QuantityType

class Runtime:
    """
    Async runtime coordinator.

    One instance owned by Engine.
    """

    def __init__(
        self,
        *,
        bus,
        streamer,
        command_processor,
        state_engine,
        order_factory=None,
        trade_instruction_factory=None,
    ):

        self.bus = bus

        self.streamer = streamer

        self.command_processor = (
            command_processor
        )

        self.state_engine = (
            state_engine
        )

        self.order_factory = order_factory
        self.trade_instruction_factory = trade_instruction_factory

        #
        # Assigned after construction
        #

        self.gui = None


        #
        # Async runtime state
        #

        self.loop = None

        self.thread = None

        self.running = False


        #
        # Async -> GUI bridge
        #

        self.gui_queue = queue.Queue(maxsize=5000)

        self.accounts = []
        self.selected_account_hash = None


    # ==========================================================
    # GUI Attachment
    # ==========================================================

    def attach_gui(
        self,
        gui,
    ):

        self.gui = gui

    def add_symbol(self, symbol: str) -> bool:
        """Queue a new market-data subscription requested by the Tk GUI."""

        symbol = symbol.strip().upper()

        if (
            not symbol
            or symbol == "-"
            or not self.running
            or self.loop is None
            or self.streamer.has_symbol(symbol)
        ):
            return False

        asyncio.run_coroutine_threadsafe(
            self.streamer.add_symbol(symbol),
            self.loop,
        )
        return True

    def remove_symbol(self, symbol: str) -> bool:
        """Queue removal of a GUI symbol from the market-data watchlist."""

        symbol = symbol.strip().upper()

        if (
            not symbol
            or not self.running
            or self.loop is None
            or not self.streamer.has_symbol(symbol)
        ):
            return False

        asyncio.run_coroutine_threadsafe(
            self.streamer.remove_symbol(symbol),
            self.loop,
        )
        return True

    def flatten_position(self, symbol: str, ) -> bool:

        if not self.running:
            return False

        if self.loop is None:
            return False

        symbol = symbol.strip().upper()

        if not symbol:
            return False
        
        request = OrderRequest(
                    symbol=symbol,
                    account_hash=self.selected_account_hash,
                    quantity=self.state_engine.get_position(symbol,self.selected_account_hash),
                    side=Side.SELL,
                    order_type=OrderType.MARKET,
                    tif=TimeInForce.DAY,
        )

        event = CommandEvent(command=CommandType.FLATTEN, payload=request)

        asyncio.run_coroutine_threadsafe(
            self.bus.publish_command(event),
            self.loop,
        )

        return True

    def refresh_positions(self) -> bool:
        """Request a low-frequency Schwab position refresh."""

        if not self.running or self.loop is None:
            return False

        asyncio.run_coroutine_threadsafe(
            self.streamer.refresh_positions(),
            self.loop,
        )
        return True

    def old_set_selected_account(
        self,
        account_hash: str | None,
    ) -> bool:
        """
        Update the currently selected account and refresh the
        quote table positions for that account.
        """

        self.selected_account_hash = account_hash

        if (
            account_hash is None
            or self.gui is None
        ):
            return False

        quantities = (
            self.state_engine.get_account_position_quantities(
                account_hash
            )
        )

        self.gui.quote_table.set_positions(
            quantities
        )

        return True

    def set_selected_account(self, account_hash):

        if (
            account_hash is None
            or self.gui is None
            or account_hash == self.selected_account_hash
        ):
            return

        self.selected_account_hash = account_hash

        self.gui.quote_table.set_positions(
            self.state_engine.get_account_position_quantities(
                account_hash
             )
         )

    # ==========================================================
    # Startup
    # ==========================================================

    def start(self):
        print("RUNTIME: START")
        if self.running:

            return


        self.running = True

        print("RUNTIME: thread starting")
        self.thread = threading.Thread(
            target=self._async_thread,
            daemon=True,
        )

        self.thread.start()

        #
        # Begin Tk polling
        #

        self._poll_gui_queue()



    def _async_thread(self):

        asyncio.run(
            self._async_main()
        )



    async def _async_main(self):

        self.loop = (
            asyncio.get_running_loop()
        )


        #
        # Start async services
        #

        tasks = [

            asyncio.create_task(
                self.streamer.run()
            ),

            asyncio.create_task(
                self.command_processor.run()
            ),

            asyncio.create_task(
                self.state_engine.run()
            ),

            asyncio.create_task(
                self.market_listener()
            ),

            asyncio.create_task(
                self.system_listener()
            ),
        ]

        print("RUNTIME: async services starting")
        try:
        
            await asyncio.gather(
                *tasks
            )


        except asyncio.CancelledError:

            pass

    def ensure_symbol(self, symbol:str) -> bool:
        """
        Ensure a position symbol exists in the GUI watchlist.

        If the symbol is not already subscribed, queue a market-data
        subscription. The GUI row is created immediately so the
        position is visible before the first quote arrives.

        Returns
        -------
        bool
            True if a new row was added.
        """
        symbol = symbol.strip().upper()

        if not symbol:
            return False
        #
        # Already displayed?
        #
        if self.gui.quote_table.find_symbol(symbol):
            return

        #
        # Start market-data subscription if needed.
        #
        if (
            self.running
            and self.loop is not None
            and not self.streamer.has_symbol(symbol)
        ):
            asyncio.run_coroutine_threadsafe(
                self.streamer.add_symbol(symbol),
                self.loop,
            )

        #
        # Create placeholder row immediately.
        #
        self.gui.quote_table.add_symbol(symbol)

        return True

    # ==========================================================
    # EventBus Consumers
    # ==========================================================

    def submit_instruction(
        self,
        instruction,
    ):
        """
        Convert a TradeInstruction into an
        OrderRequest and submit it.
        """

        if self.order_factory is None:

            raise RuntimeError(
                "OrderFactory not attached."
            )


        request = self.order_factory.create(
            self.resolve_instruction_quantity(instruction)
        )


        return self.submit_order(
            request
        )

    def resolve_instruction_quantity(self, instruction):
        """Convert a percentage sell instruction into a fixed share quantity.

        Positions remain broker-authoritative: the StateEngine receives their
        updates from Schwab account activity after executions, rather than
        changing the cached quantity when an order is merely accepted.
        """

        if instruction.quantity_type is not QuantityType.PERCENT:
            return instruction

        if instruction.side is not Side.SELL:
            raise ValueError("Percentage quantity is supported only for SELL orders.")

        percentage = instruction.quantity_value
        if not 0 < percentage <= 100:
            raise ValueError("Percentage sell quantity must be between 1 and 100.")

        account_hash = (
            instruction.account_hash
            or self.selected_account_hash
        )

        position = self.state_engine.get_position(
            instruction.symbol,
            account_hash
        )

        available_quantity = int(
            getattr(position, "quantity", 0)
        )

        if available_quantity <= 0:
            account_text = (
                instruction.account
                or account_hash
                or "selected account"
            )

            raise ValueError(
                f"No long position available for "
                f"{instruction.symbol.upper()} "
                f"in {account_text}."
            )

        quantity = math.floor(available_quantity * percentage / 100)
        if quantity <= 0:
            raise ValueError(
                "Percentage sell quantity rounds down to zero shares."
            )

        return replace(
            instruction,
            quantity_type=QuantityType.FIXED,
            quantity_value=quantity,
        )

    # Kept as an internal alias for callers that used the original helper.
    def _resolve_instruction_quantity(self, instruction):
        return self.resolve_instruction_quantity(instruction)

    async def market_listener(
        self,
    ):

        async for event in (
            self.bus.subscribe_market()
        ):

            if not self.running:

                break


            try:

                self.gui_queue.put_nowait(event)

            except queue.Full:

                #
                # Drop stale GUI updates.
                # Latest market data is more
                # valuable than old ticks.
                #

                pass


    async def system_listener(self):

        async for event in self.bus.subscribe_system():

            try:
                self.gui_queue.put_nowait(event)

            except queue.Full:
                print(
                    "GUI queue full, dropping system event:",
                    event.name,
                )


    # ==========================================================
    # Async -> Tk bridge
    # ==========================================================

    def _poll_gui_queue(self,):

        if not self.gui:

            return


        while True:

            try:

                event = (self.gui_queue.get_nowait())

                self._handle_gui_event(event)


            except queue.Empty:

                break



        if self.running:

            self.gui.root.after(50, self._poll_gui_queue,)


    def _handle_gui_event(self, event):

        """
        Translate backend events
        into GUI updates.
        """

        #
        # Quote updates
        #
        print("_handle_gui_event:", type(event), event)
        if isinstance(event, SystemEvent):
            if event.name == "ACCOUNTS_LOADED":

                self.accounts = list(event.payload or [])

                self.gui.set_accounts(
                    self.accounts
                )

                if self.accounts:

                    #
                    # Default to the first account shown in
                    # the GUI and immediately display only
                    # that account's positions.
                    #
                    self.set_selected_account(
                        self.accounts[0].account_hash
                    )

                return
            elif event.name == "PRICE_UPDATED":
                payload = event.payload
                self.gui.update_quote(
                    payload["symbol"],
                    payload,
                )
                return
            elif event.name == "POSITIONS_UPDATED":

                payload = event.payload or {}

                account_hash = payload.get("account_hash")
                quantities = payload.get("quantities", {})

                #
                # Ignore updates for accounts that are not currently selected.
                #
                if (
                    self.selected_account_hash is not None
                    and account_hash != self.selected_account_hash
                ):
                    return

                self.gui.update_positions(quantities)
                return
            elif event.name == "ORDER_ACCEPTED":
                self.refresh_positions()
                return
            elif event.name == "CONNECTED":
                self.gui.set_connection_status(
                    "Connected"
                )
                return
            elif event.name == "DISCONNECTED":
                self.gui.set_connection_status(
                    "Disconnected"
                )
                return
            elif event.name == "STREAM_ERROR":
                self.gui.set_connection_status(
                    "Stream Error"
                )
                return


        #
        # Future dataclass payloads
        #

        payload = getattr(event, "payload", None)

        if (
            payload is not None
            and hasattr(payload, "symbol")
            and hasattr(payload, "bid")
            and hasattr(payload, "ask")
            and hasattr(payload, "last")
        ):

            self.gui.update_quote(
                payload.symbol,
                payload,
            )
        return

    def submit_template(
        self,
        template_name: str,
    ):

        if self.order_factory is None:

            raise RuntimeError(
                "OrderFactory not attached."
            )

        request = self.order_factory.build(
            template_name
        )

        self.submit_order(request)


    def submit_order(
    self,
    request,
) -> bool:
        """
        Submit an OrderRequest into the backend.

        This is the single entry point used by every
        frontend component, including:

            • OrderPanel
            • Hotkeys
            • Automation
            • Future strategy engines

        Parameters
        ----------
        request
            Fully-populated OrderRequest.

        Returns
        -------
        bool
            True if the request was accepted for
            asynchronous processing.
        """

        if not self.running:
            return False

        if self.loop is None:
            return False

        event = CommandEvent(
            command=request.command_side,
            payload=request,
        )

        asyncio.run_coroutine_threadsafe(
            self.bus.publish_command(event),
            self.loop,
        )

        return True



    # ==========================================================
    # Shutdown
    # ==========================================================

    def stop(
        self,
    ):

        if not self.running:

            return


        self.running = False


        #
        # Stop async services
        #

        if self.loop:

            asyncio.run_coroutine_threadsafe(
                self._shutdown_async(),
                self.loop,
            )



    async def _shutdown_async(
        self,
    ):

        #
        # Service shutdown hooks
        #

        if hasattr(
            self.streamer,
            "stop",
        ):

            self.streamer.stop()


        if hasattr(
            self.command_processor,
            "stop",
        ):

            self.command_processor.stop()


        if hasattr(
            self.state_engine,
            "stop",
        ):

            self.state_engine.stop()
