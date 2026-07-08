"""
coalescer.py

Quote batching service.

Collects high-frequency quote updates and periodically flushes
them into TradeState, reducing GUI redraws.

Application
    ↓
Runtime
    ↓
Engine
    ↓
TickCoalescer
    ↓
TradeState
    ↓
GUI
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class TickCoalescer:

    def __init__(self, app, flush_ms=None):

        self.app = app

        self.state = app.state

        self.flush_ms = (
            flush_ms
            or app.config.quote_refresh_ms
        )

        self.buffer = defaultdict(dict)

        self.lock = asyncio.Lock()

        #
        # subscriber callbacks
        #

        self.subscribers = set()

        #
        # lifecycle
        #

        self.running = False

        #
        # statistics
        #

        self.total_ticks = 0
        self.total_flushes = 0
        self.max_batch = 0

    #
    # ---------------------------------------------------------
    #

    def subscribe(self, callback):

        self.subscribers.add(callback)

    def unsubscribe(self, callback):

        self.subscribers.discard(callback)

    #
    # ---------------------------------------------------------
    #

    async def submit(self, quotes):
        """
        Add a dictionary of quote updates.

        quotes = {
            "AAPL": {...},
            "MSFT": {...}
        }
        """

        async with self.lock:

            for symbol, quote in quotes.items():

                self.buffer[symbol].update(
                    quote
                )

                self.total_ticks += 1

    #
    # Backward compatibility
    #

    async def add(self, symbol, tick):

        await self.submit(
            {
                symbol: tick
            }
        )

    #
    # ---------------------------------------------------------
    #

    async def run(self):

        self.running = True

        logger.info(
            "TickCoalescer started (%d ms)",
            self.flush_ms
        )

        while self.running:

            await asyncio.sleep(
                self.flush_ms / 1000
            )

            await self.flush()

    #
    # ---------------------------------------------------------
    #

    async def flush(self):

        async with self.lock:

            if not self.buffer:

                return

            batch = dict(self.buffer)

            self.buffer.clear()

        self.total_flushes += 1

        self.max_batch = max(
            self.max_batch,
            len(batch)
        )

        #
        # Update shared state first.
        #

        await self.state.update_quotes(
            batch
        )

        #
        # Notify subscribers.
        #

        dead = []

        for fn in self.subscribers:

            try:

                if inspect.iscoroutinefunction(fn):

                    await fn(batch)

                else:

                    fn(batch)

            except Exception:

                logger.exception(
                    "Subscriber failure"
                )

                dead.append(fn)

        for fn in dead:

            self.subscribers.discard(fn)

    #
    # ---------------------------------------------------------
    #

    async def shutdown(self):

        logger.info(
            "Stopping TickCoalescer"
        )

        self.running = False

    #
    # ---------------------------------------------------------
    #

    @property
    def stats(self):

        return {

            "ticks": self.total_ticks,

            "flushes": self.total_flushes,

            "max_batch": self.max_batch,

            "subscribers":
                len(self.subscribers)

        }