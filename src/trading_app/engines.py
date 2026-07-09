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
        )


        self.command_processor = (
            CommandProcessor(
                client=self.client,
                bus=self.bus,
                state_engine=self.state_engine,
            )
        )


        #
        # -------------------------------------------------
        # Runtime coordinator
        # -------------------------------------------------
        #

        self.runtime = Runtime(
            bus=self.bus,
            streamer=self.streamer,
            command_processor=
                self.command_processor,
            state_engine=
                self.state_engine,
        )


        #
        # -------------------------------------------------
        # GUI
        # -------------------------------------------------
        #

        self.gui = TradingApplication(
            on_order=
                self.runtime.submit_order,

            on_connect=
                self.start_backend,

            on_disconnect=
                self.stop_backend,
        )


        self.runtime.attach_gui(
            self.gui
        )



    # =====================================================
    # Lifecycle
    # =====================================================

    def run(self):

        self.gui.run()



    def start_backend(self):
        print("ENGINE: starting backend")
        self.runtime.start()

    def stop_backend(self):

        self.runtime.stop()



    def shutdown(self):

        self.runtime.stop()

        self.gui.shutdown()