import unittest

from trading_app.engine.runtime import Runtime
from trading_app.gui.trade_instruction_panel import TradeInstructionPanel
from trading_app.models.order import OrderType, Side
from trading_app.models.trade_instruction import TradeInstruction
from trading_app.services.price_calculator import PriceCalculator
from trading_app.trading_config import OffsetUnits, PriceBasis, QuantityType


class PositionStateEngine:
    def __init__(self, quantity):
        self.position = type("Position", (), {"quantity": quantity})()

    def get_position(self, symbol):
        return self.position if symbol == "AAPL" else None


class CapturingOrderFactory:
    def __init__(self):
        self.instruction = None

    def create(self, instruction):
        self.instruction = instruction
        return instruction


class PercentagePositionSizingTests(unittest.TestCase):
    def make_runtime(self, quantity=125):
        return Runtime(
            bus=None,
            streamer=None,
            command_processor=None,
            state_engine=PositionStateEngine(quantity),
        )

    def test_percent_sell_resolves_to_fixed_shares_from_cached_position(self):
        instruction = TradeInstruction(
            symbol="AAPL",
            side=Side.SELL,
            quantity_type=QuantityType.PERCENT,
            quantity_value=40,
        )

        resolved = self.make_runtime()._resolve_instruction_quantity(instruction)

        self.assertEqual(resolved.quantity_type, QuantityType.FIXED)
        self.assertEqual(resolved.quantity_value, 50)
        self.assertEqual(instruction.quantity_type, QuantityType.PERCENT)
        self.assertEqual(instruction.quantity_value, 40)

    def test_submit_instruction_passes_resolved_share_count_to_order_factory(self):
        order_factory = CapturingOrderFactory()
        runtime = Runtime(
            bus=None,
            streamer=None,
            command_processor=None,
            state_engine=PositionStateEngine(125),
            order_factory=order_factory,
        )
        runtime.submit_order = lambda request: request
        instruction = TradeInstruction(
            symbol="AAPL",
            side=Side.SELL,
            quantity_type=QuantityType.PERCENT,
            quantity_value=40,
        )

        runtime.submit_instruction(instruction)

        self.assertEqual(order_factory.instruction.quantity_value, 50)
        self.assertEqual(order_factory.instruction.quantity_type, QuantityType.FIXED)

    def test_review_text_uses_resolved_share_count(self):
        instruction = TradeInstruction(
            symbol="AAPL",
            side=Side.SELL,
            quantity_type=QuantityType.PERCENT,
            quantity_value=40,
        )
        resolved = self.make_runtime().resolve_instruction_quantity(instruction)

        review_text = TradeInstructionPanel._review_text(resolved)

        self.assertIn("Quantity: 50", review_text)
        self.assertNotIn("Quantity: 40", review_text)

    def test_sell_limit_price_is_bid_minus_default_offset(self):
        instruction = TradeInstruction(
            symbol="AAPL",
            side=Side.SELL,
            order_type=OrderType.LIMIT,
            price_basis=PriceBasis.BID,
            offset_units=OffsetUnits.DOLLARS,
            offset_value=0.10,
            bid=25.00,
        )

        calculation = PriceCalculator.calculate(instruction)

        self.assertEqual(calculation.base_price, 25.00)
        self.assertEqual(calculation.offset_amount, -0.10)
        self.assertEqual(calculation.order_price, 24.90)


if __name__ == "__main__":
    unittest.main()
