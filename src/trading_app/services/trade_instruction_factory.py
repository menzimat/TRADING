"""
services/trade_instruction_factory.py

Build TradeInstruction objects from trading.yaml templates.

Responsibilities

    - Read TradingConfig
    - Apply trading defaults
    - Apply selected template
    - Copy current quote
    - Calculate initial order price

Non-responsibilities

    - Broker communication
    - GUI
    - OrderRequest construction
"""

from __future__ import annotations

from trading_app.models.trade_instruction import (
    TradeInstruction,
)

from trading_app.services.price_calculator import (
    PriceCalculator,
)

from trading_app.trading_config import (
    TradingConfig,
)


class TradeInstructionFactory:
    """
    Factory for TradeInstruction objects.

    The resulting TradeInstruction is fully populated
    and immediately suitable for display in the GUI.
    """

    def __init__(
        self,
        config: TradingConfig,
    ):

        self.config = config

    #
    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------
    #

    def create(
        self,
        *,
        template_name: str,
        symbol: str,
        quote=None,
    ) -> TradeInstruction:
        """
        Build a TradeInstruction.

        Parameters
        ----------
        template_name

            Template key from trading.yaml.

        symbol

            Current trading symbol.

        quote

            QuoteState or compatible object.
            Expected members:

                bid
                ask
                last
        """

        defaults = self.config.defaults

        template = self.config.templates[
            template_name
        ]

        #
        # Resolve named offset.
        #

        offset = self.config.price_offsets[
            template.price.offset
        ]

        instruction = TradeInstruction(

            #
            # Template
            #

            template_name=template_name,

            template_display_name=self._display_name(
                template_name
            ),

            #
            # Instrument
            #

            symbol=symbol.upper(),

            account=defaults.account,

            #
            # Order
            #

            side=template.side,

            order_type=template.order_type,

            tif=template.tif,

            #
            # Quantity
            #

            quantity_type=(
                template.quantity.type
            ),

            quantity_value=(
                template.quantity.value
            ),

            #
            # Pricing
            #

            price_basis=(
                template.price.basis
            ),

            offset_name=(
                template.price.offset
            ),

            offset_value=(
                offset.value
            ),

            offset_units=(
                offset.units
            ),

            #
            # Runtime options
            #

            review_before_send=True,

            extended_hours=False,

            allow_partial_fill=True,
        )

        #
        # Copy live quote.
        #

        #
        # Copy live quote.
        #
        # Runtime currently provides dictionaries.
        # StateEngine may provide QuoteState objects.
        #

        if quote is not None:

            if isinstance(quote, dict):

                instruction.bid = quote.get(
                    "bid"
                )

                instruction.ask = quote.get(
                    "ask"
                )

                instruction.last = quote.get(
                    "last"
                )

            else:

                instruction.bid = quote.bid

                instruction.ask = quote.ask

                instruction.last = quote.last

        #
        # Initial price calculation.
        #

        PriceCalculator.apply(
            instruction
        )

        return instruction

    #
    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------
    #

    @staticmethod
    def _display_name(
        template_name: str,
    ) -> str:
        """
        Convert

            buy_limit

        into

            Buy Limit

        until display_name is added
        to trading.yaml.
        """

        return (
            template_name
            .replace("_", " ")
            .title()
        )