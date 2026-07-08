"""
models/order.py

Trading order model.

Every order submitted anywhere in the application is represented
by an OrderRequest.

Sources:

    - GUI buttons
    - Hotkeys
    - Automated strategies
    - Future scripting interface

Consumers:

    - CommandProcessor
    - Schwab broker adapter
"""

from __future__ import annotations


from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Optional
import uuid



# ---------------------------------------------------------
# Enumerations
# ---------------------------------------------------------


class Side(Enum):

    BUY = auto()
    SELL = auto()


class OrderType(Enum):

    MARKET = auto()
    LIMIT = auto()
    STOP = auto()
    STOP_LIMIT = auto()
    TRAILING_STOP = auto()


class TimeInForce(Enum):

    DAY = auto()
    GTC = auto()
    IOC = auto()
    FOK = auto()



class OrderStatus(Enum):

    CREATED = auto()
    QUEUED = auto()
    SUBMITTED = auto()
    ACKNOWLEDGED = auto()
    FILLED = auto()
    PARTIAL = auto()
    CANCELLED = auto()
    REJECTED = auto()
    ERROR = auto()



# ---------------------------------------------------------
# Main Order
# ---------------------------------------------------------


@dataclass(slots=True)
class OrderRequest:
    """
    Internal order representation.

    This is the only order object that moves through:

        GUI
         |
         v
        Runtime
         |
         v
     CommandProcessor
         |
         v
       Broker
    """

    #
    # Identity
    #

    request_id: str = field(
        default_factory=lambda:
            str(uuid.uuid4())
    )


    created: datetime = field(
        default_factory=lambda:
            datetime.now(timezone.utc)
    )


    #
    # Instrument
    #

    symbol: str = ""

    quantity: int = 0



    #
    # Command fields
    #

    side: Side = Side.BUY

    order_type: OrderType = (
        OrderType.MARKET
    )

    tif: TimeInForce = (
        TimeInForce.DAY
    )


    #
    # Price fields
    #

    limit_price: Optional[float] = None

    stop_price: Optional[float] = None

    trailing_offset: Optional[float] = None



    #
    # Trading offsets
    #

    entry_offset: float = 0.0

    exit_offset: float = 0.0

    stop_offset: float = 0.0



    #
    # Runtime state
    #

    status: OrderStatus = (
        OrderStatus.CREATED
    )

    broker_order_id: Optional[str] = None

    message: str = ""



    #
    # Execution options
    #

    review_before_send: bool = True

    extended_hours: bool = False

    allow_partial_fill: bool = True



    #
    # -------------------------------------------------
    # Lifecycle helpers
    # -------------------------------------------------
    #


    def __post_init__(self):

        self.symbol = (
            self.symbol.upper()
            .strip()
        )



    #
    # -------------------------------------------------
    # Compatibility properties
    # -------------------------------------------------
    #

    @property
    def price(self):
        """
        Compatibility with CommandProcessor.
        """

        return self.limit_price



    @property
    def command_side(self):
        """
        Convert to EventBus command enum.
        """

        from trading_app.bus import CommandType


        if self.side is Side.BUY:

            return CommandType.BUY

        return CommandType.SELL



    #
    # -------------------------------------------------
    # Convenience
    # -------------------------------------------------
    #


    @property
    def is_buy(self):

        return self.side is Side.BUY



    @property
    def is_sell(self):

        return self.side is Side.SELL



    @property
    def is_market(self):

        return (
            self.order_type
            is OrderType.MARKET
        )



    @property
    def is_limit(self):

        return (
            self.order_type
            is OrderType.LIMIT
        )



    @property
    def is_stop(self):

        return (
            self.order_type
            is OrderType.STOP
        )



    @property
    def is_stop_limit(self):

        return (
            self.order_type
            is OrderType.STOP_LIMIT
        )



    #
    # -------------------------------------------------
    # Validation
    # -------------------------------------------------
    #


    def validate(self):

        if not self.symbol:

            raise ValueError(
                "Missing symbol."
            )


        if self.quantity <= 0:

            raise ValueError(
                "Quantity must be positive."
            )


        if (
            self.order_type
            is OrderType.LIMIT
            and self.limit_price is None
        ):

            raise ValueError(
                "Limit orders require limit_price."
            )


        if (
            self.order_type
            is OrderType.STOP
            and self.stop_price is None
        ):

            raise ValueError(
                "Stop orders require stop_price."
            )


        if (
            self.order_type
            is OrderType.STOP_LIMIT
            and (
                self.stop_price is None
                or self.limit_price is None
            )
        ):

            raise ValueError(
                "Stop-Limit orders require "
                "stop_price and limit_price."
            )


        return True



    #
    # -------------------------------------------------
    # Broker conversion
    # -------------------------------------------------
    #


    def to_broker_dict(self):
        """
        Convert internal model into
        broker-neutral order dictionary.
        """

        self.validate()


        return {

            "symbol":
                self.symbol,

            "quantity":
                self.quantity,

            "side":
                self.side.name,

            "order_type":
                self.order_type.name,

            "time_in_force":
                self.tif.name,

            "limit_price":
                self.limit_price,

            "stop_price":
                self.stop_price,

            "extended_hours":
                self.extended_hours,
        }



    #
    # -------------------------------------------------
    # Copy
    # -------------------------------------------------
    #


    def copy(self):

        return OrderRequest(

            symbol=self.symbol,

            quantity=self.quantity,

            side=self.side,

            order_type=self.order_type,

            tif=self.tif,

            limit_price=self.limit_price,

            stop_price=self.stop_price,

            trailing_offset=
                self.trailing_offset,

            entry_offset=
                self.entry_offset,

            exit_offset=
                self.exit_offset,

            stop_offset=
                self.stop_offset,

            review_before_send=
                self.review_before_send,

            extended_hours=
                self.extended_hours,

            allow_partial_fill=
                self.allow_partial_fill,
        )