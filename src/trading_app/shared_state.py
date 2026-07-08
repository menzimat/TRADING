"""
shared_state.py

Shared application state.

This object is owned by TradingApplication.

Every subsystem receives a reference to it.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


@dataclass
class QuoteBook:

    quotes: dict = field(default_factory=dict)

    positions: dict = field(default_factory=dict)

    orders: dict = field(default_factory=dict)

    account: dict = field(default_factory=dict)

    watchlist: list = field(default_factory=list)


class TradeState:

    def __init__(self):

        self.data = QuoteBook()

        self.lock = asyncio.Lock()

        self.subscribers = set()

    #
    # ---------------------------------------------------------
    #

    async def update_quotes(

        self,

        updates

    ):

        async with self.lock:

            self.data.quotes.update(

                updates

            )

        await self.broadcast()

    #
    # ---------------------------------------------------------
    #

    async def broadcast(self):

        dead = []

        for q in self.subscribers:

            try:

                await q.put(

                    self.data.quotes

                )

            except Exception:

                dead.append(q)

        for q in dead:

            self.subscribers.remove(q)

    #
    # ---------------------------------------------------------
    #

    def subscribe(

        self,

        queue

    ):

        self.subscribers.add(queue)

    def unsubscribe(

        self,

        queue

    ):

        self.subscribers.discard(queue)

    #
    # ---------------------------------------------------------
    #

    def set_watchlist(

        self,

        symbols

    ):

        self.data.watchlist = list(symbols)

    @property
    def watchlist(self):

        return self.data.watchlist