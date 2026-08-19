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
import logging

from trading_app.bus import (
    CommandEvent,
    CommandType,
    SystemEvent,
)

from trading_app.models.order import Side
from trading_app.trading_config import QuantityType
from trading_app.scanner.scanner_engine import ScannerEngine

logger = logging.getLogger(__name__)


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
        account_list=None,
        trading_config=None,
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

        self.scanner_state = self.state_engine.scanner_state

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
        self.streamer_task = None

        self.hotkeys_enabled = False

        self.simulation_mode = True

        #
        # Async -> GUI bridge
        #

        self.gui_queue = queue.Queue(maxsize=5000)

        self.trading_config = trading_config

        #self.account_list is a dictionary of the account numbers loaded from the
        #secure database. { "brokerage_account": "12345678", "hsa_account": "87654321" }
        #The DEFAULT account to use will be determines based on which account name is
        #listed in the trading.yaml file default account entry: brokerage_account or hsa_account.

        self.account_list = account_list
        self.accounts = []
        self.selected_account_hash = None

        self.scanner_engine = ScannerEngine( self.bus, self.scanner_state,)

    def set_simulation_mode(self, enabled):
        self.simulation_mode = enabled

    @property
    def live_trading(self):

        return not self.simulation_mode
    
    def on_simulation_changed(self, enabled ):
        logger.debug(f"RUNTIME on_simulation_changed: {enabled}")
        self.set_simulation_mode(enabled)

        

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
        request = self.order_factory.create_flatten_request(
            account=self.selected_account_hash,
            symbol=symbol,
            position=self.state_engine.get_position(symbol,self.selected_account_hash),
        )

        event = CommandEvent(command=CommandType.FLATTEN, payload=request)

        asyncio.run_coroutine_threadsafe(
            self.bus.publish_command(event),
            self.loop,
        )

        return True

    def refresh_positions(self) -> bool:
        """Request a low-frequency Schwab position refresh."""

        if (
            not self.running
            or self.loop is None
            or not getattr(self.streamer, "_connected", False)
        ):
            return False

        asyncio.run_coroutine_threadsafe(
            self.streamer.refresh_positions(),
            self.loop,
        )
        return True

    def reload_symbol_files(self) -> bool:
        """Reload ticker files and replace the displayed/subscribed symbols."""

        if (
            not self.running
            or self.loop is None
            or not getattr(self.streamer, "_connected", False)
        ):
            return False

        future = asyncio.run_coroutine_threadsafe(
            self._reload_symbol_files_from_broker(),
            self.loop,
        )

        def apply_symbols(completed):
            try:
                symbols, positions = completed.result()
            except Exception:
                logger.exception("Unable to reload ticker files")
                return

            try:
                self.gui_queue.put_nowait(
                    SystemEvent(
                        name="SYMBOLS_RELOADED",
                        payload={
                            "symbols": symbols,
                            "positions": positions,
                        },
                    )
                )
            except queue.Full:
                logger.warning("GUI queue full; symbol reload display was skipped")

        future.add_done_callback(apply_symbols)
        return True

    async def _reload_symbol_files_from_broker(self):
        """Query Schwab positions before replacing quote subscriptions."""

        snapshots = await self.streamer.refresh_positions(
            self.selected_account_hash
        )
        if self.selected_account_hash in snapshots:
            positions = {
                position["symbol"]: position["quantity"]
                for position in snapshots[self.selected_account_hash]
            }
        else:
            # A failed broker query must not erase the still-useful cached
            # position display; a later reload/account event can retry it.
            positions = self.state_engine.get_account_position_quantities(
                self.selected_account_hash
            )
        symbols = await self.streamer.reload_symbol_files(positions)
        return symbols, positions

    def set_default_account(self, accounts, acct_list, cfg):
        if cfg.defaults.account in acct_list:
            for acct in accounts:
                if acct.account_number == acct_list[cfg.defaults.account]:
                    logger.debug(f"Setting Default Account to: %s : %s", cfg.defaults.account, acct_list[cfg.defaults.account])
                    self.set_selected_account(acct.account_hash)
                    self.gui.set_accounts(self.accounts, acct.account_number)
                    break

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
        logger.debug("RUNTIME: START")
        if self.running:

            return


        self.running = True

        logger.debug("RUNTIME: thread starting")
        self.thread = threading.Thread(
            target=self._async_thread,
            daemon=True,
        )

        self.thread.start()
        self.hotkeys_enabled = True
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

        self.streamer_task = asyncio.create_task(self.streamer.run())
        tasks = [

            self.streamer_task,

            asyncio.create_task(
                self.command_processor.run()
            ),

            asyncio.create_task(
                self.state_engine.run()
            ),

            asyncio.create_task(
                self.scanner_engine.run()
            ),
            
            asyncio.create_task(
                self.market_listener()
            ),

            asyncio.create_task(
                self.system_listener()
            ),


        ]

        logger.debug("RUNTIME: async services starting")
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

        logger.debug("system_listener started")
        async for event in self.bus.subscribe_system():
    
            try:
                logger.debug(
                    "system_listener received %s",
                    event.name,
                )
                self.gui_queue.put_nowait(event)

            except queue.Full:
                logger.debug("GUI queue full, dropping system event: %s", event.name, )


    # ==========================================================
    # Async -> Tk bridge
    # ==========================================================

    def _poll_gui_queue(self,):

        if not self.gui:
            return

        logger.debug(
            "GUI queue size = %d",
            self.gui_queue.qsize(),
        )

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
        logger.debug("_handle_gui_event: %s : %s", type(event), event)
        if isinstance(event, SystemEvent):
            if event.name == "ACCOUNTS_LOADED":
                self.accounts = list(event.payload or [])
            
                if self.accounts:
                    if self.account_list and self.trading_config:
                        #Default to the configured defaults account from the trading.yaml
                        self.set_default_account(self.accounts, self.account_list, self.trading_config)
                    else:
                        #
                        # Default to the first account shown in
                        # the GUI and immediately display only
                        # that account's positions.
                        #
                        self.set_selected_account(self.accounts[0].account_hash)
                        self.gui.set_accounts(self.accounts, self.accounts[0].account_number)

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
            elif event.name == "SCANNER_UPDATED":
                logger.debug(
                    "Runtime received scanner update: %d symbols",
                    len(event.payload),
                )
                self.gui.update_scanner(event.payload )
            elif event.name == "SYMBOLS_RELOADED":
                payload = event.payload or {}
                self.gui.replace_symbols(
                    payload.get("symbols", []),
                    payload.get("positions", {}),
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

    def cancel_all_orders(self) -> bool:

        if not self.running or self.loop is None:
            return False

        event = CommandEvent(
            command=CommandType.CANCEL_ALL,
            payload={
                "account_hash": self.selected_account_hash,
            },
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

    def disconnect(self):
        """Disconnect only the Schwab stream, leaving the runtime restartable."""

        if not self.running or self.loop is None:
            return

        asyncio.run_coroutine_threadsafe(
            self._disconnect_streamer(),
            self.loop,
        )

    async def _disconnect_streamer(self):
        self.streamer.stop()
        await self.streamer.disconnect()

        if self.streamer_task and not self.streamer_task.done():
            await self.streamer_task

    def connect(self):
        """Start a new Schwab stream after a menu disconnect."""

        if not self.running:
            self.start()
            return

        if self.loop is not None:
            asyncio.run_coroutine_threadsafe(
                self._connect_streamer(),
                self.loop,
            )

    async def _connect_streamer(self):
        if self.streamer_task and not self.streamer_task.done():
            return

        self.streamer_task = asyncio.create_task(self.streamer.run())



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

        if hasattr(self.streamer, "disconnect"):
            await self.streamer.disconnect()


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

        if hasattr(self.scanner_engine, "stop"):
            self.scanner_engine.stop()
