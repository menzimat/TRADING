"""
schwab_streamer.py

Schwab websocket market data adapter.

Responsibilities:

    - Maintain Schwab websocket connection
    - Subscribe to Level One equity quotes
    - Normalize quote messages
    - Publish MarketEvents

Does NOT:

    - Update GUI
    - Maintain application state
    - Execute orders
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import json
from pathlib import Path
from trading_app.models.broker_account import BrokerAccount
from schwab.streaming import StreamClient


from trading_app.bus import (
    EventBus,
    MarketEvent,
    EventType,
    SystemEvent,
)


logger = logging.getLogger(__name__)



class SchwabStreamer:


    def __init__(
        self,
        client,
        bus: EventBus,
        state_engine=None,
    ):

        self.client = client

        self.bus = bus

        self.state_engine = state_engine

        self.running = False

        self.stream_client = None

        self.account_hash = None
        self.account_hashes = []

        self.symbols = self.load_symbols()
        self._subscribed_symbols = set()
        self._subscription_lock = asyncio.Lock()
        self._subscriptions_ready = False



    # ======================================================
    # Watchlist
    # ======================================================

    def load_symbols(self):

        path = Path(
            "cfg/tickers.txt"
        )


        if not path.exists():

            logger.warning(
                "No ticker file found"
            )

            return []


        return [

            line.strip().upper()

            for line in path.read_text().splitlines()

            if line.strip()

        ]

    def has_symbol(self, symbol: str) -> bool:
        """Return whether a symbol is already on the streamer watchlist."""

        return symbol.strip().upper() in self.symbols

    async def add_symbol(self, symbol: str) -> bool:
        """Add one symbol to the watchlist and subscribe it when connected."""

        symbol = symbol.strip().upper()

        if not symbol or symbol == "-" or self.has_symbol(symbol):
            return False

        self.symbols.append(symbol)

        if self._subscriptions_ready:
            await self._subscribe_symbols([symbol], add=True)

        return True

    async def remove_symbol(self, symbol: str) -> bool:
        """Remove one symbol from the watchlist and unsubscribe when live."""

        symbol = symbol.strip().upper()

        if not symbol or symbol not in self.symbols:
            return False

        self.symbols.remove(symbol)

        if self._subscriptions_ready:
            async with self._subscription_lock:
                await self.stream_client.level_one_equity_unsubs([symbol])
                self._subscribed_symbols.discard(symbol)
                logger.info("Unsubscribed: %s", symbol)

        return True

    async def _subscribe_symbols(self, symbols, *, add=False):
        """Subscribe only symbols not yet sent on this websocket connection.

        ``SUBS`` establishes the initial subscription set. Subsequent symbols
        must use Schwab's ``ADD`` command so existing quote subscriptions stay
        active.
        """

        async with self._subscription_lock:
            pending = [
                symbol for symbol in symbols
                if symbol not in self._subscribed_symbols
            ]

            if not pending:
                return

            if add:
                await self.stream_client.level_one_equity_add(pending)
            else:
                await self.stream_client.level_one_equity_subs(pending)
            self._subscribed_symbols.update(pending)
            logger.info("Subscribed: %s", pending)



    # ======================================================
    # Runtime entry point
    # ======================================================

    async def run(self):

        if self.running:

            return


        self.running = True


        try:

            await self.connect()


            while self.running:

                await (
                    self.stream_client
                    .handle_message()
                )


        except asyncio.CancelledError:

            pass


        except Exception:

            logger.exception(
                "Schwab streamer failed"
            )


            await self.bus.publish_system(
                SystemEvent(
                    name="STREAM_ERROR"
                )
            )


        finally:

            await self.disconnect()



    # ======================================================
    # Connect websocket
    # ======================================================

    async def connect(self):

        logger.info(
            "Creating Schwab StreamClient"
        )


        accounts = await (
            self.client
            .get_account_numbers()
        )


        account_data = (
            accounts.json()
        )


        if not account_data:

            raise RuntimeError(
                "No Schwab accounts returned"
            )

        broker_accounts = []

        for acct in accounts.json():

            number = acct["accountNumber"]

            broker_accounts.append(
                BrokerAccount(
                    display_name=f"Acct {number[-4:]}",
                    account_number=number,
                    account_hash=acct["hashValue"],
                )
            )
        
        
        account_hash = (
            account_data[0]["hashValue"]
        )

        self.account_hash = account_hash
        self.account_hashes = [acct["hashValue"] for acct in account_data]


        logger.info(
            f"Using account hash {account_hash}"
        )
        print(f"ACCOUNT DATA:", account_data)


        self.stream_client = StreamClient(
            self.client,
            account_id=account_hash,
        )


        self.stream_client.add_level_one_equity_handler(
            self.handle_quote
        )
        self.stream_client.add_account_activity_handler(
            self.handle_account_activity
        )

        await self.stream_client.login()

        await self.stream_client.account_activity_sub()

        self._subscribed_symbols.clear()
        self._subscriptions_ready = False


        logger.info(
            "Schwab websocket connected"
        )


        await self.refresh_positions()

        if self.symbols:
            await self._subscribe_symbols(self.symbols)
        self._subscriptions_ready = True
        try:
            print("Publishing accounts:", broker_accounts)
            await self.bus.publish_system(
                SystemEvent(
                    name="ACCOUNTS_LOADED",
                    payload=broker_accounts,
                )
            )
            print("Accounts event published")
        except Exception:
            logger.exception("Failed publishing ACCOUNTS_LOADED")


        await self.bus.publish_system(
            SystemEvent(
                name="CONNECTED"
            )
        )


    # ======================================================
    # Quote callback
    # ======================================================

    async def handle_quote(
        self,
        message,
    ):
        print(message)
        for record in message["content"]:
            quote = self.parse_quote(record)
            if quote is None:
                continue

            print("STREAMER:", quote)
            await self.bus.publish_market(
                MarketEvent(
                    event=EventType.QUOTES,
                    payload=quote,
                )
            )

    async def handle_account_activity(self, message):
        payload = message.get("content") if isinstance(message, dict) else None
        if not payload:
            return

        await self.refresh_positions()

        await self.bus.publish_system(
            SystemEvent(
                name="POSITION_REFRESH_REQUESTED",
                payload=payload,
            )
        )

    async def refresh_positions(self, account_hash=None):
        if self.state_engine is None or self.client is None:
            return

        account_hashes = [account_hash] if account_hash else self.account_hashes
        if not account_hashes and self.account_hash:
            account_hashes = [self.account_hash]

        for account_hash in account_hashes:
            await self._refresh_account_positions(account_hash)

    async def _refresh_account_positions(self, account_hash):
        try:
            fields = None
            if hasattr(self.client, "Account") and hasattr(self.client.Account, "Fields"):
                fields = [self.client.Account.Fields.POSITIONS]

            if fields is None:
                response = self.client.get_account(account_hash)
            else:
                response = self.client.get_account(account_hash, fields=fields)

            logger.info(
                "ACCOUNT RESPONSE\n%s",
                json.dumps(response, indent=2, default=str),
            )

            if inspect.isawaitable(response):
                response = await response

            account_payload = self._coerce_payload(response)

            logger.info(
                "Account payload keys: %s",
                list(account_payload.keys()) if isinstance(account_payload, dict) else type(account_payload),
            )

            logger.info(
                "ACCOUNT PAYLOAD\n%s",
                json.dumps(account_payload, indent=2, default=str),
            )
            positions = self._extract_positions(account_payload)
            logger.info(
                "Extracted %d raw positions",
                len(positions),
            )

            normalized_positions = []
            for position in positions:
                normalized = self._normalize_position(position)
                logger.info(
                    "Normalized: %s",
                    normalized,
                )
                if normalized is None:
                    continue
                normalized_positions.append(normalized)

            await self.bus.publish_market(
                MarketEvent(
                    event=EventType.POSITION_SNAPSHOT,
                    payload={
                        "account_hash": account_hash,
                        "positions": normalized_positions,
                    },
                )
            )
        except Exception:
            logger.exception(
                "Failed refreshing positions from Schwab account %s",
                account_hash,
            )

    def _coerce_payload(self, response):
        if response is None:
            return None

        if hasattr(response, "json"):
            try:
                return response.json()
            except Exception:
                return None

        return response

    def _extract_positions(self, payload):
        """
        Locate the first 'positions' list anywhere in the Schwab account payload.
        """

        if isinstance(payload, list):
            for item in payload:
                positions = self._extract_positions(item)
                if positions:
                    return positions
            return []

        if not isinstance(payload, dict):
            return []

        positions = payload.get("positions")
        if isinstance(positions, list):
            return positions

        for value in payload.values():
            if isinstance(value, (dict, list)):
                positions = self._extract_positions(value)
                if positions:
                    return positions

        return []

    def old_extract_positions(self, payload):
        if not isinstance(payload, dict):
            return []

        if isinstance(payload.get("positions"), list):
            return payload["positions"]

        for key in ("securitiesAccount", "account"):
            nested = payload.get(key)
            if isinstance(nested, dict):
                positions = nested.get("positions")
                if isinstance(positions, list):
                    return positions

        return []

    def _normalize_position(self, position):
        if not isinstance(position, dict):
            return None

        instrument = position.get("instrument") or {}
        symbol = (
            position.get("symbol")
            or instrument.get("symbol")
            or position.get("underlyingSymbol")
        )

        if not symbol:
            return None

        quantity = position.get("quantity")
        if quantity is None:
            quantity = position.get("longQuantity")
        if quantity is None:
            quantity = position.get("shortQuantity")
        if quantity is None:
            quantity = 0

        try:
            quantity = int(float(quantity))
        except (TypeError, ValueError):
            quantity = 0

        if position.get("positionType") == "SHORT" and quantity > 0:
            quantity = -quantity

        average_price = (
            position.get("averagePrice")
            or position.get("average_price")
            or position.get("costBasis")
        )

        try:
            average_price = float(average_price)
        except (TypeError, ValueError):
            average_price = 0.0

        return {
            "symbol": str(symbol).upper(),
            "quantity": quantity,
            "average_price": average_price,
        }

    # ======================================================
    # Schwab -> internal format
    # ======================================================

    def parse_quote(self,message,):

        try:

            quote = {"symbol": message["key"],}

            field_map = {
                "BID_PRICE": "bid",
                "ASK_PRICE": "ask",
                "LAST_PRICE": "last",
                "TOTAL_VOLUME": "volume",
            }

            for schwab_name, internal_name in field_map.items():

                if schwab_name in message:
                    quote[internal_name] = message[schwab_name]

            return quote

        except Exception:

            logger.exception(
                "Quote parse failure"
            )

            return None



    # ======================================================
    # Shutdown
    # ======================================================

    async def disconnect(self):

        logger.info(
            "Disconnecting Schwab streamer"
        )


        if self.stream_client:

            try:

                await (
                    self.stream_client
                    .logout()
                )

            except Exception:

                pass


        await self.bus.publish_system(
            SystemEvent(
                name="DISCONNECTED"
            )
        )


        self.stream_client = None
        self._subscriptions_ready = False
        self._subscribed_symbols.clear()



    def stop(self):

        self.running = False
