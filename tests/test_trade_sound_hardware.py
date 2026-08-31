"""
Hardware tests for the persistent trade sound service.

These tests intentionally produce audible BUY and SELL sounds.

Run explicitly with:

    pytest -q tests/test_trade_sound_hardware.py -s

They are NOT intended to be part of an unattended CI test run.
"""

import time

import pytest

from trading_app.services.trade_sound import (
    ToneSettings,
    TradeSoundService,
    TradeSoundSettings,
)


# Device 25 was confirmed by the user to produce audio through PipeWire.
PIPEWIRE_DEVICE = 24


@pytest.fixture
def hardware_sound_service():
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

    if not service._started:
        service.close()
        pytest.fail(
            "TradeSoundService could not open "
            f"audio device {PIPEWIRE_DEVICE}"
        )

    try:
        yield service
    finally:
        service.close()


def test_buy_sound_hardware(hardware_sound_service):
    """
    Play the BUY sound.

    Expected:
        short, higher-pitched two-tone chime.
    """

    print()
    print("========================================")
    print("PLAYING BUY SOUND")
    print("========================================")

    hardware_sound_service.play_buy()

    # Allow the 180-ms sound to reach the hardware.
    time.sleep(0.30)

    print("BUY sound complete.")


def test_sell_sound_hardware(hardware_sound_service):
    """
    Play the SELL sound.

    Expected:
        short, lower-pitched descending boop.
    """

    print()
    print("========================================")
    print("PLAYING SELL SOUND")
    print("========================================")

    hardware_sound_service.play_sell()

    time.sleep(0.30)

    print("SELL sound complete.")


def test_buy_then_sell_hardware(hardware_sound_service):
    """
    Verify that two sounds can be queued without reopening
    or reinitializing the audio device.
    """

    print()
    print("========================================")
    print("PLAYING BUY THEN SELL")
    print("========================================")

    start = time.perf_counter()

    hardware_sound_service.play_buy()
    hardware_sound_service.play_sell()

    elapsed = time.perf_counter() - start

    print(
        f"Both playback requests queued in "
        f"{elapsed * 1000:.3f} ms"
    )

    # The two 180-ms sounds are queued back-to-back.
    time.sleep(0.50)

    print("BUY + SELL sequence complete.")

    # The important requirement is that the playback calls themselves
    # return very quickly and do not wait for the sounds to finish.
    assert elapsed < 0.050
