import unittest

from trading_app.services.hotkeys import HotkeyManager
from trading_app.trading_config import TradingConfig


class DummyRuntime:
    pass


class HotkeyManagerTests(unittest.TestCase):
    def test_resolve_hotkey_target_from_config(self):
        config = TradingConfig.load("cfg/trading.yaml")
        manager = HotkeyManager(
            trading_config=config,
            runtime=DummyRuntime(),
        )

        self.assertEqual(
            manager.resolve_hotkey_target("ctrl+b"),
            {"template_name": "buy_limit", "overrides": None},
        )
        self.assertEqual(
            manager.resolve_hotkey_target("esc"),
            {"action": "CANCEL_ALL"},
        )


if __name__ == "__main__":
    unittest.main()
