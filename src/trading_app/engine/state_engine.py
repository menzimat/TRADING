"""
engine/state_engine.py

Authoritative application state engine.

Responsibilities:

    - Consume market events
    - Maintain current application state
    - Provide state queries
    - Publish derived system events

Non-responsibilities:

    - Broker communication
    - Order execution
    - GUI updates
"""

from __future__ import annotations
import time
import logging

from dataclasses import dataclass, field
from typing import Dict, Any, Optional


from trading_app.bus import (
    EventBus,
    MarketEvent,
    EventType,
    SystemEvent,
)


logger = logging.getLogger(__name__)


@dataclass
class QuoteState:
    """
    Current quote for one symbol.

    Represents the latest known values,
    not an update from Schwab.
    """

    symbol: str

    bid: float | None = None

    ask: float | None = None

    last: float | None = None

    volume: int | None = None

@dataclass
class AccountState:
    """
    Account snapshot.
    """

    cash: float = 0.0

    buying_power: float = 0.0



@dataclass
class PositionState:
    """
    Single position.
    """

    symbol: str

    quantity: int = 0

    average_price: float = 0.0



@dataclass
class ApplicationState:
    """
    Complete application state.
    """

    quotes: Dict[str, QuoteState] = field(
        default_factory=dict
    )

    positions: Dict[str, PositionState] = field(
        default_factory=dict
    )

    orders: Dict[str, Any] = field(
        default_factory=dict
    )

    account: AccountState = field(
        default_factory=AccountState
    )



class StateEngine:
    """
    Central application state manager.
    """


    def __init__(
        self,
        bus: EventBus,
    ):

        self.bus = bus

        self.state = ApplicationState()

        self.running = True



    # ==========================================================
    # Runtime entry point
    # ==========================================================

    async def run(self):

        logger.info(
            "StateEngine started"
        )


        async for event in (
            self.bus.subscribe_market()
        ):

            if not self.running:

                break


            await self.process_market_event(
                event
            )



    # ==========================================================
    # Market processing
    # ==========================================================

    async def process_market_event(
        self,
        event: MarketEvent,
    ):

        print(
        "STATE EVENT:",
        event.event,
        event.payload
    )

        if event.event == EventType.QUOTES:

            await self.update_quote(
                event.payload
            )


        elif event.event == EventType.POSITION:

            self.update_position(
                event.payload
            )


        elif event.event == EventType.ORDER:

            self.update_order(
                event.payload
            )


        elif event.event == EventType.ACCOUNT:

            self.update_account(
                event.payload
            )



    # ==========================================================
    # State updates
    # ==========================================================

    async def update_quote(
        self,
        quote,
    ):

        symbol = quote.get("symbol")

        if not symbol:
            return

        symbol = symbol.upper()

        #
        # Get existing quote or create one.
        #
        current = self.state.quotes.get(symbol)

        if current is None:
            current = QuoteState(symbol=symbol)
            self.state.quotes[symbol] = current

        #
        # Save previous last price before merge.
        #

        old_price = current.last

        if "bid" in quote:
            current.bid = quote["bid"]

        if "ask" in quote:
            current.ask = quote["ask"]

        if "last" in quote:
            current.last = quote["last"]

        if "volume" in quote:
            current.volume = quote["volume"]

        #
        # Determine whether last price changed.
        #

        new_price = current.last

        if (
            old_price is not None
            and new_price is not None
            and old_price != new_price
        ):

            await self.bus.publish_system(
                SystemEvent(
                    name="PRICE_UPDATED",
                    payload={
                        "symbol": symbol,
                        "bid": current.bid,
                        "ask": current.ask,
                        "last": current.last,
                        "volume": current.volume,
                    },
                )
            )
        current.updated = time.time()
        return current
    
       
    def update_position(
        self,
        position,
    ):

        symbol = (position["symbol"].upper())

        self.state.positions[
            symbol
        ] = PositionState(
            symbol=symbol,
            quantity=
                position.get(
                    "quantity",
                    0,
                ),
            average_price=
                position.get(
                    "average_price",
                    0.0,
                ),
        )



    def update_order(
        self,
        order,
    ):

        order_id = (
            order["id"]
        )


        self.state.orders[
            order_id
        ] = order



    def update_account(
        self,
        account,
    ):

        self.state.account = (
            AccountState(
                cash=
                    account.get(
                        "cash",
                        0.0,
                    ),

                buying_power=
                    account.get(
                        "buying_power",
                        0.0,
                    ),
            )
        )



    # ==========================================================
    # Query API
    # ==========================================================

    def get_quote(
        self,
        symbol: str,
    ) -> Optional[dict]:

        return self.state.quotes.get(
            symbol.upper()
        )



    def get_position(
        self,
        symbol: str,
    ) -> Optional[PositionState]:

        return self.state.positions.get(
            symbol.upper()
        )



    def get_all_positions(
        self,
    ):

        return self.state.positions



    def get_account(
        self,
    ):

        return self.state.account



    def has_position(
        self,
        symbol: str,
    ) -> bool:

        position = (
            self.get_position(
                symbol
            )
        )

        return (
            position is not None
            and position.quantity != 0
        )



    # ==========================================================
    # Shutdown
    # ==========================================================

    def stop(
        self,
    ):

        self.running = False