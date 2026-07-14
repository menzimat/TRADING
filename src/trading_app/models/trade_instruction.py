"""
models/trade_instruction.py

Mutable trading instruction model.

A TradeInstruction represents the complete order the trader is
currently editing. It is NOT a broker order.

Sources:

    TradingConfig templates
    Hotkeys
    GUI edits
    Automated strategies

Consumers:

    TradeInstructionPanel
    PriceCalculator
    OrderFactory
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from trading_app.models.order import (
    Side,
    OrderType,
    TimeInForce,
)

from trading_app.trading_config import (
    QuantityType,
    PriceBasis,
    OffsetUnits,
)


# ---------------------------------------------------------
# Main instruction
# ---------------------------------------------------------


@dataclass(slots=True)
class TradeInstruction:
    """
    Mutable GUI trading instruction.

    Unlike OrderRequest this object contains both
    trader intent and live market information.

    It is expected to change repeatedly while
    the trader edits an order.
    """

    #
    # Template
    #

    template_name: str = ""

    template_display_name: str = ""

    #
    # Instrument
    #

    symbol: str = ""

    account: str = ""

    account_hash: Optional[str] = None

    #
    # Order
    #

    side: Side = Side.BUY

    order_type: OrderType = OrderType.MARKET

    tif: TimeInForce = TimeInForce.DAY

    #
    # Quantity
    #

    quantity_type: QuantityType = QuantityType.FIXED

    quantity_value: int = 100

    #
    # Pricing
    #

    price_basis: PriceBasis = PriceBasis.MARKET

    offset_name: str = ""

    offset_value: float = 0.0

    offset_units: OffsetUnits = OffsetUnits.DOLLARS

    #
    # Live market
    #

    bid: Optional[float] = None

    ask: Optional[float] = None

    last: Optional[float] = None

    #
    # Calculated values
    #

    base_price: Optional[float] = None

    order_price: Optional[float] = None

    manual_order_price: Optional[float] = None

    #
    # Convenience
    #

    review_before_send: bool = True

    extended_hours: bool = False

    allow_partial_fill: bool = True

    #
    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------
    #

    @property
    def is_market(self) -> bool:
        return self.order_type is OrderType.MARKET

    @property
    def is_limit(self) -> bool:
        return self.order_type is OrderType.LIMIT

    @property
    def is_stop(self) -> bool:
        return self.order_type is OrderType.STOP

    @property
    def is_stop_limit(self) -> bool:
        return self.order_type is OrderType.STOP_LIMIT

    @property
    def quantity(self) -> int:
        """
        Alias used by OrderFactory.
        """
        return self.quantity_value

    @property
    def has_live_quote(self) -> bool:
        return any(
            value is not None
            for value in (
                self.bid,
                self.ask,
                self.last,
            )
        )

    @property
    def summary(self) -> str:
        """
        Human-readable preview shown in the GUI.
        """

        side = self.side.name

        order_type = self.order_type.name

        tif = self.tif.name

        qty = self.quantity_value

        symbol = self.symbol or "?"

        if self.order_price is None:
            return (
                f"{side} {qty} {symbol} "
                f"{order_type} {tif}"
            )

        return (
            f"{side} {qty} {symbol} "
            f"@ {self.order_price:.2f} "
            f"{order_type} {tif}"
        )