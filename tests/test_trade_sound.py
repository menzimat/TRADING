import numpy as np

from trading_app.services.trade_sound import (
    ToneSettings,
    TradeSoundService,
    TradeSoundSettings,
)


def test_buy_and_sell_waveforms_are_generated_without_starting_audio():
    settings = TradeSoundSettings(
        enabled=False,
        sample_rate=48000,
    )

    service = TradeSoundService(settings)

    assert service._started is False

    # Disabled services don't initialize waveforms.
    assert service._buy_samples.size == 0
    assert service._sell_samples.size == 0

    service.close()


def test_generated_waveform_has_expected_duration():
    settings = TradeSoundSettings(
        enabled=False,
        sample_rate=48000,
    )

    service = TradeSoundService(settings)

    samples = service._generate_tone(
        ToneSettings(
            type="beep",
            frequency_hz=880,
            duration_ms=100,
            volume=0.30,
        )
    )

    assert samples.dtype == np.float32
    assert len(samples) == 4800
    assert np.max(np.abs(samples)) <= 0.30


def test_chime_is_generated():
    settings = TradeSoundSettings(
        enabled=False,
        sample_rate=48000,
    )

    service = TradeSoundService(settings)

    samples = service._generate_tone(
        ToneSettings(
            type="chime",
            frequency_hz=880,
            frequency2_hz=1175,
            duration_ms=120,
            volume=0.30,
        )
    )

    assert len(samples) == 5760
    assert np.max(np.abs(samples)) > 0.0


def test_booped_waveform_is_generated():
    settings = TradeSoundSettings(
        enabled=False,
        sample_rate=48000,
    )

    service = TradeSoundService(settings)

    samples = service._generate_tone(
        ToneSettings(
            type="boop",
            frequency_hz=520,
            frequency2_hz=390,
            duration_ms=120,
            volume=0.30,
        )
    )

    assert len(samples) == 5760
    assert np.max(np.abs(samples)) > 0.0


def test_disabled_service_playback_is_nonblocking():
    settings = TradeSoundSettings(
        enabled=False,
    )

    service = TradeSoundService(settings)

    service.play_buy()
    service.play_sell()

    service.close()