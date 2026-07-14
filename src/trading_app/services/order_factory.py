"""
services/order_factory.py

Convert TradeInstruction objects into OrderRequest objects.

Responsibilities:

    - Translate GUI/strategy instruction into
      internal broker-neutral order model.

Non-responsibilities:

    - Reading trading.yaml
    - Looking up quotes
    - Calculating prices
    - Resolving quantities
    - GUI interaction
"""

from __future__ import annotations


from trading_app.models.order import (
    OrderRequest,
)

from trading_app.models.trade_instruction import (
    TradeInstruction,
)


class OrderFactory:
    """
    Build OrderRequest objects from TradeInstruction.

    This is the final application-layer translation
    before Runtime submits the order.
    """

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------

    def create(
        self,
        instruction: TradeInstruction,
    ) -> OrderRequest:
        """
        Convert a TradeInstruction into an OrderRequest.
        """

        if not instruction.symbol:

            raise ValueError(
                "Trade instruction has no symbol."
            )


        request = OrderRequest(

            #
            # Instrument
            #

            symbol=instruction.symbol,

            quantity=instruction.quantity,

            account_hash=instruction.account_hash,

            #
            # Order fields
            #

            side=instruction.side,

            order_type=instruction.order_type,

            tif=instruction.tif,


            #
            # Price fields
            #

            limit_price=(
                instruction.manual_order_price
                if instruction.is_limit
                and instruction.manual_order_price is not None
                else (
                    instruction.order_price
                    if instruction.is_limit
                    else None
                )
            ),


            #
            # Runtime options
            #

            review_before_send=(
                instruction.review_before_send
            ),

            extended_hours=(
                instruction.extended_hours
            ),

            allow_partial_fill=(
                instruction.allow_partial_fill
            ),
        )


        return request