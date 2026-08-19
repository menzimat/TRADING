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
from contextlib import suppress
from trading_app.models.broker_account import BrokerAccount
from schwab.streaming import StreamClient


from trading_app.bus import (
    EventBus,
    MarketEvent,
    EventType,
    SystemEvent,
)
from trading_app.services.trade_sound import TradeSoundService

logger = logging.getLogger(__name__)



class SchwabStreamer:


    def __init__(
        self,
        client,
        bus: EventBus,
        state_engine=None,
        trade_sound: TradeSoundService | None = None,
    ):

        self.client = client

        self.bus = bus

        self.state_engine = state_engine

        self.trade_sound = trade_sound

        self.running = False
        self._connected = False

        self.stream_client = None

        self.account_hash = None
        self.account_hashes = []

        self.symbols = self.load_symbols()
        self.symbol_set = set(self.symbols)

        self._subscribed_symbols = set()
        self._subscription_lock = asyncio.Lock()
        self._subscriptions_ready = False

        # Scanner file symbols that are already in the main watchlist are
        # deliberately omitted.  The two lists share one quote subscription
        # set, and scanner_tickers.txt is persisted as the supplemental list.
        self.scanner_symbols = [
            symbol for symbol in self.load_scanner_symbols()
            if symbol not in self.symbol_set
        ]
        self.scanner_symbol_set = set(self.scanner_symbols)

        for symbol in self.scanner_symbols:
            self.state_engine.scanner_state.add_watch_symbol(symbol)

        self.movers_task = None

        momentum = getattr(self.state_engine.config, "momentum", None)

