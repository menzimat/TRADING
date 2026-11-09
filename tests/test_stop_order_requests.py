import unittest
from pathlib import Path

from trading_app.models.order import (
    OrderRequest,
    OrderType,
    Side,
    TrailingOffsetType,
)
from trading_app.services.order_factory import OrderFactory
from trading_app.services.trade_instruction_factory import TradeInstructionFactory
from trading_app.trading_config import TradingConfig


class StopOrderRequestTests(unittest.TestCase):
    def test_stop_order_has_only_a_stop_price(self):
        request = OrderRequest(
            symbol="AAPL",
            quantity=10,
            side=Side.SELL,
            order_type=OrderType.STOP,
            stop_price=99.50,
        )

        payload = request.to_broker_dict()

        self.assertEqual(payload["stopPrice"], 99.50)
        self.assertIsNone(payload["limit_price"])

    def test_stop_limit_order_has_trigger_and_execution_prices(self):
        request = OrderRequest(
            symbol="AAPL",
            quantity=10,
            side=Side.BUY,
            order_type=OrderType.STOP_LIMIT,
            stop_price=100.10,
            limit_price=100.20,
        )

        payload = request.to_broker_dict()

        self.assertEqual(payload["stopPrice"], 100.10)
        self.assertEqual(payload["price"], 100.20)

    def test_dollar_trailing_stop_uses_schwab_value_link_type(self):
        request = OrderRequest(
            symbol="AAPL",
            quantity=10,
            side=Side.SELL,
            order_type=OrderType.TRAILING_STOP,
            trailing_offset=0.10,
            trailing_offset_type=TrailingOffsetType.DOLLARS,
        )

        payload = request.to_broker_dict()

        self.assertEqual(payload["stopPriceLinkBasis"], "LAST")
        self.assertEqual(payload["stopPriceLinkType"], "VALUE")
        self.assertEqual(payload["stopPriceOffset"], 0.10)

    def test_percent_trailing_stop_uses_schwab_percent_link_type(self):
        request = OrderRequest(
            symbol="AAPL",
            quantity=10,
            side=Side.SELL,
            order_type=OrderType.TRAILING_STOP,
            trailing_offset=10,
            trailing_offset_type=TrailingOffsetType.PERCENT,
        )

        payload = request.to_broker_dict()

        self.assertEqual(payload["stopPriceLinkType"], "PERCENT")
        self.assertEqual(payload["stopPriceOffset"], 10)

    def test_trailing_price_yaml_definition_reaches_order_request(self):
        config_path = Path(__file__).parents[1] / "cfg" / "trading.yaml"
        config = TradingConfig.load(config_path)
        instruction = TradeInstructionFactory(config).create(
            template_name="sell_trailing_stop",
            symbol="AAPL",
            quote={"bid": 100.0, "ask": 100.1, "last": 100.05},
        )

        request = OrderFactory().create(instruction)
        trailing_price = config.templates[
            "sell_trailing_stop"
        ].trailing_price

        self.assertIsNotNone(trailing_price)
        self.assertEqual(request.trailing_offset, trailing_price.value)
        self.assertIs(request.trailing_offset_type, trailing_price.type)


if __name__ == "__main__":
    unittest.main()
