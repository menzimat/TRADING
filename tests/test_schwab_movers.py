import asyncio
import logging

import httpx

from trading_app.schwab_streamer import SchwabStreamer


class TimeoutMoversClient:
    class Movers:
        class Index:
            EQUITY_ALL = "EQUITY_ALL"

        class SortOrder:
            PERCENT_CHANGE_UP = "PERCENT_CHANGE_UP"

    async def get_movers(self, *args, **kwargs):
        raise httpx.ConnectTimeout("connection timed out")


def test_equity_movers_timeout_keeps_existing_movers(caplog):
    streamer = object.__new__(SchwabStreamer)
    streamer.client = TimeoutMoversClient()
    streamer._frequency_enum = lambda: 5
    streamer.min_mover_price = 0.7
    streamer.max_mover_price = 20.0
    streamer.max_movers = 10

    with caplog.at_level(logging.WARNING):
        result = asyncio.run(streamer.get_equity_movers())

    assert result is None
    assert "Timed out while fetching Schwab equity movers" in caplog.text
