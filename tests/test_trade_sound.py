import numpy as np
from unittest.mock import MagicMock

from trading_app.services.trade_sound import (
    ToneSettings,
    TradeSoundService,
    TradeSoundSettings,
)
from trading_app.services import trade_sound


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


def test_string_device_name_resolves_to_matching_output_index(monkeypatch):
    devices = [
        {"name": "Monitor", "max_output_channels": 0},
        {"name": "PipeWire", "max_output_channels": 2},
    ]
    monkeypatch.setattr(trade_sound.sd, "query_devices", lambda: devices)
    stream = MagicMock()
    monkeypatch.setattr(trade_sound.sd, "OutputStream", lambda **kwargs: stream)

    service = TradeSoundService(
        TradeSoundSettings(enabled=True, device="pipewire")
    )

    assert service._started is True
    assert service._stream is stream
    stream.start.assert_called_once()

    service.close()


def test_string_device_name_matches_backend_name_containing_pipewire(monkeypatch):
    devices = [
        {"name": "PipeWire: ALSA Output", "max_output_channels": 2},
    ]
    monkeypatch.setattr(trade_sound.sd, "query_devices", lambda: devices)
    stream = MagicMock()
    output_stream = MagicMock(return_value=stream)
    monkeypatch.setattr(trade_sound.sd, "OutputStream", output_stream)

    service = TradeSoundService(
        TradeSoundSettings(enabled=True, device="PipeWire")
    )

    assert service._started is True
    assert output_stream.call_args.kwargs["device"] == 0
    service.close()


def test_numeric_device_index_is_passed_through(monkeypatch):
    query_devices = MagicMock(side_effect=AssertionError("should not query"))
    monkeypatch.setattr(trade_sound.sd, "query_devices", query_devices)
    stream = MagicMock()
    output_stream = MagicMock(return_value=stream)
    monkeypatch.setattr(trade_sound.sd, "OutputStream", output_stream)

    service = TradeSoundService(
        TradeSoundSettings(enabled=True, device=21)
    )

    assert service._started is True
    assert output_stream.call_args.kwargs["device"] == 21
    query_devices.assert_not_called()

    service.close()
