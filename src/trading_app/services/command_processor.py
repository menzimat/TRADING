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

import inspect
import logging
from typing import Any

import pprint


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
        account_provider=None,
    ):

        self.client = client

        self.bus = bus

        self.state_engine = (
            state_engine
        )

        self.account_provider = account_provider

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
        )



    async def submit_limit_order(
        self,
        request,
        side: str,
    ):

        await self.submit_order(
            request,
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



        try:
            if request.side.name == "SELL":
                await self._enforce_sell_position_limit(request)
        except Exception as exc:
            logger.exception("Sell validation failed for %s", request.symbol)
            await self.bus.publish_system(
                SystemEvent(
                    name="ORDER_REJECTED",
                    payload={
                        "command": request.command_side,
                        "reason": str(exc),
                        "payload": request,
                    },
                )
            )
            return

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

        order_payload = request.to_schwab_order_spec()

        logger.info(
            "Submitting order payload: %s",
            order_payload,
        )



        #
        # Schwab API boundary
        #

        try:
            response = await (
                self.place_order(
                    order_payload,
                    request=request,
                )
            )
        except Exception as exc:
            logger.exception(
                "Broker order submission failed for %s",
                request.symbol,
            )
            await self.bus.publish_system(
                SystemEvent(
                    name="ORDER_REJECTED",
                    payload={
                        "command": CommandEvent(
                            command=request.command_side,
                            payload=request,
                        ),
                        "reason": str(exc),
                        "payload": order_payload,
                    },
                )
            )
            return

        logger.info(
            "Broker order response: %s",
            response,
        )

        payload = {
            "request": request,
            "response": response,
            "payload": order_payload,
        }

        await self.bus.publish_system(
            SystemEvent(
                name="ORDER_ACCEPTED",
                payload=payload,
            )
        )



    async def _enforce_sell_position_limit(self, request):
        if request.side.name != "SELL":
            return

        symbol = request.symbol.upper()
        position = self.state_engine.get_position(symbol)

        if position is None or position.quantity <= 0:
            raise ValueError(f"No long position available for {symbol}")

        requested_qty = int(request.quantity)
        available_qty = int(getattr(position, "quantity", 0))
        capped_qty = min(requested_qty, available_qty)
        if capped_qty <= 0:
            raise ValueError(f"No long position available for {symbol}")

        request.quantity = capped_qty

    async def place_order(
        self,
        payload: dict,
        request=None,
    ):

        """
        Schwab API boundary.

        The schwab-py client API varies by version. This adapter
        tries the common signatures in order and raises a clear
        error if the installed client does not support order entry.
        """

        if not self.client:
            raise RuntimeError("Schwab client is not configured.")

        place_order = getattr(
            self.client,
            "place_order",
            None,
        )

        if place_order is None:
            raise RuntimeError(
                "Installed schwab client does not expose place_order()."
            )

        account_hash = None

        if request is not None:
            account_hash = getattr(request, "account_hash", None)

        if account_hash is None and self.account_provider is not None:
            account_hash = self.account_provider()

        if account_hash is None and hasattr(self.client, "account_hash"):
            account_hash = self.client.account_hash

        if account_hash is None:
            account_hash = getattr(self.client, "accounts", None)
            if account_hash:
                try:
                    account_hash = account_hash[0].account_hash
                except Exception:
                    account_hash = None

        if account_hash is None:
            raise RuntimeError(
                "Schwab client does not expose an account_hash for order placement."
            )

        try:
            response = place_order(account_hash, payload)
            if inspect.isawaitable(response):
                response = await response

            diagnostics = self._extract_response_diagnostics(response)
            logger.error(
                "Schwab order response diagnostics: %s",
                pprint.pformat(diagnostics),
            )
            print(
                "SCHWAB ORDER RESPONSE DIAGNOSTICS",
                pprint.pformat(diagnostics),
                flush=True,
            )
            return response
        except TypeError as exc:
            raise RuntimeError(
                "Unable to submit order with installed schwab client: "
                f"{exc}"
            ) from exc

    def _extract_response_diagnostics(self, response: Any) -> dict[str, Any]:
        if response is None:
            return {
                "status_code": None,
                "headers": None,
                "body": None,
            }

        status_code = getattr(response, "status_code", None)
        headers = getattr(response, "headers", None)
        body = getattr(response, "text", None)

        if body is None:
            body = getattr(response, "content", None)

        if body is None:
            body = getattr(response, "body", None)

        if body is None and hasattr(response, "json"):
            try:
                body = response.json()
            except Exception:
                body = None

        return {
            "status_code": status_code,
            "headers": headers,
            "body": body,
        }



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