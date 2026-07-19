import asyncio
import unittest

from trading_app.bus import EventType, MarketEvent
from trading_app.engine.state_engine import StateEngine


class DummyBus:
    def __init__(self):
        self.system_events = []

    async def publish_system(self, event):
        self.system_events.append(event)


class PositionSnapshotTests(unittest.TestCase):
    def test_account_snapshots_aggregate_positions_and_clear_sold_symbols(self):
        bus = DummyBus()
        engine = StateEngine(bus)

        self._snapshot(engine, "one", [{"symbol": "AAPL", "quantity": 10}])
        self._snapshot(engine, "two", [{"symbol": "AAPL", "quantity": 5}])
        self.assertEqual(engine.get_position("AAPL").quantity, 15)

        self._snapshot(engine, "one", [])
        self.assertEqual(engine.get_position("AAPL").quantity, 5)

        self._snapshot(engine, "two", [])
        self.assertEqual(engine.get_position("AAPL").quantity, 0)
        self.assertEqual(
            bus.system_events[-1].payload,
            {"account_hash": "two", "quantities": {}},
        )

    @staticmethod
    def _snapshot(engine, account_hash, positions):
        asyncio.run(engine.process_market_event(MarketEvent(
            event=EventType.POSITION_SNAPSHOT,
            payload={"account_hash": account_hash, "positions": positions},
        )))


if __name__ == "__main__":
    unittest.main()
