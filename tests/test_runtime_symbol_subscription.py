import unittest
from unittest.mock import patch
import asyncio

from trading_app.engine.runtime import Runtime
from trading_app.schwab_streamer import SchwabStreamer


class DummyStreamer:
    def __init__(self, existing_symbols=()):
        self.existing_symbols = set(existing_symbols)

    def has_symbol(self, symbol):
        return symbol in self.existing_symbols

    async def add_symbol(self, symbol):
        return True


class RuntimeSymbolSubscriptionTests(unittest.TestCase):
    def make_runtime(self, streamer):
        runtime = Runtime(
            bus=None,
            streamer=streamer,
            command_processor=None,
            state_engine=None,
        )
        runtime.running = True
        runtime.loop = object()
        return runtime

    def test_add_symbol_normalizes_and_schedules_streamer_subscription(self):
        runtime = self.make_runtime(DummyStreamer())

        with patch(
            "trading_app.engine.runtime.asyncio.run_coroutine_threadsafe"
        ) as schedule:
            self.assertTrue(runtime.add_symbol(" aapl "))

        coroutine, loop = schedule.call_args.args
        self.assertEqual(loop, runtime.loop)
        coroutine.close()

    def test_add_symbol_rejects_existing_or_blank_symbols(self):
        runtime = self.make_runtime(DummyStreamer({"AAPL"}))

        with patch(
            "trading_app.engine.runtime.asyncio.run_coroutine_threadsafe"
        ) as schedule:
            self.assertFalse(runtime.add_symbol("aapl"))
            self.assertFalse(runtime.add_symbol("   "))
            self.assertFalse(runtime.add_symbol("-"))

        schedule.assert_not_called()


class DummyStreamClient:
    def __init__(self):
        self.subs_calls = []
        self.add_calls = []
        self.unsubs_calls = []

    async def level_one_equity_subs(self, symbols):
        self.subs_calls.append(symbols)

    async def level_one_equity_add(self, symbols):
        self.add_calls.append(symbols)

    async def level_one_equity_unsubs(self, symbols):
        self.unsubs_calls.append(symbols)


class SchwabStreamerSubscriptionTests(unittest.IsolatedAsyncioTestCase):
    def make_streamer(self):
        streamer = SchwabStreamer.__new__(SchwabStreamer)
        streamer.symbols = ["AAPL"]
        streamer.stream_client = DummyStreamClient()
        streamer._subscribed_symbols = {"AAPL"}
        streamer._subscription_lock = asyncio.Lock()
        streamer._subscriptions_ready = True
        return streamer

    async def test_dynamic_symbol_uses_add_without_replacing_existing_subs(self):
        streamer = self.make_streamer()

        self.assertTrue(await streamer.add_symbol("msft"))

        self.assertEqual(streamer.symbols, ["AAPL", "MSFT"])
        self.assertEqual(streamer.stream_client.subs_calls, [])
        self.assertEqual(streamer.stream_client.add_calls, [["MSFT"]])

    async def test_remove_symbol_unsubscribes_and_removes_the_watchlist_entry(self):
        streamer = self.make_streamer()

        self.assertTrue(await streamer.remove_symbol("aapl"))

        self.assertEqual(streamer.symbols, [])
        self.assertNotIn("AAPL", streamer._subscribed_symbols)
        self.assertEqual(streamer.stream_client.unsubs_calls, [["AAPL"]])


if __name__ == "__main__":
    unittest.main()
