"""
engines.py

Application composition root.

Creates and connects:

    Schwab client
    EventBus
    Runtime
    StateEngine
    SchwabStreamer
    CommandProcessor
    TradingApplication GUI

No business logic belongs here.
"""

from __future__ import annotations


from trading_app.auth import (
    get_easy_client,
)

from trading_app.bus import (
    EventBus,
)

from trading_app.schwab_streamer import (
    SchwabStreamer,
)

from trading_app.services.command_processor import (
    CommandProcessor,
)

from trading_app.engine.runtime import (
    Runtime,
)

from trading_app.engine.state_engine import (
    StateEngine,
)

from trading_app.gui.application import (
    TradingApplication,
)

from trading_app.config import AppConfig
from trading_app.trading_config import TradingConfig
from trading_app.services.order_factory import OrderFactory
from trading_app.services.trade_instruction_factory import (
    TradeInstructionFactory,
)
from trading_app.services.hotkeys import HotkeyManager

class Engine:
    """
    Main application controller.

    Owns application lifetime.
    """


    def __init__(self):

        #
        # -------------------------------------------------
        # Authenticated Schwab client
        # -------------------------------------------------
        #

        self.config = AppConfig.load()

        self.trading_cfg = TradingConfig.load(self.config.get_trading_config_path())

        self.client = get_easy_client(
            str(self.config.keepass_config))

        #
        # -------------------------------------------------
        # Event infrastructure
        # -------------------------------------------------
        #

        self.bus = EventBus()



        #
        # -------------------------------------------------
        # Backend services
        # -------------------------------------------------
        #

        self.state_engine = StateEngine(
            self.bus
        )


        self.streamer = SchwabStreamer(
            self.client,
            self.bus,
            state_engine=self.state_engine,
        )


        self.command_processor = (
            CommandProcessor(
                client=self.client,
                bus=self.bus,
                state_engine=self.state_engine,
                is_simulation_enabled=lambda: self.runtime.simulation_mode,
                account_provider=self._get_selected_account_hash,
            )
        )

        self.trade_instruction_factory = (
            TradeInstructionFactory(
                config=self.trading_cfg,
            )
        )


        
        #
        # OrderFactory is a service that builds OrderRequest objects from GUI input.
        #

        self.order_factory = OrderFactory()


        #
        # -------------------------------------------------
        # Runtime coordinator
        # -------------------------------------------------
        #

        self.runtime = Runtime(
            bus=self.bus,
            streamer=self.streamer,
            command_processor=self.command_processor,
            state_engine=self.state_engine,
            order_factory=self.order_factory,
        )

        self.hotkey_manager = HotkeyManager(
            trading_config=self.trading_cfg,
            runtime=self.runtime,
            trade_instruction_factory=self.trade_instruction_factory,
        )

        #
        # -------------------------------------------------
        # GUI
        # -------------------------------------------------
        #

        self.gui = TradingApplication(

            trading_config= self.trading_cfg,

            trade_instruction_factory= self.trade_instruction_factory,

            hotkey_manager= self.hotkey_manager,

            get_quote=self.state_engine.get_quote,

            on_order= self.runtime.submit_order,

            on_instruction_submit= self.runtime.submit_instruction,

            on_connect= self.start_backend,

            on_disconnect= self.stop_backend,

            on_add_symbol= self.runtime.add_symbol,

            on_remove_symbol= self.runtime.remove_symbol,

            resolve_instruction= self.runtime.resolve_instruction_quantity,

            on_refresh_positions= self.runtime.refresh_positions,

            on_account_changed= self.runtime.set_selected_account,

            on_ensure_symbol= self.runtime.ensure_symbol,

            on_flatten_position= self.runtime.flatten_position,

            on_simulation_changed= self.runtime.on_simulation_changed,

            on_get_quote= self.state_engine.get_quote,
        )

        self.runtime.attach_gui(self.gui)

        
        #
        # Runtime receives final order factory
        #

        self.runtime.order_factory = (
            self.order_factory
        )

    def _get_selected_account_hash(self):
        """
        Return the currently selected Schwab account.
        """

        if self.runtime is None:
            return None

        return self.runtime.selected_account_hash
        
    # =====================================================
    # Lifecycle
    # =====================================================

    def run(self):

        self.gui.run()



    def start_backend(self):
        print("ENGINE: starting backend")
        self.runtime.start()
        self.gui.attach_hotkey_manager(self.hotkey_manager)

    def stop_backend(self):

        self.runtime.stop()



    def shutdown(self):

        self.runtime.stop()

        self.gui.shutdown()
