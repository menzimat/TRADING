import unittest

from trading_app.models.order import OrderType, Side
from trading_app.models.trade_instruction import TradeInstruction
from trading_app.services.order_factory import OrderFactory
from trading_app.trading_config import OffsetUnits, PriceBasis, QuantityType


class OrderFactoryManualPriceTests(unittest.TestCase):
    def test_manual_price_override_is_used_for_limit_orders(self):
        instruction = TradeInstruction(
            symbol="AAPL",
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            quantity_type=QuantityType.FIXED,
            quantity_value=100,
            price_basis=PriceBasis.ASK,
            offset_units=OffsetUnits.DOLLARS,
            offset_value=0.25,
            ask=100.0,
            order_price=100.25,
            manual_order_price=102.5,
        )

        request = OrderFactory().create(instruction)

        self.assertEqual(request.limit_price, 102.5)


if __name__ == "__main__":
    unittest.main()
