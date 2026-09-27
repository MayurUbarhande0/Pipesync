"""
Audio Calibration and Acoustic Transient Generator for Latency Tuning
"""

import logging
import math
import os
import struct
import subprocess
import threading
import time
import wave
from typing import Optional

from pipesync.constants import TICK_WAV_PATH, MASTER_SINK_NAME

logger = logging.getLogger(__name__)


class AudioCalibrator:
    """Generates acoustic reference clicks and metronome pulses for fine-tuning delay."""

    def __init__(self):
        self._ensure_wav_file()
        self._metronome_thread: Optional[threading.Thread] = None
        self._stop_metronome = threading.Event()

    def _ensure_wav_file(self):
        """Generates the calibration click WAV file if it does not already exist."""
        if TICK_WAV_PATH.exists():
            return

        TICK_WAV_PATH.parent.mkdir(parents=True, exist_ok=True)
        sample_rate = 48000
        duration = 0.5  # 500ms total file length
        pulse_len = 0.015  # 15ms pulse

        n_samples = int(sample_rate * duration)
        with wave.open(str(TICK_WAV_PATH), "w") as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)

            frames = bytearray()
            for i in range(n_samples):
                t = i / sample_rate
                if t < pulse_len:
                    # 1200Hz sine burst with exponential envelope
                    env = math.exp(-t * 250)
                    sample_val = int(28000 * math.sin(2 * math.pi * 1200 * t) * env)
                else:
                    sample_val = 0
                frames.extend(struct.pack("<hh", sample_val, sample_val))

            wav.writeframes(frames)
        logger.info(f"Generated calibration tick WAV at {TICK_WAV_PATH}")

    def play_pulse(self, target_sink: str = MASTER_SINK_NAME):
        """Plays a single calibration pulse to the specified sink."""
        self._ensure_wav_file()
        try:
            # pw-play supports targeting a specific sink via target.object property
            subprocess.Popen(
                ["pw-play", "--target", target_sink, str(TICK_WAV_PATH)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            logger.warning(f"Error playing calibration pulse: {e}")

    def play_device_beep(self, target_sink: str, freq_hz: int = 880):
        """Plays a short tone on a specific target sink to verify device identity."""
        temp_wav = f"/tmp/beep_{freq_hz}.wav"
        if not os.path.exists(temp_wav):
            sr = 48000
            dur = 0.25
            with wave.open(temp_wav, "w") as wav:
                wav.setnchannels(2)
                wav.setsampwidth(2)
                wav.setframerate(sr)
                frames = bytearray()
                for i in range(int(sr * dur)):
                    t = i / sr
                    env = math.sin(math.pi * t / dur)
                    val = int(24000 * math.sin(2 * math.pi * freq_hz * t) * env)
                    frames.extend(struct.pack("<hh", val, val))
                wav.writeframes(frames)

        try:
            subprocess.Popen(
                ["pw-play", "--target", target_sink, temp_wav],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            logger.warning(f"Error playing device beep: {e}")

    def start_metronome(self, interval_sec: float = 0.65, target_sink: str = MASTER_SINK_NAME):
        """Starts a rhythmic metronome pulse in the background."""
        self.stop_metronome()
        self._stop_metronome.clear()

        def _metronome_loop():
            logger.info("Metronome calibrator started")
            while not self._stop_metronome.is_set():
                self.play_pulse(target_sink)
                # Sleep in short slices for prompt stop response
                start_time = time.time()
                while time.time() - start_time < interval_sec:
                    if self._stop_metronome.is_set():
                        break
                    time.sleep(0.02)
            logger.info("Metronome calibrator stopped")

        self._metronome_thread = threading.Thread(target=_metronome_loop, daemon=True)
        self._metronome_thread.start()

    def stop_metronome(self):
        """Stops the rhythmic metronome if running."""
        if self._metronome_thread and self._metronome_thread.is_alive():
            self._stop_metronome.set()
            self._metronome_thread.join(timeout=1.0)
            self._metronome_thread = None

    @property
    def is_metronome_active(self) -> bool:
        return self._metronome_thread is not None and self._metronome_thread.is_alive()
