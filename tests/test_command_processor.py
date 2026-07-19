import asyncio
import unittest

from trading_app.models.order import OrderRequest, OrderType, Side
from trading_app.services.command_processor import CommandProcessor


class DummyBus:
    def __init__(self):
        self.events = []

    async def publish_system(self, event):
        self.events.append(event)
        return None


class DummyStateEngine:
    pass


class PositionAwareStateEngine:
    def __init__(self, positions=None):
        self.positions = positions or {}

    def get_position(self, symbol, account_hash=None):
        return self.positions.get(symbol.upper())


class DummyClient:
    def __init__(self):
        self.account_hash = None
        self.accounts = []
        self.placed_orders = []

    async def place_order(self, account_hash, payload):
        self.last_account_hash = account_hash
        self.last_payload = payload
        self.placed_orders.append((account_hash, payload))
        return {"ok": True}


class DummyResponse:
    def __init__(self, status_code=200, headers=None, body="ok"):
        self.status_code = status_code
        self.headers = headers or {"content-type": "application/json"}
        self._body = body
        self.text = body


class CommandProcessorTests(unittest.TestCase):
    def test_limit_order_submission_uses_request_payload(self):
        processor = CommandProcessor(
            client=DummyClient(),
            bus=DummyBus(),
            state_engine=DummyStateEngine(),
        )

        seen = {}

        async def fake_submit_order(self, request):
            seen["request"] = request

        processor.submit_order = fake_submit_order.__get__(processor, CommandProcessor)

        request = OrderRequest(
            symbol="AAPL",
            quantity=1,
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            limit_price=1.46,
        )

        asyncio.run(processor.submit_limit_order(request, "BUY"))

        self.assertIs(seen["request"], request)

    def test_place_order_uses_selected_account_hash(self):
        client = DummyClient()
        processor = CommandProcessor(
            client=client,
            bus=DummyBus(),
            state_engine=DummyStateEngine(),
            account_provider=lambda: "provider-account-hash",
        )

        request = OrderRequest(
            symbol="AAPL",
            quantity=1,
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            limit_price=1.46,
            account_hash="request-account-hash",
        )

        asyncio.run(processor.submit_order(request))

        self.assertEqual(client.last_account_hash, "request-account-hash")

    def test_extract_response_diagnostics(self):
        processor = CommandProcessor(
            client=DummyClient(),
            bus=DummyBus(),
            state_engine=DummyStateEngine(),
        )

        response = DummyResponse(
            status_code=403,
            headers={"x-error": "boom"},
            body='{"error":"bad"}',
        )

        diagnostics = processor._extract_response_diagnostics(response)

        self.assertEqual(diagnostics["status_code"], 403)
        self.assertEqual(diagnostics["headers"], {"x-error": "boom"})
        self.assertEqual(diagnostics["body"], '{"error":"bad"}')

    def test_sell_order_caps_quantity_to_cached_position(self):
        bus = DummyBus()
        client = DummyClient()
        client.account_hash = "acct-1"
        state_engine = PositionAwareStateEngine(
            {"AAPL": type("Position", (), {"quantity": 3})()}
        )
        processor = CommandProcessor(
            client=client,
            bus=bus,
            state_engine=state_engine,
        )

        request = OrderRequest(
            symbol="AAPL",
            quantity=10,
            side=Side.SELL,
            order_type=OrderType.MARKET,
        )

        asyncio.run(processor.submit_order(request))

        self.assertEqual(client.placed_orders[0][1]["quantity"], 3)

    def test_sell_without_position_is_rejected(self):
        bus = DummyBus()
        client = DummyClient()
        client.account_hash = "acct-1"
        processor = CommandProcessor(
            client=client,
            bus=bus,
            state_engine=PositionAwareStateEngine(),
        )

        request = OrderRequest(
            symbol="AAPL",
            quantity=1,
            side=Side.SELL,
            order_type=OrderType.MARKET,
        )

        asyncio.run(processor.submit_order(request))

        self.assertEqual(client.placed_orders, [])
        self.assertTrue(
            any(event.name == "ORDER_REJECTED" for event in bus.events)
        )


if __name__ == "__main__":
    unittest.main()
