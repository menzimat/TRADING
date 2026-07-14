import unittest

from trading_app.bus import SystemEvent
from trading_app.engine.runtime import Runtime
from trading_app.models.order import OrderRequest, OrderType, Side


class DummyGui:
    def __init__(self):
        self.updated_quotes = []

    def update_quote(self, symbol, payload):
        self.updated_quotes.append((symbol, payload))


class RuntimeGuiEventTests(unittest.TestCase):
    def test_order_submission_event_does_not_trigger_quote_update(self):
        runtime = Runtime(
            bus=None,
            streamer=None,
            command_processor=None,
            state_engine=None,
        )
        gui = DummyGui()
        runtime.gui = gui

        request = OrderRequest(
            symbol="OTLK",
            quantity=1,
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            limit_price=1.46,
        )
        event = SystemEvent(name="ORDER_SUBMITTED", payload=request)

        runtime._handle_gui_event(event)

        self.assertEqual(gui.updated_quotes, [])


if __name__ == "__main__":
    unittest.main()
