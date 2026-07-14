"""
services/price_calculator.py

Pricing calculations for TradeInstruction.

Responsibilities:

    - Determine the base price from the selected basis.
    - Apply dollar / percent / tick offsets.
    - Produce the final order price.

Non-responsibilities:

    - Building OrderRequest objects.
    - Reading TradingConfig.
    - GUI updates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from trading_app.models.trade_instruction import (
    TradeInstruction,
)

from trading_app.trading_config import (
    PriceBasis,
    OffsetUnits,
)

from trading_app.models.order import (
    Side,
)

# ---------------------------------------------------------
# Calculation Result
# ---------------------------------------------------------


@dataclass(slots=True, frozen=True)
class PriceCalculation:
    """
    Result of a pricing calculation.
    """

    base_price: Optional[float]

    offset_amount: float

    order_price: Optional[float]


# ---------------------------------------------------------
# Price Calculator
# ---------------------------------------------------------


class PriceCalculator:
    """
    Stateless pricing service.
    """

    #
    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------
    #

    @classmethod
    def calculate(
        cls,
        instruction: TradeInstruction,
    ) -> PriceCalculation:
        """
        Compute the current order price.

        Market orders intentionally return None for
        base_price and order_price.
        """

        base = cls._base_price(instruction)

        if (
            instruction.is_limit
            and instruction.manual_order_price is not None
        ):
            return PriceCalculation(
                base_price=base,
                offset_amount=0.0,
                order_price=round(
                    instruction.manual_order_price,
                    2,
                ),
            )

        if base is None:
            return PriceCalculation(
                base_price=None,
                offset_amount=0.0,
                order_price=None,
            )

        offset = cls._offset_amount(
            base,
            instruction,
        )
        if instruction.side is Side.SELL:
            offset = -offset

        return PriceCalculation(
            base_price=base,
            offset_amount=offset,
            order_price=round(
                base + offset,
                2,
            ),
        )

    #
    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------
    #

    @staticmethod
    def _base_price(
        instruction: TradeInstruction,
    ) -> Optional[float]:
        """
        Determine the unadjusted market price.
        """

        match instruction.price_basis:

            case PriceBasis.BID:
                return instruction.bid

            case PriceBasis.ASK:
                return instruction.ask

            case PriceBasis.LAST:
                return instruction.last

            case PriceBasis.MARKET:
                #
                # Market orders do not require
                # a calculated limit price.
                #
                return None

        raise ValueError(
            f"Unsupported price basis: "
            f"{instruction.price_basis}"
        )

    @staticmethod
    def _offset_amount(
        base_price: float,
        instruction: TradeInstruction,
    ) -> float:
        """
        Convert the configured offset into
        an absolute dollar adjustment.
        """

        match instruction.offset_units:

            case OffsetUnits.DOLLARS:
                return instruction.offset_value

            case OffsetUnits.PERCENT:
                return (
                    base_price
                    * instruction.offset_value
                    / 100.0
                )

            case OffsetUnits.TICKS:
                #
                # TODO:
                #
                # Replace with the instrument's
                # actual minimum tick size.
                #
                tick_size = 0.01

                return (
                    instruction.offset_value
                    * tick_size
                )

        raise ValueError(
            f"Unsupported offset units: "
            f"{instruction.offset_units}"
        )

    #
    # ---------------------------------------------------------
    # Convenience
    # ---------------------------------------------------------
    #

    @classmethod
    def apply(
        cls,
        instruction: TradeInstruction,
    ) -> None:
        """
        Convenience helper.

        Updates the TradeInstruction with
        the current calculated prices.
        """

        result = cls.calculate(
            instruction
        )

        instruction.base_price = (
            result.base_price
        )

        instruction.order_price = (
            result.order_price
        )