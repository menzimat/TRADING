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
    SystemEvent,
)
from trading_app.models.order import Side
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

        position = self.state_engine.get_position(instruction.symbol)
        available_quantity = int(getattr(position, "quantity", 0))
        if available_quantity <= 0:
            raise ValueError(
                f"No long position available for {instruction.symbol.upper()}"
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
                if self.accounts:
                    self.selected_account_hash = self.accounts[0].account_hash
                self.gui.set_accounts(self.accounts)
                return
            elif event.name == "PRICE_UPDATED":
                payload = event.payload
                self.gui.update_quote(
                    payload["symbol"],
                    payload,
                )
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

    def old_submit_template(
        self,
        template_name: str,
        symbol: str | None = None,
    ) -> bool:
        """
        Submit an order using a named trading template.

        This method is intended for hotkeys and future automation.
        It delegates construction of the OrderRequest to the
        OrderFactory.

        Parameters
        ----------
        template_name
            Name of the template in trading.yaml.

        symbol
            Optional symbol override.  If omitted, the currently
            selected GUI symbol is used.

        Returns
        -------
        bool
            True if the order was accepted for asynchronous
            processing.
        """

        if not self.running:
            return False

        #
        # Determine the active symbol.
        #
        if symbol is None:

            #
            # TODO:
            # Replace with the application's authoritative
            # source for the currently selected symbol.
            #
            symbol = self.gui.get_selected_symbol()

        #
        # Obtain the latest QuoteState.
        #
        quote = self.state_engine.get_quote(symbol)

        if quote is None:

            print(f"No QuoteState available for {symbol}")

            return False

        #
        # Build an OrderRequest from the template.
        #
        from trading_app.services.order_factory import OrderFactory

        request = OrderFactory.build_from_template(
            trading_config=self.gui.trading_config,
            template_name=template_name,
            symbol=symbol,
            quote=quote,
        )

        if request is None:

            return False

        #
        # Submit through the normal command path.
        #
        return self.submit_order(request)

    # ==========================================================
    # GUI -> Async command path
    # ==========================================================

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
