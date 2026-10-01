"""
PipeSync Constants and Defaults
"""

import os
from pathlib import Path

APP_NAME = "PipeSync"
APP_DESCRIPTION = "Ultra-Low-Latency Multi-Device Audio Sharing & Synchronization for PipeWire & Helvum"
APP_ID = "org.pipewire.PipeSync"
from pipesync import __version__

APP_VERSION = __version__

# Master Virtual Sink Configuration
MASTER_SINK_NAME = "pipesync_master"
MASTER_SINK_DESC = "PipeSync: Multi-Device Broadcast"
MASTER_NODE_GROUP = "pipesync-hub"

# PipeWire Quantum Presets (at 48000 Hz)
# samples: (latency_ms, description)
QUANTUM_PRESETS = {
    128: {"ms": 2.67, "name": "Ultra-Low", "desc": "128 samples (~2.7ms) - Ideal for gaming & realtime sync"},
    256: {"ms": 5.33, "name": "Low-Latency", "desc": "256 samples (~5.3ms) - Recommended default, rock solid"},
    512: {"ms": 10.67, "name": "Balanced", "desc": "512 samples (~10.7ms) - Low CPU, moderate buffering"},
    1024: {"ms": 21.33, "name": "Standard", "desc": "1024 samples (~21.3ms) - PipeWire default profile"},
}

DEFAULT_QUANTUM = 256

# Device Category Classifications
TYPE_BLUETOOTH = "bluetooth"
TYPE_WIRED = "wired"
TYPE_USB = "usb"
TYPE_HDMI = "hdmi"
TYPE_SPEAKER = "speaker"
TYPE_OTHER = "other"

# Baseline Hardware Latency Estimates in milliseconds (used when not dynamically reported)
DEFAULT_DEVICE_LATENCIES_MS = {
    TYPE_BLUETOOTH: 185.0,  # Standard A2DP (SBC/AAC) typical hardware + buffer delay
    TYPE_WIRED: 5.0,        # 3.5mm analog output DAC
    TYPE_USB: 8.0,          # External USB DAC / Audio Interface
    TYPE_HDMI: 45.0,        # TV / Monitor HDMI audio processing delay
    TYPE_SPEAKER: 10.0,     # Built-in laptop speakers
    TYPE_OTHER: 15.0,
}

# Bluetooth Codec-Specific Estimated Base Latencies (ms)
BLUETOOTH_CODEC_LATENCY_MS = {
    "sbc": 210.0,
    "sbc_xq": 190.0,
    "aac": 175.0,
    "aptx": 130.0,
    "aptx_hd": 150.0,
    "aptx_ll": 38.0,
    "ldac": 160.0,
    "lc3": 35.0,
    "faststream": 45.0,
}

# Paths
CONFIG_DIR = Path(os.path.expanduser("~/.config/pipesync"))
PROFILES_FILE = CONFIG_DIR / "profiles.json"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
# Generated calibration audio belongs in the user's config area so installed
# wheels do not depend on repository-only files and remain read-only safe.
TICK_WAV_PATH = CONFIG_DIR / "calibration_tick.wav"
