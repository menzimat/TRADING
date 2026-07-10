"""
services/order_factory.py

Build OrderRequest objects from trading.yaml templates.

The OrderFactory centralizes all order construction for:

    GUI
    Hotkeys
    Future automation
"""

from __future__ import annotations

from trading_app.models.order import (
    OrderRequest,
    Side,
    OrderType,
    TimeInForce,
)

from trading_app.engine.state_engine import (
    QuoteState,
)

from trading_app.trading_config import (
    QuantityDefinition,
    PriceDefinition,
    PriceBasis,
    QuantityType,
    OffsetUnits,
)


class OrderFactory:

    def __init__(
        self,
        *,
        config,
        state_engine,
        symbol_provider,
    ):

        self.config = config
        self.state_engine = state_engine
        self.symbol_provider = symbol_provider

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------

    def create_from_template(
        self,
        template_name: str,
    ) -> OrderRequest:

        symbol = self.symbol_provider.get_selected_symbol()

        if not symbol:
            raise RuntimeError(
                "No symbol selected."
            )

        quote = self.state_engine.get_quote(symbol)

        if quote is None:
            raise RuntimeError(
                f"No quote available for {symbol}"
            )

        template = self.config.templates[template_name]

        qty = self._resolve_quantity(
            template.quantity
        )

        price = self._compute_price(
            quote,
            template.price,
        )

        return OrderRequest(

            symbol=symbol,

            quantity=qty,

            side=self._side(
                template.side
            ),

            order_type=self._order_type(
                template.order_type
            ),

            tif=self._tif(
                template.tif
            ),

            limit_price=price,

            review_before_send=(
                self.config.defaults.review_orders
            ),

            extended_hours=(
                self.config.defaults.extended_hours
            ),
        )

    # ---------------------------------------------------------
    # Quantity
    # ---------------------------------------------------------

    def _resolve_quantity(
        self,
        quantity: QuantityDefinition,
    ) -> int:
        """
        Resolve a quantity definition into a share count.

        Supported types:

            fixed
            risk      (future)
            dollars   (future)
            percent   (future)
        """

        match quantity.type.lower():

            case "fixed":
                return int(quantity.value)

            case "risk":
                raise NotImplementedError(
                    "Risk-based sizing not implemented."
                )

            case "dollars":
                raise NotImplementedError(
                    "Dollar sizing not implemented."
                )

            case "percent":
                raise NotImplementedError(
                    "Percent sizing not implemented."
                )

            case _:
                raise ValueError(
                    f"Unknown quantity type: "
                    f"{quantity.type}"
                )

     # ---------------------------------------------------------
    # Price
    # ---------------------------------------------------------

    def _compute_price(
        self,
        quote: QuoteState,
        price: PriceDefinition,
    ) -> float | None:
        """
        Compute the order price from the current quote
        and the template's pricing definition.
        """

        #
        # Resolve named offset.
        #

        offset = self.config.price_offsets[price.offset]

        #
        # Choose base price.
        #

        match price.basis:

            case PriceBasis.ASK:
                base = quote.ask

            case PriceBasis.BID:
                base = quote.bid

            case PriceBasis.LAST:
                base = quote.last

            case PriceBasis.MARKET:
                return None

            #
            # Market orders do not require a limit.
            #

        if base is None:
            return None

        #
        # Dollar offsets
        #

        if offset.units == "dollars":

            return round(
                base + offset.value,
                2,
            )

        #
        # Percent offsets
        #

        if offset.units == "percent":

            return round(
                base * (
                    1.0 + offset.value / 100.0
                ),
                2,
            )

        #
        # Tick offsets
        #

        if offset.units == "ticks":

            #
            # Replace 0.01 later with
            # instrument tick size.
            #

            return round(
                base + offset.value * 0.01,
                2,
            )

        raise ValueError(
            f"Unknown offset units: "
            f"{offset.units}"
        )