#        if momentum:
#           print(f"momentum: {momentum}")

        if momentum["enabled"]:
            self.use_schwab_movers = (
                momentum["use_schwab_movers"]
                if momentum
                else False
            )

            self.movers_poll_interval = (
                momentum["movers_poll_interval"]
                if momentum
                else 6
            )

            self.movers_frequency = (
                momentum["movers_frequency"]
                if momentum
                else 5
            )

            self.max_movers = (
                momentum["max_movers"]
                if momentum
                else 10
            )

            self.merge_scanner_file = (
                momentum["merge_scanner_file"]
                if momentum
                else True
            )

            self.min_mover_price = (
                momentum["min_mover_price"]
                if momentum
                else 0.7
            )

            self.max_mover_price = (
                momentum["max_mover_price"]
                if momentum
                else 20.0
            )

            self.min_volume = (
                momentum["min_volume"]
                if momentum
                else 5000000
            )


            self.base_scanner_symbols = set(self.scanner_symbols)


    # ======================================================
    # Watchlist
    # ======================================================

    def load_symbols(self):
        return self.load_symbol_file("tickers.txt")

    def load_scanner_symbols(self):
        return self.load_symbol_file("scanner_tickers.txt")

    def load_symbol_file(self, filename: str) -> list[str]:

        path = Path("cfg") / filename

        if not path.exists():
            logger.warning("%s not found", path)
            return []

        return [
            line.strip().upper()
            for line in path.read_text().splitlines()
            if line.strip()
        ]

    @staticmethod
    def _unique_symbols(symbols) -> list[str]:
        """Normalize symbols while retaining their order."""

        seen = set()
        normalized = []
        for symbol in symbols:
            symbol = symbol.strip().upper()
            if symbol and symbol not in seen:
                seen.add(symbol)
                normalized.append(symbol)
        return normalized

    def all_symbols(self) -> list[str]:
        """Return the complete displayed/subscribed symbol set in order."""

        return self._unique_symbols(self.symbols + self.scanner_symbols)

    def save_scanner_symbols(self, symbols) -> list[str]:
        """Persist supplemental QuoteTable symbols without duplicating tickers.

        ``tickers.txt`` remains the primary watchlist.  Every displayed symbol
        not already present there is written to ``scanner_tickers.txt``.
        """

        primary_symbols = set(self.load_symbols())
        scanner_symbols = [
            symbol for symbol in self._unique_symbols(symbols)
            if symbol not in primary_symbols
        ]
        path = Path("cfg") / "scanner_tickers.txt"
        contents = "\n".join(scanner_symbols)
        path.write_text(f"{contents}\n" if contents else "")
        return scanner_symbols

    async def reload_symbol_files(self, position_symbols=()) -> list[str]:
        """Replace the live watchlist with ticker files and open positions.

        Open positions are always retained in the market-data subscription set
        so their QuoteTable rows remain actionable after a reload.
        """

        primary_symbols = self._unique_symbols(
            self.load_symbols() + list(position_symbols)
        )
        primary_set = set(primary_symbols)
        scanner_symbols = [
            symbol for symbol in self._unique_symbols(self.load_scanner_symbols())
            if symbol not in primary_set
        ]
        desired_symbols = primary_symbols + scanner_symbols
        desired_set = set(desired_symbols)

        if self._subscriptions_ready:
            async with self._subscription_lock:
                removed = self._subscribed_symbols - desired_set
                if removed:
                    await self.stream_client.level_one_equity_unsubs(sorted(removed))
                added = desired_set - self._subscribed_symbols
                if added:
                    await self.stream_client.level_one_equity_add(sorted(added))
                self._subscribed_symbols = desired_set

        self.symbols = primary_symbols
        self.symbol_set = primary_set
        self.scanner_symbols = scanner_symbols
        self.scanner_symbol_set = set(scanner_symbols)
        self.base_scanner_symbols = set(scanner_symbols)
        self.state_engine.scanner_state.set_watch_symbols(self.scanner_symbol_set)
        return desired_symbols

    def has_symbol(self, symbol: str) -> bool:
        """Return whether a symbol is already on the streamer watchlist."""

        return symbol.strip().upper() in self.symbols

    async def add_scanner_symbol(self, symbol: str):

        symbol = symbol.upper().strip()

        logger.debug(
            "SCANNER ADD: %s  count=%d",
            symbol,
            len(self.scanner_symbols),
        )

        if symbol in self.scanner_symbol_set:
            return False

        self.scanner_symbol_set.add(symbol)
        self.scanner_symbols.append(symbol)
        self.state_engine.scanner_state.add_candidate(symbol)

        if self._subscriptions_ready:
            await self._subscribe_symbols([symbol], add=True)

        return True

    async def add_symbol(self, symbol: str) -> bool:
        """Add one symbol to the watchlist and subscribe it when connected."""

        logger.info(
            "QUOTE ADD: %s  count=%d",
            symbol,
            len(self.symbols),
        )
        symbol = symbol.strip().upper()

        if not symbol or symbol == "-" or self.has_symbol(symbol):
            return False
        self.symbol_set.add(symbol)
        self.symbols.append(symbol)

        if self._subscriptions_ready:
            await self._subscribe_symbols([symbol], add=True)

        return True

    async def remove_scanner_symbol(self, symbol: str) -> bool:
            """Remove one symbol from the scanner list and unsubscribe when live."""

            symbol = symbol.strip().upper()

            if not symbol or symbol not in self.scanner_symbols:
                return False
            
            self.scanner_symbol_set.remove(symbol)
            self.scanner_symbols.remove(symbol)
            self.state_engine.scanner_state.remove_candidate(symbol)

            if self._subscriptions_ready:
                async with self._subscription_lock:
                    await self.stream_client.level_one_equity_unsubs([symbol])
                    self._subscribed_symbols.discard(symbol)
                    logger.info("Unsubscribed: %s", symbol)

            return True


    async def remove_symbol(self, symbol: str) -> bool:
        """Remove one symbol from the watchlist and unsubscribe when live."""

        symbol = symbol.strip().upper()

        if not symbol or symbol not in self.symbols:
            return False

        self.symbol_set.remove(symbol)
        self.symbols.remove(symbol)

        if self._subscriptions_ready:
            async with self._subscription_lock:
                await self.stream_client.level_one_equity_unsubs([symbol])
                self._subscribed_symbols.discard(symbol)
                logger.debug("Unsubscribed: %s", symbol)

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
            logger.debug("Subscribed: %s", pending)


    def _frequency_enum(self):

        freq = self.client.Movers.Frequency

        mapping = {
            0: freq.ZERO,
            1: freq.ONE,
            5: freq.FIVE,
            10: freq.TEN,
            30: freq.THIRTY,
            60: freq.SIXTY,
        }

        return mapping.get(
            self.movers_frequency,
            freq.FIVE,
        )


    async def get_equity_movers(self):

        response = await self.client.get_movers(
            self.client.Movers.Index.EQUITY_ALL,
            sort_order=self.client.Movers.SortOrder.PERCENT_CHANGE_UP,
            frequency=self._frequency_enum(),)

        response.raise_for_status()
        payload = response.json()
        symbols = []

        logger.debug("MOVERS PAYLOAD TYPE: %s", type(payload))
        logger.debug("MOVERS PAYLOAD: %s", json.dumps(payload, indent=2))

        if isinstance(payload, list):
            movers = payload
        elif isinstance(payload, dict):
            movers = None

            for value in payload.values():
                if (isinstance(value, list) and value and isinstance(value[0], dict)):
                    movers = value
                    break
            if movers is None:
                movers = []
        else:
            movers = []

        for item in movers:
            symbol = item.get("symbol")
            if symbol:
                price = item.get("lastPrice")

                if price is None:
                    continue

                if price < self.min_mover_price:
                    continue

                if self.max_mover_price is not None and price > self.max_mover_price:
                    continue
                symbols.append(symbol.upper())

        return symbols[: self.max_movers]


    async def update_mover_symbols(self, movers):

        desired = set(movers)

        logger.debug(
            "Mover update: %s",
            sorted(desired),
        )

        if self.merge_scanner_file:
            desired |= self.base_scanner_symbols
            self.state_engine.scanner_state.set_watch_symbols(desired)

        current = set(self.scanner_symbols)

        for symbol in desired - current:
            await self.add_scanner_symbol(symbol)
            self.state_engine.scanner_state.add_watch_symbol(symbol)
            

        #
        # Do NOT remove symbols for now. Let the list grow.
        #
        for symbol in current - desired:
            if symbol not in self.base_scanner_symbols:
                await self.remove_scanner_symbol(symbol)
                self.state_engine.scanner_state.remove_watch_symbol(symbol)


    async def movers_poll_loop(self):

        logger.debug(
            "Schwab movers polling every %d seconds",
            self.movers_poll_interval,
        )

        while self.running:
            try:
                movers = await self.get_equity_movers()
                await self.update_mover_symbols(movers)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "Unable to refresh Schwab movers"
                )
            await asyncio.sleep(
                self.movers_poll_interval
            )


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

        logger.debug("Creating Schwab StreamClient")

        accounts = await (self.client.get_account_numbers())

        account_data = (accounts.json())

        if not account_data:
            raise RuntimeError("No Schwab accounts returned")

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
        
        account_hash = (account_data[0]["hashValue"])

        self.account_hash = account_hash
        self.account_hashes = [acct["hashValue"] for acct in account_data]

        logger.debug(f"Using account hash {account_hash}")
        logger.debug(f"ACCOUNT DATA:", account_data)

        self.stream_client = StreamClient(self.client, account_id=account_hash,)

        self.stream_client.add_level_one_equity_handler(self.handle_quote)
        self.stream_client.add_account_activity_handler(self.handle_account_activity)

        try:
            await self.stream_client.login()
        except Exception as e:
            logger.exception(f"LOGIN Exception:", e)
            raise
        
        await self.stream_client.account_activity_sub()

        self._connected = True

        self._subscribed_symbols.clear()
        self._subscriptions_ready = False
        logger.debug("Schwab websocket connected")

        await self.refresh_positions()

        subscription_symbols = sorted(self.symbol_set | self.scanner_symbol_set)

        if subscription_symbols:
            await self._subscribe_symbols(subscription_symbols)

        self._subscriptions_ready = True

        if (self.use_schwab_movers and self.movers_task is None):
                    self.movers_task = asyncio.create_task(self.movers_poll_loop())

        try:
            logger.debug("Publishing ACCOUNTS_LOADED:", broker_accounts)
            await self.bus.publish_system(
                SystemEvent(
                    name="ACCOUNTS_LOADED",
                    payload=broker_accounts,
                )
            )
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
        logger.debug(message)
        for record in message["content"]:
            quote = self.parse_quote(record)
            if quote is None:
                continue

            logger.debug("STREAMER:", quote)
            await self.bus.publish_market(
                MarketEvent(
                    event=EventType.QUOTES,
                    payload=quote,
                )
            )

    async def handle_account_activity(self, message):
        """
        Process Schwab Account Activity messages.

        POSITION_REFRESH_REQUESTED continues to be published for every
        account-activity message, preserving the existing application
        behavior.

        Trade sounds are generated only for a confirmed
        OrderFillCompleted event.  ORDER_ACCEPTED and other intermediate
        order states do not produce sounds.
        """


        logger.info(
            "ACCOUNT ACTIVITY RECEIVED: %r",
            message,
        )
        payload = (
            message.get("content")
            if isinstance(message, dict)
            else None
        )

        if not payload:
            return

        self._process_trade_fill_sounds(payload)

        await self.refresh_positions()

        await self.bus.publish_system(
            SystemEvent(
                name="POSITION_REFRESH_REQUESTED",
                payload=payload,
            )
        )

    # ======================================================
    # Trade fill notifications
    # ======================================================

    @staticmethod
    def _parse_schwab_number(value):
        """
        Decode Schwab's {lo, signScale} numeric representation.

        Schwab uses signScale for both decimal precision and sign.
        This helper is primarily useful for diagnostic payloads;
        sound selection itself does not depend on quantity/price.
        """

        if value is None:
            return None

        if isinstance(value, (int, float)):
            return float(value)

        if not isinstance(value, dict):
            return None

        lo = value.get("lo")

        if lo is None:
            return None

        try:
            lo = int(lo)
        except (TypeError, ValueError):
            return None

        try:
            sign_scale = int(
                value.get("signScale", 0)
            )
        except (TypeError, ValueError):
            sign_scale = 0

        decimals = sign_scale // 2

        result = lo / (10 ** decimals)

        # Schwab's signScale convention uses an odd signScale
        # to represent a negative value.
        if sign_scale % 2:
            result = -result

        return result

    @staticmethod
    def _parse_trade_fill_record(record):
        """
        Convert one Schwab Account Activity record into a normalized
        trade-fill dictionary.

        Returns None for all non-fill events.

        Supports both the current Schwab Account Activity representation:

            {
                "MESSAGE_TYPE": "OrderFillCompleted",
                "MESSAGE_DATA": "{...}"
            }

        and the older/internal representation:

            {
                "2": "OrderFillCompleted",
                "3": "{...}"
            }
        """

        if not isinstance(record, dict):
            return None

        # Schwab Account Activity normally supplies these fields.
        event_type = (
            record.get("MESSAGE_TYPE")
            or record.get("2")
        )

        if event_type != "OrderFillCompleted":
            return None

        raw_data = (
            record.get("MESSAGE_DATA")
            if "MESSAGE_DATA" in record
            else record.get("3")
        )

        if isinstance(raw_data, str):
            try:
                event_data = json.loads(raw_data)
            except (TypeError, ValueError, json.JSONDecodeError):
                logger.warning(
                    "Unable to decode OrderFillCompleted payload"
                )
                return None

        elif isinstance(raw_data, dict):
            event_data = raw_data

        else:
            return None

        if not isinstance(event_data, dict):
            return None

        base_event = event_data.get("BaseEvent") or {}

        fill_event = (
            base_event.get(
                "OrderFillCompletedEventOrderLegQuantityInfo"
            )
            or {}
        )

        order_info = (
            fill_event.get(
                "OrderInfoForTransactionPosting"
            )
            or {}
        )

        execution_info = (
            fill_event.get("ExecutionInfo")
            or {}
        )

        # Schwab sends values such as "Buy", "Sell", "BuyToCover",
        # etc.  Normalize them before determining the trade direction.
        buy_sell_code = str(
            order_info.get("BuySellCode", "")
        ).strip().lower()

        if buy_sell_code in {
            "buy",
            "buytocover",
            "buy_to_cover",
        }:
            side = "BUY"

        elif buy_sell_code in {
            "sell",
            "sellshort",
            "sell_short",
        }:
            side = "SELL"

        else:
            logger.debug(
                "Ignoring OrderFillCompleted with "
                "unsupported BuySellCode=%r",
                buy_sell_code,
            )
            return None

        symbol = (
            order_info.get("Symbol")
            or event_data.get("Symbol")
        )

        order_id = (
            event_data.get("SchwabOrderID")
            or event_data.get("SchwabOrderId")
            or order_info.get("SchwabOrderID")
            or order_info.get("SchwabOrderId")
        )

        # The live Schwab message uses ExecutionID.  Preserve the
        # alternate spellings used by other payload variants.
        execution_id = (
            execution_info.get("ExecutionID")
            or execution_info.get("ExecutionId")
            or execution_info.get("executionID")
            or execution_info.get("executionId")
            or fill_event.get("QuantityInfo", {}).get(
                "ExecutionID"
            )
            or fill_event.get("QuantityInfo", {}).get(
                "ExecutionId"
            )
            or order_id
        )

        execution_quantity = (
            SchwabStreamer._parse_schwab_number(
                execution_info.get("ExecutionQuantity")
            )
        )

        execution_price = (
            SchwabStreamer._parse_schwab_number(
                execution_info.get("ExecutionPrice")
            )
        )

        execution_timestamp = (
            execution_info
            .get("ExecutionTimeStamp", {})
            .get("DateTimeString")
        )

        return {
            "side": side,
            "symbol": (
                str(symbol).upper()
                if symbol
                else None
            ),
            "order_id": order_id,
            "execution_id": execution_id,
            "quantity": execution_quantity,
            "price": execution_price,
            "execution_timestamp": execution_timestamp,
        }

    @staticmethod
    def _old_parse_trade_fill_record(record):
        """
        Convert one Schwab Account Activity record into a normalized
        trade-fill dictionary.

        Returns None for all non-fill events.
        """

        if not isinstance(record, dict):
            return None

        event_type = record.get("2")

        if event_type != "OrderFillCompleted":
            return None

        raw_data = record.get("3")

        if isinstance(raw_data, str):
            try:
                event_data = json.loads(raw_data)
            except (TypeError, ValueError, json.JSONDecodeError):
                logger.warning(
                    "Unable to decode OrderFillCompleted payload"
                )
                return None

        elif isinstance(raw_data, dict):
            event_data = raw_data

        else:
            return None

        if not isinstance(event_data, dict):
            return None

        base_event = event_data.get("BaseEvent") or {}

        fill_event = (
            base_event.get(
                "OrderFillCompletedEventOrderLegQuantityInfo"
            )
            or {}
        )

        order_info = (
            fill_event.get(
                "OrderInfoForTransactionPosting"
            )
            or {}
        )

        execution_info = (
            fill_event.get("ExecutionInfo")
            or {}
        )

        buy_sell_code = str(
            order_info.get("BuySellCode", "")
        ).strip().lower()

        if buy_sell_code in {
            "buy",
            "buytocover",
            "buy_to_cover",
        }:
            side = "BUY"

        elif buy_sell_code in {
            "sell",
            "sellshort",
            "sell_short",
        }:
            side = "SELL"

        else:
            logger.debug(
                "Ignoring OrderFillCompleted with "
                "unsupported BuySellCode=%r",
                buy_sell_code,
            )
            return None

        symbol = (
            order_info.get("Symbol")
            or event_data.get("Symbol")
        )

        order_id = event_data.get(
            "SchwabOrderID"
        )

        execution_id = (
            execution_info.get("ExecutionId")
            or execution_info.get("ExecutionID")
            or fill_event.get("QuantityInfo", {}).get(
                "ExecutionID"
            )
            or order_id
        )

        execution_quantity = (
            SchwabStreamer._parse_schwab_number(
                execution_info.get("ExecutionQuantity")
            )
        )

        execution_price = (
            SchwabStreamer._parse_schwab_number(
                execution_info.get("ExecutionPrice")
            )
        )

        return {
            "side": side,
            "symbol": (
                str(symbol).upper()
                if symbol
                else None
            ),
            "order_id": order_id,
            "execution_id": execution_id,
            "quantity": execution_quantity,
            "price": execution_price,
            "execution_timestamp": (
                execution_info
                .get("ExecutionTimeStamp", {})
                .get("DateTimeString")
            ),
        }

    def _process_trade_fill_sounds(self, payload) -> None:
        """
        Generate one sound for each confirmed OrderFillCompleted
        Account Activity record.

        Duplicate execution IDs are suppressed so reconnect/replay
        behavior cannot produce duplicate sounds.
        """

        if self.trade_sound is None:
            return

        if not isinstance(payload, list):
            payload = [payload]

        for record in payload:

            fill = self._parse_trade_fill_record(
                record
            )

            if fill is None:
                continue

            execution_id = fill.get(
                "execution_id"
            )

            if execution_id:
                if not hasattr(
                    self,
                    "_played_execution_ids",
                ):
                    self._played_execution_ids = set()

                if execution_id in (
                    self._played_execution_ids
                ):
                    logger.debug(
                        "Ignoring duplicate fill sound "
                        "for execution %s",
                        execution_id,
                    )
                    continue

                self._played_execution_ids.add(
                    execution_id
                )

                # Prevent unbounded growth during a long-running
                # trading session.
                if len(
                    self._played_execution_ids
                ) > 1000:
                    self._played_execution_ids = set(
                        list(
                            self._played_execution_ids
                        )[-500:]
                    )

            logger.info(
                "TRADE FILL: %s %s qty=%s price=%s "
                "order=%s execution=%s",
                fill["side"],
                fill["symbol"],
                fill["quantity"],
                fill["price"],
                fill["order_id"],
                fill["execution_id"],
            )

            try:
                if fill["side"] == "BUY":
                    self.trade_sound.play_buy()
                elif fill["side"] == "SELL":
                    self.trade_sound.play_sell()

            except Exception:
                # Audio must never interfere with trading.
                logger.exception(
                    "Trade sound playback request failed"
                )



    async def old_handle_account_activity(self, message):
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
            return {}

        account_hashes = [account_hash] if account_hash else self.account_hashes
        if not account_hashes and self.account_hash:
            account_hashes = [self.account_hash]

        snapshots = {}
        for account_hash in account_hashes:
            positions = await self._refresh_account_positions(
                account_hash
            )
            if positions is not None:
                snapshots[account_hash] = positions
        return snapshots

    async def _refresh_account_positions(self, account_hash):
        try:
            #TODO: CUSTOMIZE QUERY FIELDS HERE using input parameter
            fields = None
            if hasattr(self.client, "Account") and hasattr(self.client.Account, "Fields"):
                fields = [self.client.Account.Fields.POSITIONS]

            if fields is None:
                response = self.client.get_account(account_hash)
            else:
                response = self.client.get_account(account_hash, fields=fields)

            logger.debug(
                "ACCOUNT RESPONSE\n%s",
                json.dumps(response, indent=2, default=str),
            )

            if inspect.isawaitable(response):
                response = await response

            account_payload = self._coerce_payload(response)

            logger.debug(
                "Account payload keys: %s",
                list(account_payload.keys()) if isinstance(account_payload, dict) else type(account_payload),
            )

            logger.debug(
                "ACCOUNT PAYLOAD\n%s",
                json.dumps(account_payload, indent=2, default=str),
            )
            positions = self._extract_positions(account_payload)
            logger.debug("Extracted %d raw positions",len(positions),)

            normalized_positions = []
            for position in positions:
                normalized = self._normalize_position(position)
                logger.debug("Normalized: %s", normalized)
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
            return normalized_positions
        except Exception:
            logger.exception(
                "Failed refreshing positions from Schwab account %s",
                account_hash,
            )
            return None

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

        logger.debug("Disconnecting Schwab streamer")

        was_connected = self._connected
        self._connected = False

        if self.stream_client:
            if self.movers_task:
                self.movers_task.cancel()

                with suppress(asyncio.CancelledError):
                    await self.movers_task
                self.movers_task = None

            try:
                await (self.stream_client.logout())
            except Exception:
                pass

        if was_connected:
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
