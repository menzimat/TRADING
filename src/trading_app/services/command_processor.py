"""
services/command_processor.py

Order command execution service.

Responsibilities:

    - Consume CommandEvents
    - Validate commands
    - Submit orders through Schwab client
    - Publish order lifecycle events

Non-responsibilities:

    - GUI updates
    - Market data
    - Position ownership
"""

from __future__ import annotations

import logging
from typing import Any


from trading_app.bus import (
    EventBus,
    CommandEvent,
    CommandType,
    SystemEvent,
)


logger = logging.getLogger(__name__)



class CommandProcessor:
    """
    Async order command processor.
    """

    def __init__(
        self,
        *,
        client,
        bus: EventBus,
        state_engine,
    ):

        self.client = client

        self.bus = bus

        self.state_engine = (
            state_engine
        )

        self.running = True



    # ==========================================================
    # Main worker
    # ==========================================================

    async def run(self):

        logger.info(
            "CommandProcessor started"
        )


        async for command in (
            self.bus.subscribe_commands()
        ):

            if not self.running:

                break


            await self.process(
                command
            )



    # ==========================================================
    # Dispatcher
    # ==========================================================

    async def process(
        self,
        event: CommandEvent,
    ):

        try:

            match event.command:

                case CommandType.BUY:

                    await self.submit_market_order(
                        event.payload,
                        "BUY",
                    )


                case CommandType.SELL:

                    await self.submit_market_order(
                        event.payload,
                        "SELL",
                    )


                case CommandType.LIMIT_BUY:

                    await self.submit_limit_order(
                        event.payload,
                        "BUY",
                    )


                case CommandType.LIMIT_SELL:

                    await self.submit_limit_order(
                        event.payload,
                        "SELL",
                    )


                case CommandType.CANCEL:

                    await self.cancel_order(
                        event.payload
                    )


                case CommandType.FLATTEN:

                    await self.flatten_position(
                        event.payload
                    )


                case CommandType.PANIC:

                    await self.panic()


                case _:

                    logger.warning(
                        "Unhandled command %s",
                        event.command,
                    )


        except Exception as exc:

            logger.exception(
                "Command processing failure"
            )

            await self.publish_rejected(
                event,
                str(exc),
            )



    # ==========================================================
    # Order submission
    # ==========================================================

    async def submit_market_order(
        self,
        request,
        side: str,
    ):

        await self.submit_order(
            request,
            side,
            order_type="MARKET",
        )



    async def submit_limit_order(
        self,
        request,
        side: str,
    ):

        await self.submit_order(
            request,
            side,
            order_type="LIMIT",
        )



    async def submit_order(
        self,
        request,
    ):

        #
        # Validate symbol
        #

        symbol = (
            request.symbol.upper()
        )


        if not symbol:

            raise ValueError(
                "Missing symbol"
            )



        #
        # Publish submitted event
        #

        await self.bus.publish_system(
            SystemEvent(
                name="ORDER_SUBMITTED",
                payload=request,
            )
        )



        #
        # Broker order payload
        #

        order_payload = ( request.to_broker_dict())

        if (
            request.order_type == "LIMIT"
            and request.price
        ):

            order_payload[
                "price"
            ] = request.price



        #
        # Schwab API boundary
        #

        response = await (
            self.place_order(
                order_payload
            )
        )



        await self.bus.publish_system(
            SystemEvent(
                name="ORDER_ACCEPTED",
                payload=response,
            )
        )



    async def place_order(
        self,
        payload: dict,
    ):

        """
        Schwab API boundary.

        Adjust here to match
        schwab-py client version.
        """

        #
        # Typical schwab-py:
        #
        # response = await client.place_order(...)
        #

        response = (
            self.client.place_order(
                payload
            )
        )


        return response



    # ==========================================================
    # Cancellation
    # ==========================================================

    async def cancel_order(
        self,
        payload,
    ):

        order_id = payload


        try:

            response = (
                self.client.cancel_order(
                    order_id
                )
            )


            await self.bus.publish_system(
                SystemEvent(
                    name="ORDER_CANCELLED",
                    payload=response,
                )
            )


        except Exception as exc:

            await self.bus.publish_system(
                SystemEvent(
                    name="ORDER_REJECTED",
                    payload=str(exc),
                )
            )



    # ==========================================================
    # Position commands
    # ==========================================================

    async def flatten_position(
        self,
        payload,
    ):

        symbol = (
            payload.symbol
        )


        position = (
            self.state_engine.get_position(
                symbol
            )
        )


        if not position:

            await self.bus.publish_system(
                SystemEvent(
                    name="FLATTEN_REJECTED",
                    payload=
                    "No position",
                )
            )

            return



        side = (
            "SELL"
            if position.quantity > 0
            else "BUY"
        )


        request = {

            "symbol":
                symbol,

            "quantity":
                abs(
                    position.quantity
                ),

        }


        await self.submit_market_order(
            request,
            side,
        )



    async def panic(
        self,
    ):

        await self.bus.publish_system(
            SystemEvent(
                name="PANIC_REQUESTED"
            )
        )



    # ==========================================================
    # Error reporting
    # ==========================================================

    async def publish_rejected(
        self,
        command,
        reason,
    ):

        await self.bus.publish_system(
            SystemEvent(
                name="ORDER_REJECTED",
                payload={
                    "command": command,
                    "reason": reason,
                },
            )
        )



    # ==========================================================
    # Shutdown
    # ==========================================================

    def stop(
        self,
    ):

        self.running = False