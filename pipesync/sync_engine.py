"""
Multi-Device Audio Synchronization Engine for PipeWire
"""

import logging
import os
import re
import signal
import subprocess
import time
from typing import Dict, List, Optional

from pipesync.constants import (
    MASTER_SINK_NAME,
    MASTER_SINK_DESC,
    MASTER_NODE_GROUP,
)
from pipesync.models import AudioDevice

logger = logging.getLogger(__name__)


class SyncEngine:
    """
    Manages the virtual master broadcast sink and per-device delay-compensated
    loopback branches.
    """

    def __init__(self):
        self.master_module_id: Optional[int] = None
        self.branch_processes: Dict[str, subprocess.Popen] = {}  # device_name -> Popen
        self.active_devices: Dict[str, AudioDevice] = {}  # device_name -> AudioDevice
        self.is_running: bool = False
        self.previous_default_sink: Optional[str] = None
        self._check_for_existing_master()
        self._cleanup_orphaned_loopbacks()

    def _check_for_existing_master(self):
        """Checks if a master sink is already loaded from a previous session and cleans it."""
        try:
            res = subprocess.run(
                ["pactl", "list", "short", "modules"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            for line in res.stdout.splitlines():
                if MASTER_SINK_NAME in line and "module-null-sink" in line:
                    parts = line.split()
                    if parts:
                        mod_id = parts[0]
                        logger.info(f"Cleaning up pre-existing master module {mod_id}")
                        subprocess.run(["pactl", "unload-module", mod_id], capture_output=True, timeout=3)
        except Exception as e:
            logger.warning(f"Failed to check existing master modules: {e}")

    def get_current_default_sink(self) -> Optional[str]:
        """Returns the current default audio sink name."""
        try:
            res = subprocess.run(
                ["pactl", "get-default-sink"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            sink = res.stdout.strip()
            if sink and sink != MASTER_SINK_NAME:
                return sink
        except Exception as e:
            logger.warning(f"Failed to get default sink: {e}")
        return None

    def start_master_sink(self) -> bool:
        """Creates the PipeSync master broadcast sink in PipeWire."""
        if self.master_module_id:
            return True

        # Remember previous default sink before switching
        prev = self.get_current_default_sink()
        if prev and prev != MASTER_SINK_NAME:
            self.previous_default_sink = prev

        try:
            cmd = [
                "pactl",
                "load-module",
                "module-null-sink",
                f"sink_name={MASTER_SINK_NAME}",
                f"sink_properties=device.description=\"{MASTER_SINK_DESC}\"",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=5)
            try:
                self.master_module_id = int(res.stdout.strip())
            except (ValueError, TypeError) as e:
                logger.error(f"Failed to parse module ID from pactl output '{res.stdout.strip()}': {e}")
                self.master_module_id = None
                return False

            logger.info(f"Loaded master sink '{MASTER_SINK_NAME}' (Module ID: {self.master_module_id})")
            time.sleep(0.3)

            # Set as default sink so all new audio automatically plays into PipeSync
            self.set_as_default_sink(True)

            # Reroute any currently playing streams (like Chrome, Spotify, VLC) to PipeSync
            self.reroute_active_streams(MASTER_SINK_NAME)

            return True
        except Exception as e:
            logger.error(f"Failed to create master sink: {e}")
            return False

    def stop_master_sink(self):
        """Unloads the master sink from PipeWire and restores default sink."""
        # Restore previous default sink if we saved one
        if self.previous_default_sink:
            try:
                subprocess.run(
                    ["pactl", "set-default-sink", self.previous_default_sink],
                    capture_output=True,
                    timeout=3,
                )
                self.reroute_active_streams(self.previous_default_sink)
                logger.info(f"Restored default sink to '{self.previous_default_sink}'")
            except Exception as e:
                logger.warning(f"Failed to restore default sink: {e}")

        if self.master_module_id:
            try:
                subprocess.run(
                    ["pactl", "unload-module", str(self.master_module_id)],
                    capture_output=True,
                    timeout=3,
                )
                logger.info(f"Unloaded master sink module {self.master_module_id}")
            except Exception as e:
                logger.warning(f"Error unloading master sink: {e}")
            finally:
                self.master_module_id = None

    def reroute_active_streams(self, target_sink: str):
        """
        Moves all active non-PipeSync playback streams (e.g. Chrome, Spotify, MPV)
        to the target sink so they play through PipeSync.
        """
        try:
            res = subprocess.run(
                ["pactl", "list", "sink-inputs"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            current_input_id = None
            is_pipesync_loopback = False

            for line in res.stdout.splitlines():
                line = line.strip()
                if line.startswith("Sink Input #"):
                    # Process previous input
                    if current_input_id and not is_pipesync_loopback:
                        self._move_stream(current_input_id, target_sink)

                    current_input_id = line.split("#")[1].strip()
                    is_pipesync_loopback = False
                elif "PipeSync" in line or "pipesync" in line:
                    is_pipesync_loopback = True

            # Process last stream
            if current_input_id and not is_pipesync_loopback:
                self._move_stream(current_input_id, target_sink)

        except Exception as e:
            logger.warning(f"Error rerouting active streams: {e}")

    def _move_stream(self, input_id: str, target_sink: str):
        try:
            subprocess.run(
                ["pactl", "move-sink-input", input_id, target_sink],
                capture_output=True,
                timeout=2,
            )
            logger.info(f"Rerouted stream #{input_id} to '{target_sink}'")
        except Exception as e:
            logger.debug(f"Failed to move stream #{input_id}: {e}")

    def _generate_unique_branch_name(self, device: AudioDevice) -> str:
        """
        Generates a 100% unique, collision-free branch name incorporating the node ID
        and device name suffix.
        """
        suffix = device.name.split(".")[-1]
        clean_suffix = re.sub(r"[^a-zA-Z0-9_]", "_", suffix)[:20]
        return f"pipesync_br_{device.node_id}_{clean_suffix}"

    def _spawn_branch_loopback(self, device: AudioDevice) -> Optional[subprocess.Popen]:
        """Spawns a pw-loopback process for a specific target device with delay."""
        delay_sec = max(0.0, device.compensation_delay_ms / 1000.0)
        branch_name = self._generate_unique_branch_name(device)
        desc = f"PipeSync -> {device.description} (+{device.compensation_delay_ms:.1f}ms)"

        capture_props = (
            f"node.autoconnect=false "
            f"node.description=\"{desc}\" "
            f"node.group=\"{MASTER_NODE_GROUP}\" "
            f"audio.channels=2 "
            f"audio.position=[FL,FR] "
            f"resample.quality=4 "
            f"resample.prefill=true"
        )
        playback_props = (
            f"node.description=\"{desc}\" "
            f"node.group=\"{MASTER_NODE_GROUP}\" "
            f"audio.channels=2 "
            f"audio.position=[FL,FR] "
            f"resample.quality=4 "
            f"resample.prefill=true"
        )

        cmd = [
            "pw-loopback",
            "-n", branch_name,
            "-i", capture_props,
            "-o", playback_props,
            "-P", device.name,
            "-d", f"{delay_sec:.4f}",
        ]

        logger.info(f"Spawning loopback branch '{branch_name}' targeting '{device.name}' with delay {device.compensation_delay_ms:.1f}ms")
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid,
            )
            # Give loopback a short moment to register ports
            time.sleep(0.35)

            # Link master monitor to loopback input
            input_fl = f"input.{branch_name}:input_FL"
            input_fr = f"input.{branch_name}:input_FR"
            master_fl = f"{MASTER_SINK_NAME}:monitor_FL"
            master_fr = f"{MASTER_SINK_NAME}:monitor_FR"

            links = (
                subprocess.run(
                    ["pw-link", master_fl, input_fl],
                    capture_output=True,
                    timeout=2,
                ),
                subprocess.run(
                    ["pw-link", master_fr, input_fr],
                    capture_output=True,
                    timeout=2,
                ),
            )
            if any(result.returncode != 0 for result in links):
                logger.error("Failed to link PipeSync master to %s", device.name)
                self._terminate_process(proc)
                return None

            return proc
        except Exception as e:
            logger.error(f"Failed to spawn loopback for {device.name}: {e}")
            return None

    def start_sync(self, devices: List[AudioDevice]) -> bool:
        """Starts synchronized audio broadcasting across the specified devices."""
        if not self.start_master_sink():
            return False

        self.stop_all_branches()
        self.active_devices.clear()

        for dev in devices:
            if not dev.enabled:
                continue

            proc = self._spawn_branch_loopback(dev)
            if proc:
                self.branch_processes[dev.name] = proc
                self.active_devices[dev.name] = dev

        self.is_running = len(self.branch_processes) > 0
        if not self.is_running:
            # Do not leave a defaultable virtual sink behind after a partial
            # startup or an empty device selection.
            self.stop_master_sink()
        logger.info(f"SyncEngine running with {len(self.branch_processes)} active output branches")
        return self.is_running

    def update_device_delay(self, device_name: str, delay_ms: float) -> bool:
        """
        Dynamically updates the delay on a single device branch without
        restarting any other branches.
        """
        if device_name not in self.active_devices:
            logger.warning(f"Device {device_name} is not currently active in sync engine")
            return False

        device = self.active_devices[device_name]
        device.compensation_delay_ms = max(0.0, delay_ms)

        # Stop old branch for this device
        if device_name in self.branch_processes:
            old_proc = self.branch_processes.pop(device_name)
            self._terminate_process(old_proc)

        # Spawn updated branch
        new_proc = self._spawn_branch_loopback(device)
        if new_proc:
            self.branch_processes[device_name] = new_proc
            logger.info(f"Updated delay for {device.description} to {delay_ms:.1f}ms")
            return True
        return False

    def set_device_volume(self, device: AudioDevice, volume: float) -> bool:
        """
        Sets the actual output volume for a device sink in PipeWire (0.0 to 1.5).
        """
        vol_pct = int(max(0.0, min(1.5, volume)) * 100)
        device.volume = volume
        try:
            res = subprocess.run(
                ["pactl", "set-sink-volume", device.name, f"{vol_pct}%"],
                capture_output=True,
                timeout=2,
            )
            logger.info(f"Set volume for '{device.description}' to {vol_pct}%")
            return res.returncode == 0
        except Exception as e:
            logger.warning(f"Failed to set sink volume: {e}")
            return False

    def set_device_mute(self, device: AudioDevice, muted: bool) -> bool:
        """Sets mute state for a device sink in PipeWire."""
        device.muted = muted
        mute_val = "1" if muted else "0"
        try:
            res = subprocess.run(
                ["pactl", "set-sink-mute", device.name, mute_val],
                capture_output=True,
                timeout=2,
            )
            logger.info(f"Set mute for '{device.description}' to {muted}")
            return res.returncode == 0
        except Exception as e:
            logger.warning(f"Failed to set sink mute: {e}")
            return False

    def toggle_device_enabled(self, device: AudioDevice) -> bool:
        """Enables or disables an individual output device branch."""
        if device.enabled:
            self.active_devices[device.name] = device
            if device.name in self.branch_processes:
                return True
            proc = self._spawn_branch_loopback(device)
            if proc:
                self.branch_processes[device.name] = proc
                return True
            return False
        else:
            if device.name in self.branch_processes:
                proc = self.branch_processes.pop(device.name)
                self._terminate_process(proc)
            self.active_devices.pop(device.name, None)
            return True

    @staticmethod
    def _terminate_process(proc: subprocess.Popen):
        """Safely terminates a subprocess and its process group without leaking or raising."""
        if proc is None or proc.poll() is not None:
            return
        try:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGTERM)
            proc.wait(timeout=1.0)
        except (ProcessLookupError, OSError):
            pass
        except Exception as e:
            logger.debug(f"Exception terminating process group: {e}")

        # Fallback to direct process kill if process group did not exit
        if proc.poll() is None:
            try:
                proc.kill()
                proc.wait(timeout=0.5)
            except Exception:
                pass

    def stop_all_branches(self):
        """Terminates all active loopback processes."""
        for name, proc in list(self.branch_processes.items()):
            self._terminate_process(proc)
        self.branch_processes.clear()

    def set_as_default_sink(self, make_default: bool = True) -> bool:
        """Sets or unsets PipeSync master sink as the system default audio sink."""
        try:
            sink_target = MASTER_SINK_NAME if make_default else (self.previous_default_sink or "@DEFAULT_AUDIO_SINK@")
            subprocess.run(["pactl", "set-default-sink", sink_target], check=True, timeout=3)
            logger.info(f"Set '{sink_target}' as default system audio output")
            return True
        except Exception as e:
            logger.error(f"Failed to set default sink: {e}")
            return False

    def _cleanup_orphaned_loopbacks(self):
        """Kills any lingering pw-loopback processes created by PipeSync from previous sessions."""
        try:
            res = subprocess.run(
                ["pgrep", "-a", "pw-loopback"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            for line in res.stdout.splitlines():
                if "pipesync" in line or MASTER_NODE_GROUP in line:
                    parts = line.split()
                    if parts:
                        try:
                            pid = int(parts[0])
                            # Do not kill actively tracked child processes
                            if not any(p.pid == pid for p in self.branch_processes.values() if p):
                                logger.info(f"Cleaning up orphaned loopback process {pid}")
                                os.kill(pid, signal.SIGTERM)
                        except Exception:
                            pass
        except Exception as e:
            logger.debug(f"Error checking orphaned loopbacks: {e}")

    def heal_branches(self) -> int:
        """
        Self-healing monitor: checks all active branches; if any pw-loopback process
        died or was terminated externally, restarts it automatically.
        """
        if not self.is_running:
            return 0
        healed_count = 0
        for dev_name, dev in list(self.active_devices.items()):
            if not dev.enabled:
                continue
            proc = self.branch_processes.get(dev_name)
            if proc is None or proc.poll() is not None:
                logger.warning(f"Branch for '{dev.description}' died unexpectedly. Healing and respawning...")
                new_proc = self._spawn_branch_loopback(dev)
                if new_proc:
                    self.branch_processes[dev_name] = new_proc
                    healed_count += 1
        return healed_count

    def get_active_audio_streams(self) -> List[Dict]:
        """
        Returns a list of currently active audio playback streams (e.g. Chrome, Spotify, VLC)
        with application name, media title, stream ID, and current output sink.
        """
        streams = []
        try:
            res = subprocess.run(
                ["pactl", "list", "sink-inputs"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            current = {}
            for line in res.stdout.splitlines():
                line = line.strip()
                if line.startswith("Sink Input #"):
                    if current:
                        streams.append(current)
                    current = {"id": line.split("#")[1].strip(), "props": {}}
                elif ":" in line and not line.startswith("application.") and not line.startswith("media."):
                    k, v = line.split(":", 1)
                    current[k.strip()] = v.strip()
                elif "=" in line:
                    k, v = line.split("=", 1)
                    current.setdefault("props", {})[k.strip()] = v.strip().strip('"')

            if current:
                streams.append(current)

            result = []
            for s in streams:
                props = s.get("props", {})
                app_name = (
                    props.get("application.name")
                    or props.get("media.name")
                    or props.get("node.name")
                    or "Audio Playback"
                )
                media_title = props.get("media.title") or props.get("media.name") or ""
                desc = props.get("device.description") or props.get("node.description") or ""
                # Filter out PipeSync loopbacks
                if "PipeSync" in app_name or "PipeSync" in desc:
                    continue

                result.append({
                    "id": s.get("id"),
                    "app_name": app_name,
                    "media_title": media_title,
                    "sink_id": s.get("Sink", ""),
                    "corked": s.get("Corked", "no") == "yes",
                    "muted": s.get("Mute", "no") == "yes",
                })
            return result
        except Exception as e:
            logger.debug(f"Error querying active audio streams: {e}")
            return []

    def stop(self):
        """Stops all branches and unloads master sink."""
        logger.info("Stopping PipeSync engine...")
        self.stop_all_branches()
        self.stop_master_sink()
        self._cleanup_orphaned_loopbacks()
        self.active_devices.clear()
        self.is_running = False
