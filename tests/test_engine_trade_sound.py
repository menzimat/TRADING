"""
Audible integration test for the Engine -> SchwabStreamer -> TradeSound path.

This test does NOT connect to Schwab and does NOT submit orders.

It exercises the actual SchwabStreamer fill-processing code with the
real TradeSoundService and therefore verifies:

    confirmed fill
        -> _process_trade_fill_sounds()
        -> play_buy()/play_sell()
        -> persistent sounddevice OutputStream
        -> PipeWire

Run explicitly:

    pytest -q tests/test_engine_trade_sound.py -s

This test intentionally produces audible output.
"""

import time

import pytest

from trading_app.services.trade_sound import (
    ToneSettings,
    TradeSoundService,
    TradeSoundSettings,
)
from trading_app.schwab_streamer import SchwabStreamer

from tests.test_schwab_streamer_fill import make_fill_record


PIPEWIRE_DEVICE = 24


@pytest.fixture
def real_trade_sound():
    """
    Create the same TradeSoundService configuration used by Engine,
    explicitly selecting the known-working PipeWire device.
    """

    settings = TradeSoundSettings(
        enabled=True,
        device=PIPEWIRE_DEVICE,
        sample_rate=48000,
        queue_size=8,

        buy=ToneSettings(
            type="chime",
            frequency_hz=880.0,
            frequency2_hz=1175.0,
            duration_ms=180.0,
            volume=0.30,
        ),

        sell=ToneSettings(
            type="boop",
            frequency_hz=520.0,
            frequency2_hz=390.0,
            duration_ms=180.0,
            volume=0.30,
        ),
    )

    service = TradeSoundService(settings)

    try:
        yield service
    finally:
        service.close()


@pytest.fixture
def streamer_with_real_sound(real_trade_sound):
    """
    Create a SchwabStreamer instance without establishing a Schwab
    connection.

    _process_trade_fill_sounds() does not require the network client,
    EventBus, or StateEngine, so object.__new__ lets us exercise the
    actual production fill-sound path without starting the application.
    """

    streamer = object.__new__(SchwabStreamer)

    streamer.trade_sound = real_trade_sound
    streamer._played_execution_ids = set()

    return streamer


def test_engine_fill_buy_produces_real_sound(
    streamer_with_real_sound,
):
    """
    Simulate a confirmed BUY execution through the actual
    SchwabStreamer fill-sound path.
    """

    record = make_fill_record(
        side="Buy",
        execution_id="ENGINE-SOUND-BUY-001",
    )

    print()
    print("========================================")
    print("ENGINE/FILL SOUND TEST: BUY")
    print("========================================")
    print("Expected: high two-tone BUY chime")

    start = time.perf_counter()

    streamer_with_real_sound._process_trade_fill_sounds(
        [record]
    )

    elapsed = time.perf_counter() - start

    print(
        f"Fill sound request returned in "
        f"{elapsed * 1000:.3f} ms"
    )

    # The fill-processing path must not block waiting for the sound.
    assert elapsed < 0.100

    # Allow the queued 180-ms sound to reach the hardware.
    time.sleep(0.30)

    print("BUY sound complete.")


def test_engine_fill_sell_produces_real_sound(
    streamer_with_real_sound,
):
    """
    Simulate a confirmed SELL execution through the actual
    SchwabStreamer fill-sound path.
    """

    record = make_fill_record(
        side="Sell",
        execution_id="ENGINE-SOUND-SELL-001",
    )

    print()
    print("========================================")
    print("ENGINE/FILL SOUND TEST: SELL")
    print("========================================")
    print("Expected: lower descending SELL boop")

    start = time.perf_counter()

    streamer_with_real_sound._process_trade_fill_sounds(
        [record]
    )

    elapsed = time.perf_counter() - start

    print(
        f"Fill sound request returned in "
        f"{elapsed * 1000:.3f} ms"
    )

    assert elapsed < 0.100

    time.sleep(0.30)

    print("SELL sound complete.")


def test_engine_fill_buy_then_sell_produces_distinct_sounds(
    streamer_with_real_sound,
):
    """
    Exercise two consecutive confirmed fills.

    The BUY and SELL requests use different execution IDs and therefore
    must both reach the real TradeSoundService.
    """

    buy_record = make_fill_record(
        side="Buy",
        execution_id="ENGINE-SOUND-SEQUENCE-BUY",
    )

    sell_record = make_fill_record(
        side="Sell",
        execution_id="ENGINE-SOUND-SEQUENCE-SELL",
    )

    print()
    print("========================================")
    print("ENGINE/FILL SOUND TEST: BUY -> SELL")
    print("========================================")
    print("Expected:")
    print("  1. High BUY chime")
    print("  2. Lower SELL boop")

    start = time.perf_counter()

    streamer_with_real_sound._process_trade_fill_sounds(
        [buy_record]
    )

    streamer_with_real_sound._process_trade_fill_sounds(
        [sell_record]
    )

    elapsed = time.perf_counter() - start

    print(
        f"Both fill sound requests returned in "
        f"{elapsed * 1000:.3f} ms"
    )

    # Both calls should only enqueue audio. They must not wait for
    # the sounds to finish playing.
    assert elapsed < 0.100

    # Both sounds are approximately 180 ms and are queued back-to-back.
    time.sleep(0.50)

    print("BUY -> SELL sequence complete.")
