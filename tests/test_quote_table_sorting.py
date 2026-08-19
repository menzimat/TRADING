import unittest

from trading_app.gui.table_renderer import QuoteTable
from trading_app.gui.application import TradingApplication


class QuoteTableSortingTests(unittest.TestCase):
    def test_numeric_sort_keys_handle_missing_values_without_mixed_types(self):
        keys = [
            QuoteTable._sortable_value("last", value)
            for value in ("12.34", "", "1,234.50", None)
        ]

        self.assertEqual(keys[0], (False, 12.34))
        self.assertEqual(keys[1], (True, 0.0))
        self.assertEqual(keys[2], (False, 1234.50))
        self.assertEqual(keys[3], (True, 0.0))

    def test_complete_quote_requires_all_numeric_display_fields(self):
        self.assertTrue(
            TradingApplication._has_complete_quote(
                {"last": 1.25, "bid": 1.24, "ask": 1.26, "volume": 100}
            )
        )
        self.assertFalse(
            TradingApplication._has_complete_quote(
                {"last": 1.25, "bid": 1.24, "ask": 1.26, "volume": None}
            )
        )


if __name__ == "__main__":
    unittest.main()
