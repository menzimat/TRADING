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
import logging
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
    ):

        self.client = client

        self.bus = bus

        self.running = False

        self.stream_client = None

        self.symbols = self.load_symbols()



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


        await self.stream_client.login()


        logger.info(
            "Schwab websocket connected"
        )


        if self.symbols:

            await (
                self.stream_client
                .level_one_equity_subs(
                    self.symbols
                )
            )


            logger.info(
                "Subscribed: %s",
                self.symbols
            )
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



    def stop(self):

        self.running = False