"""
trade_sound.py

Low-latency BUY/SELL trade notification sounds.

The service:
    - Generates BUY and SELL waveforms once during initialization.
    - Keeps one PortAudio output stream open for the lifetime of the service.
    - Uses a small non-blocking queue for playback requests.
    - Does not launch an external audio player.
    - Does not read sound files when a trade occurs.

On Linux Mint using PipeWire, sounddevice/PortAudio normally routes
through the system's configured PipeWire audio device.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections import deque
import logging
import math
import threading
from typing import Any

import numpy as np
import sounddevice as sd


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToneSettings:
    """Settings for one generated trade sound."""

    type: str = "beep"
    frequency_hz: float = 880.0
    frequency2_hz: float | None = None
    duration_ms: float = 120.0
    volume: float = 0.30


@dataclass(frozen=True)
class TradeSoundSettings:
    """Complete trade-sound configuration."""

    enabled: bool = True
    device: int | str | None = None
    sample_rate: int = 48000
    queue_size: int = 8
    buy: ToneSettings = ToneSettings(
        type="chime",
        frequency_hz=880.0,
        frequency2_hz=1175.0,
        duration_ms=120.0,
        volume=0.30,
    )
    sell: ToneSettings = ToneSettings(
        type="boop",
        frequency_hz=520.0,
        frequency2_hz=390.0,
        duration_ms=120.0,
        volume=0.30,
    )


class TradeSoundService:
    """
    Persistent, low-latency BUY/SELL audio notification service.

    The audio stream is opened once. Playback requests are simply placed
    into an in-memory queue and therefore do not block the trading stream.
    """

    def __init__(self, settings: TradeSoundSettings | None = None):
        self.settings = settings or TradeSoundSettings()

        self._lock = threading.Lock()
        self._queue: deque[np.ndarray] = deque(
            maxlen=max(1, self.settings.queue_size)
        )

        self._buy_samples = np.empty(0, dtype=np.float32)
        self._sell_samples = np.empty(0, dtype=np.float32)

        self._stream: sd.OutputStream | None = None
        self._current_samples: np.ndarray | None = None
        self._current_index = 0

        self._started = False
        self._closed = False

        if not self.settings.enabled:
            logger.info("Trade sounds disabled")
            return

        self._initialize()

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def _initialize(self) -> None:
        """Generate sounds and open the persistent audio stream."""

        try:
            self._buy_samples = self._generate_tone(
                self.settings.buy
            )

            self._sell_samples = self._generate_tone(
                self.settings.sell
            )

            self._stream = sd.OutputStream(
                samplerate=self.settings.sample_rate,
                channels=1,
                dtype="float32",
                callback=self._audio_callback,
                blocksize=0,
                latency="low",
                device=self.settings.device,
            )

            self._stream.start()
            self._started = True

            logger.info(
                "Trade sound service initialized "
                "(sample_rate=%d)",
                self.settings.sample_rate,
            )

        except Exception:
            logger.exception(
                "Unable to initialize trade sound service; "
                "trading will continue without audio"
            )

            self._stream = None
            self._started = False

    # ------------------------------------------------------------------
    # Waveform generation
    # ------------------------------------------------------------------

    def _generate_tone(
        self,
        settings: ToneSettings,
    ) -> np.ndarray:
        """
        Generate a short tone/chime in memory.

        The generated samples are never regenerated during playback.
        """

        sample_count = max(
            1,
            int(
                self.settings.sample_rate
                * settings.duration_ms
                / 1000.0
            ),
        )

        t = np.arange(
            sample_count,
            dtype=np.float32,
        ) / float(self.settings.sample_rate)

        duration = sample_count / float(
            self.settings.sample_rate
        )

        tone_type = settings.type.lower().strip()

        f1 = max(20.0, float(settings.frequency_hz))

        if settings.frequency2_hz is not None:
            f2 = max(20.0, float(settings.frequency2_hz))
        else:
            f2 = f1

        if tone_type == "chime":
            # Upward two-tone chime.
            half = max(1, sample_count // 2)

            samples = np.empty(
                sample_count,
                dtype=np.float32,
            )

            first_t = t[:half]
            second_t = t[half:] - (
                half / float(self.settings.sample_rate)
            )

            samples[:half] = np.sin(
                2.0 * math.pi * f1 * first_t
            )

            samples[half:] = np.sin(
                2.0 * math.pi * f2 * second_t
            )

        elif tone_type == "boop":
            # A short downward sweep.
            sweep = np.linspace(
                f1,
                f2,
                sample_count,
                dtype=np.float32,
            )

            phase = (
                2.0
                * math.pi
                * (
                    f1 * t
                    + 0.5
                    * (f2 - f1)
                    / max(duration, 1e-6)
                    * t * t
                )
            )

            samples = np.sin(phase)

        else:
            # Default: simple beep.
            samples = np.sin(
                2.0 * math.pi * f1 * t
            )

        # Short attack/release envelope prevents clicks.
        attack_samples = max(
            1,
            int(
                self.settings.sample_rate
                * min(0.010, duration / 8.0)
            ),
        )

        release_samples = attack_samples

        envelope = np.ones(
            sample_count,
            dtype=np.float32,
        )

        envelope[:attack_samples] = np.linspace(
            0.0,
            1.0,
            attack_samples,
            dtype=np.float32,
        )

        envelope[-release_samples:] = np.linspace(
            1.0,
            0.0,
            release_samples,
            dtype=np.float32,
        )

        volume = min(
            1.0,
            max(0.0, float(settings.volume)),
        )

        samples = (
            samples.astype(np.float32)
            * envelope
            * volume
        )

        return samples

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    def play_buy(self) -> None:
        """Queue the pre-generated BUY sound."""

        self._queue_sound(self._buy_samples)

    def play_sell(self) -> None:
        """Queue the pre-generated SELL sound."""

        self._queue_sound(self._sell_samples)

    def _queue_sound(
        self,
        samples: np.ndarray,
    ) -> None:
        """
        Queue a sound without blocking.

        If the queue is full, the oldest notification is discarded.
        A trading notification must never be allowed to block the
        Schwab streaming event loop.
        """

        if not self._started:
            return

        if samples.size == 0:
            return

        with self._lock:
            if len(self._queue) >= self.settings.queue_size:
                self._queue.popleft()

            self._queue.append(samples)

    # ------------------------------------------------------------------
    # PortAudio callback
    # ------------------------------------------------------------------

    def _audio_callback(
        self,
        outdata: np.ndarray,
        frames: int,
        time_info: Any,
        status: sd.CallbackFlags,
    ) -> None:
        """PortAudio callback; must remain fast and non-blocking."""

        if status:
            logger.debug("Trade audio callback status: %s", status)

        outdata.fill(0)

        written = 0

        while written < frames:

            if self._current_samples is None:

                with self._lock:
                    if not self._queue:
                        return

                    self._current_samples = (
                        self._queue.popleft()
                    )
                    self._current_index = 0

            remaining = (
                len(self._current_samples)
                - self._current_index
            )

            count = min(
                frames - written,
                remaining,
            )

            outdata[
                written : written + count,
                0
            ] = self._current_samples[
                self._current_index :
                self._current_index + count
            ]

            self._current_index += count
            written += count

            if (
                self._current_index
                >= len(self._current_samples)
            ):
                self._current_samples = None
                self._current_index = 0

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Stop and release the persistent audio stream."""

        if self._closed:
            return

        self._closed = True

        stream = self._stream
        self._stream = None
        self._started = False

        if stream is not None:
            try:
                stream.stop()
            except Exception:
                logger.debug(
                    "Trade audio stream stop failed",
                    exc_info=True,
                )

            try:
                stream.close()
            except Exception:
                logger.debug(
                    "Trade audio stream close failed",
                    exc_info=True,
                )

        with self._lock:
            self._queue.clear()

        logger.debug("Trade sound service closed")

    def __enter__(self) -> "TradeSoundService":
        return self

    def __exit__(self, *args) -> None:
        self.close()