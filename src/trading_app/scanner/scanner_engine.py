#
#  Momentum Calculations
#  Trade Candidate Rules (momentum score, flag, and alerts)
#
# subscribes to MarketEvent QUOTES and updates ScannerState; 
# then forwards normalized quotes to ScannerState
#

import logging

from trading_app.bus import (
    EventBus,
    SystemEvent,
    EventType,
)

from trading_app.scanner.scanner_state import ScannerState

class  ScannerEngine:

    def __init__(self, bus: EventBus, scanner_state: ScannerState):
        self.scanner_state = scanner_state
        self.bus = bus
        self.running = True
        self.logger = logging.getLogger(__name__)

    async def run(self):

        async for event in self.bus.subscribe_market():

            if not self.running:
                break

            if event.event is not EventType.QUOTES:
                continue

            await self.on_quote(event)


    def stop(self):
        self.running = False


    async def on_quote(self, event):

        self.logger.debug("ScannerEngine.on_quote entered")

        state = self.scanner_state.update_quote(event.payload)

        try:
            snapshot = self.scanner_state.dirty_snapshot()
        except Exception:
            self.logger.exception("dirty_snapshot failed")
            raise

        if not snapshot:
            return
        
        self.logger.debug(
            "Scanner updated %s last=%s volume=%s",
            state.symbol,
            state.last,
            state.total_volume,
        )

        self.logger.debug(
            "Publishing %d dirty scanner symbols",
            len(snapshot),
        )

        await self.bus.publish_system(
            SystemEvent(
                name="SCANNER_UPDATED",
                payload=snapshot,
            )
        )

        self.logger.debug("SCANNER_UPDATED publish completed")