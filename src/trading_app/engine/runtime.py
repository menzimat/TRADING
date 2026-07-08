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
from typing import Optional


from trading_app.bus import (
    CommandEvent,
    SystemEvent,
)



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
    ):

        self.bus = bus

        self.streamer = streamer

        self.command_processor = (
            command_processor
        )

        self.state_engine = (
            state_engine
        )


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


    # ==========================================================
    # GUI Attachment
    # ==========================================================

    def attach_gui(
        self,
        gui,
    ):

        self.gui = gui



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

        async for event in (
            self.bus.subscribe_system()
        ):

            if event.name == "PRICE_UPDATED":

                self.gui_queue.put(event)

            elif event.name in (
                "CONNECTED",
                "DISCONNECTED",
                "STREAM_ERROR",
            ):

                self.gui_queue.put(event)


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

            if event.name == "PRICE_UPDATED":

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

        if hasattr(payload, "symbol"):

            self.gui.update_quote(
                payload.symbol,
                payload,
            )
        return


    # ==========================================================
    # GUI -> Async command path
    # ==========================================================

    def submit_order(
        self,
        request,
    ):

        """
        Called by OrderPanel.

        Converts GUI request into
        CommandEvent.
        """

        if not self.loop:

            return


        from trading_app.bus import CommandType


        event = CommandEvent(
            command=request.command_side,
            payload=request,
            )

        asyncio.run_coroutine_threadsafe(
            self.bus.publish_command(
                event
            ),
            self.loop,
        )



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