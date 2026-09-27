"""
Configuration and Profiles Persistence for PipeSync
"""

import json
import logging
from typing import Dict, Any, Optional

from pipesync.constants import (
    CONFIG_DIR,
    SETTINGS_FILE,
    PROFILES_FILE,
    DEFAULT_QUANTUM,
)
from pipesync.models import SyncProfile

logger = logging.getLogger(__name__)


class ConfigManager:
    """Loads and saves user preferences and per-device calibration profiles."""

    def __init__(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.settings: Dict[str, Any] = self._load_settings()
        self.profiles: Dict[str, SyncProfile] = self._load_profiles()

    def _load_settings(self) -> Dict[str, Any]:
        default_settings = {
            "preferred_quantum": DEFAULT_QUANTUM,
            "auto_align_on_start": True,
            "set_default_sink": False,
            "metronome_bpm": 100,
            "mpv_ipc_enabled": True,
        }
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r") as f:
                    loaded = json.load(f)
                    default_settings.update(loaded)
            except Exception as e:
                logger.warning(f"Error loading settings file: {e}")
        return default_settings

    def save_settings(self):
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving settings: {e}")

    def _load_profiles(self) -> Dict[str, SyncProfile]:
        profiles = {}
        if PROFILES_FILE.exists():
            try:
                with open(PROFILES_FILE, "r") as f:
                    data = json.load(f)
                    for name, prof_data in data.items():
                        profiles[name] = SyncProfile.from_dict(prof_data)
            except Exception as e:
                logger.warning(f"Error loading profiles: {e}")
        return profiles

    def save_profile(self, profile: SyncProfile):
        self.profiles[profile.name] = profile
        try:
            with open(PROFILES_FILE, "w") as f:
                data = {k: v.to_dict() for k, v in self.profiles.items()}
                json.dump(data, f, indent=2)
            logger.info(f"Saved profile '{profile.name}'")
        except Exception as e:
            logger.error(f"Error saving profile: {e}")

    def get_calibrated_delay(self, device_name: str) -> Optional[float]:
        """Looks up if a specific device has a saved calibration offset."""
        # Check explicit device_delays map first
        dev_delays = self.settings.get("device_delays", {})
        if device_name in dev_delays:
            return float(dev_delays[device_name])
        for prof in self.profiles.values():
            if device_name in prof.delays:
                return float(prof.delays[device_name])
        return None

    def save_device_delay(self, device_name: str, delay_ms: float):
        """Persists the user-adjusted compensation delay for a specific audio sink."""
        if "device_delays" not in self.settings:
            self.settings["device_delays"] = {}
        self.settings["device_delays"][device_name] = round(delay_ms, 1)
        self.save_settings()

    def get_saved_volume(self, device_name: str) -> Optional[float]:
        """Returns saved volume setting for a device if present."""
        dev_vols = self.settings.get("device_volumes", {})
        if device_name in dev_vols:
            return float(dev_vols[device_name])
        return None

    def save_device_volume(self, device_name: str, volume: float):
        """Persists volume level for a specific audio sink."""
        if "device_volumes" not in self.settings:
            self.settings["device_volumes"] = {}
        self.settings["device_volumes"][device_name] = round(volume, 2)
        self.save_settings()

