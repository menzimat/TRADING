import json

from trading_app.schwab_streamer import (
    SchwabStreamer,
)


def make_fill_record(
    side="Buy",
    symbol="AAPL",
    order_id="123456",
    execution_id="EXEC-001",
):
    payload = {
        "SchwabOrderID": order_id,
        "AccountNumber": "ACCOUNT",
        "BaseEvent": {
            "EventType": "OrderFillCompleted",
            "OrderFillCompletedEventOrderLegQuantityInfo": {
                "EventType": "OrderFillCompleted",
                "LegId": "LEG-001",
                "LegStatus": "LegClosed",
                "QuantityInfo": {
                    "ExecutionID": execution_id,
                    "CumulativeQuantity": {
                        "lo": "1000000",
                        "signScale": 12,
                    },
                    "LeavesQuantity": {
                        "signScale": 12,
                    },
                    "AveragePrice": {
                        "lo": "213409100",
                        "signScale": 12,
                    },
                },
                "LegSubStatus": "LegSubStatusFilled",
                "ExecutionInfo": {
                    "ExecutionSequenceNumber": 1,
                    "ExecutionId": execution_id,
                    "ExecutionQuantity": {
                        "lo": "1000000",
                        "signScale": 12,
                    },
                    "ExecutionPrice": {
                        "lo": "213409100",
                        "signScale": 12,
                    },
                    "ExecutionTimeStamp": {
                        "DateTimeString":
                            "2025-03-20 13:43:45.620"
                    },
                },
                "OrderInfoForTransactionPosting": {
                    "OrderTypeCode": "Limit",
                    "BuySellCode": side,
                    "Quantity": {
                        "lo": "1000000",
                        "signScale": 12,
                    },
                    "Symbol": symbol,
                },
            },
        },
    }

    return {
        "1": "ACCOUNT",
        "2": "OrderFillCompleted",
        "3": json.dumps(payload),
        "seq": 1,
        "key": "Account Activity",
    }


def test_buy_fill_is_parsed():
    result = (
        SchwabStreamer._parse_trade_fill_record(
            make_fill_record(
                side="Buy"
            )
        )
    )

    assert result is not None
    assert result["side"] == "BUY"
    assert result["symbol"] == "AAPL"
    assert result["order_id"] == "123456"
    assert result["execution_id"] == "EXEC-001"
    assert result["quantity"] == 1.0
    assert result["price"] == 213.4091


def test_sell_fill_is_parsed():
    result = (
        SchwabStreamer._parse_trade_fill_record(
            make_fill_record(
                side="Sell"
            )
        )
    )

    assert result is not None
    assert result["side"] == "SELL"


def test_buy_to_cover_is_buy_sound():
    result = (
        SchwabStreamer._parse_trade_fill_record(
            make_fill_record(
                side="BuyToCover"
            )
        )
    )

    assert result is not None
    assert result["side"] == "BUY"


def test_sell_short_is_sell_sound():
    result = (
        SchwabStreamer._parse_trade_fill_record(
            make_fill_record(
                side="SellShort"
            )
        )
    )

    assert result is not None
    assert result["side"] == "SELL"


def test_order_accepted_does_not_trigger_fill():
    record = make_fill_record()
    record["2"] = "OrderAccepted"

    assert (
        SchwabStreamer._parse_trade_fill_record(
            record
        )
        is None
    )


def test_malformed_fill_is_ignored():
    record = make_fill_record()
    record["3"] = "{not valid json"

    assert (
        SchwabStreamer._parse_trade_fill_record(
            record
        )
        is None
    )


def test_non_dictionary_record_is_ignored():
    assert (
        SchwabStreamer._parse_trade_fill_record(
            "not a record"
        )
        is None
    )


class FakeSound:
    def __init__(self):
        self.buy_count = 0
        self.sell_count = 0

    def play_buy(self):
        self.buy_count += 1

    def play_sell(self):
        self.sell_count += 1


def test_fill_sound_is_played_once():
    streamer = object.__new__(SchwabStreamer)

    sound = FakeSound()

    streamer.trade_sound = sound
    streamer._played_execution_ids = set()

    record = make_fill_record(
        side="Buy",
        execution_id="EXEC-123",
    )

    streamer._process_trade_fill_sounds(
        [record]
    )

    assert sound.buy_count == 1
    assert sound.sell_count == 0


def test_duplicate_execution_does_not_play_twice():
    streamer = object.__new__(SchwabStreamer)

    sound = FakeSound()

    streamer.trade_sound = sound
    streamer._played_execution_ids = set()

    record = make_fill_record(
        side="Sell",
        execution_id="EXEC-123",
    )

    streamer._process_trade_fill_sounds(
        [record]
    )

    streamer._process_trade_fill_sounds(
        [record]
    )

    assert sound.buy_count == 0
    assert sound.sell_count == 1