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
    OrderType,
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

    stop_base_price: Optional[float]

    stop_price: Optional[float]


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

        base = cls._base_price(instruction.price_basis, instruction)
        execution_offset = 0.0

        if (
            instruction.order_type in (OrderType.LIMIT, OrderType.STOP_LIMIT)
            and instruction.manual_order_price is not None
        ):
            order_price = round(instruction.manual_order_price, 2)
        elif base is None:
            order_price = None
        else:
            offset = cls._offset_amount(
                base, instruction.offset_value, instruction.offset_units,
            )
            if instruction.side is Side.SELL:
                offset = -offset
            execution_offset = offset
            order_price = round(base + offset, 2)

        if not instruction.requires_stop_price:
            return PriceCalculation(
                base,
                execution_offset,
                order_price,
                None,
                None,
            )

        stop_base = cls._base_price(
            instruction.stop_price_basis,
            instruction,
        )
        if stop_base is None:
            stop_price = None
        else:
            stop_offset = cls._offset_amount(
                stop_base,
                instruction.stop_offset_value,
                instruction.stop_offset_units,
            )
            if instruction.side is Side.SELL:
                stop_offset = -stop_offset
            stop_price = round(stop_base + stop_offset, 2)

        return PriceCalculation(
            base,
            execution_offset,
            order_price,
            stop_base,
            stop_price,
        )

    #
    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------
    #

    @staticmethod
    def _base_price(
        basis: PriceBasis,
        instruction: TradeInstruction,
    ) -> Optional[float]:
        """
        Determine the unadjusted market price.
        """

        match basis:

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
            f"Unsupported price basis: {basis}"
        )

    @staticmethod
    def _offset_amount(
        base_price: float,
        offset_value: float,
        offset_units: OffsetUnits,
    ) -> float:
        """
        Convert the configured offset into
        an absolute dollar adjustment.
        """

        match offset_units:

            case OffsetUnits.DOLLARS:
                return offset_value

            case OffsetUnits.PERCENT:
                return (
                    base_price
                    * offset_value
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
                    offset_value
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

        instruction.stop_base_price = result.stop_base_price
        instruction.stop_price = result.stop_price
