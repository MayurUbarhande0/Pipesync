"""
PipeWire Audio Sink Detection and Device Profiling
"""

import json
import logging
import subprocess
from typing import List, Dict, Optional, Tuple

from pipesync.constants import (
    MASTER_SINK_NAME,
    TYPE_BLUETOOTH,
    TYPE_WIRED,
    TYPE_USB,
    TYPE_HDMI,
    TYPE_SPEAKER,
    TYPE_OTHER,
    DEFAULT_DEVICE_LATENCIES_MS,
    BLUETOOTH_CODEC_LATENCY_MS,
)
from pipesync.models import AudioDevice

logger = logging.getLogger(__name__)


class DeviceDetector:
    """Discovers and classifies audio sinks in the PipeWire graph."""

    def __init__(self):
        pass

    def run_pw_dump(self) -> List[Dict]:
        """Execute pw-dump and return the JSON object tree."""
        try:
            res = subprocess.run(
                ["pw-dump"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            return json.loads(res.stdout)
        except Exception as e:
            logger.error(f"Failed to query pw-dump: {e}")
            return []

    def classify_device(self, node_props: Dict, node_name: str) -> Tuple[str, str, Optional[str], float]:
        """
        Classifies an audio sink into (device_type, icon_name, codec, estimated_latency_ms).
        """
        name_lower = node_name.lower()
        desc_lower = (node_props.get("node.description") or "").lower()
        bus = (node_props.get("device.bus") or "").lower()
        form_factor = (node_props.get("device.form-factor") or "").lower()

        # 1. Bluetooth Check
        if "bluez" in name_lower or bus == "bluetooth" or "bluetooth" in desc_lower:
            codec = node_props.get("api.bluez5.codec")
            if not codec:
                for k, v in node_props.items():
                    if "codec" in k.lower():
                        codec = str(v).lower()
                        break
            
            # Lookup codec latency or fall back to default bluetooth latency
            if codec and codec.lower() in BLUETOOTH_CODEC_LATENCY_MS:
                latency = BLUETOOTH_CODEC_LATENCY_MS[codec.lower()]
            else:
                latency = DEFAULT_DEVICE_LATENCIES_MS[TYPE_BLUETOOTH]

            return TYPE_BLUETOOTH, "bluetooth-active-symbolic", codec, latency

        # 2. USB Audio / DAC
        if bus == "usb" or "usb" in name_lower:
            # Check if it's headphones or speakers
            if "headphone" in desc_lower or "headset" in desc_lower or form_factor in ["headphone", "headset"]:
                return TYPE_USB, "audio-headphones-symbolic", None, DEFAULT_DEVICE_LATENCIES_MS[TYPE_USB]
            return TYPE_USB, "audio-card-symbolic", None, DEFAULT_DEVICE_LATENCIES_MS[TYPE_USB]

        # 3. Wired Headphones / 3.5mm Analog
        if (
            "headphone" in name_lower
            or "headphone" in desc_lower
            or "headset" in desc_lower
            or form_factor in ["headphone", "headset"]
            or "lineout" in desc_lower
            or "earphone" in desc_lower
        ):
            return TYPE_WIRED, "audio-headphones-symbolic", None, DEFAULT_DEVICE_LATENCIES_MS[TYPE_WIRED]

        # 4. HDMI / DisplayPort
        if (
            "hdmi" in name_lower
            or "hdmi" in desc_lower
            or "displayport" in desc_lower
            or "_dp" in name_lower
            or ".dp" in name_lower
            or "dp " in desc_lower
        ):
            return TYPE_HDMI, "video-display-symbolic", None, DEFAULT_DEVICE_LATENCIES_MS[TYPE_HDMI]

        # 5. Built-in Laptop / Desktop Speaker
        if "speaker" in name_lower or "speaker" in desc_lower or form_factor == "speaker" or "internal" in desc_lower:
            return TYPE_SPEAKER, "audio-speakers-symbolic", None, DEFAULT_DEVICE_LATENCIES_MS[TYPE_SPEAKER]

        return TYPE_OTHER, "audio-headphones-symbolic", None, DEFAULT_DEVICE_LATENCIES_MS[TYPE_OTHER]

    def get_audio_sinks(self) -> List[AudioDevice]:
        """Retrieve all physical or external audio sink devices from PipeWire."""
        objects = self.run_pw_dump()
        if not objects:
            return []

        # Find all Audio/Sink nodes
        sink_nodes = {}
        for obj in objects:
            if obj.get("type") == "PipeWire:Interface:Node":
                props = obj.get("info", {}).get("props", {})
                media_class = props.get("media.class")
                node_name = props.get("node.name", "")

                # Exclude our own master sink and temporary loopback streams
                if media_class == "Audio/Sink":
                    if node_name == MASTER_SINK_NAME or "pipesync" in node_name:
                        continue
                    sink_nodes[obj["id"]] = obj

        # Map ports to sink nodes
        sink_ports: Dict[int, List[str]] = {node_id: [] for node_id in sink_nodes}
        for obj in objects:
            if obj.get("type") == "PipeWire:Interface:Port":
                props = obj.get("info", {}).get("props", {})
                node_id = props.get("node.id")
                port_name = props.get("port.name", "")
                direction = obj.get("info", {}).get("direction", "")

                # Only playback input ports for sinks
                if node_id in sink_ports and direction == "input":
                    sink_ports[node_id].append(port_name)

        devices = []
        for node_id, node_obj in sink_nodes.items():
            props = node_obj.get("info", {}).get("props", {})
            node_name = props.get("node.name", f"sink_{node_id}")
            node_desc = props.get("node.description") or props.get("device.description") or node_name

            dev_type, icon_name, codec, base_latency = self.classify_device(props, node_name)

            # Check if PipeWire port has reported latency parameters
            reported_latency_ms = None
            for obj in objects:
                if obj.get("type") == "PipeWire:Interface:Port":
                    p_props = obj.get("info", {}).get("props", {})
                    if p_props.get("node.id") == node_id and obj.get("info", {}).get("direction") == "input":
                        latency_params = obj.get("info", {}).get("params", {}).get("Latency", [])
                        for lat in latency_params:
                            min_ns = lat.get("minNs", 0)
                            if min_ns > 0:
                                reported_latency_ms = min_ns / 1_000_000.0
                                break
                        if reported_latency_ms is not None:
                            break

            final_hw_latency = reported_latency_ms if reported_latency_ms and reported_latency_ms > 0 else base_latency

            # Extract current volume and mute from pactl
            current_vol = 1.0
            is_muted = False
            try:
                v_res = subprocess.run(["pactl", "get-sink-volume", node_name], capture_output=True, text=True, timeout=3)
                for part in v_res.stdout.split("/"):
                    if "%" in part:
                        try:
                            parsed_vol = float(part.replace("%", "").strip()) / 100.0
                            current_vol = max(0.0, min(1.5, parsed_vol))
                        except (ValueError, TypeError):
                            pass
                        break
                m_res = subprocess.run(["pactl", "get-sink-mute", node_name], capture_output=True, text=True, timeout=3)
                if "yes" in m_res.stdout.lower():
                    is_muted = True
            except Exception:
                pass

            device = AudioDevice(
                node_id=node_id,
                name=node_name,
                description=node_desc,
                device_type=dev_type,
                codec=codec,
                hardware_latency_ms=round(final_hw_latency, 1),
                compensation_delay_ms=0.0,
                volume=round(current_vol, 2),
                muted=is_muted,
                enabled=True,
                ports=sink_ports.get(node_id, ["playback_FL", "playback_FR"]),
                icon_name=icon_name,
            )
            devices.append(device)

        # Sort: Bluetooth first, then Wired, USB, HDMI, Speaker
        sort_order = {
            TYPE_BLUETOOTH: 0,
            TYPE_WIRED: 1,
            TYPE_USB: 2,
            TYPE_SPEAKER: 3,
            TYPE_HDMI: 4,
            TYPE_OTHER: 5,
        }
        devices.sort(key=lambda d: (sort_order.get(d.device_type, 99), d.description))

        return devices

    @staticmethod
    def calculate_sync_delays(devices: List[AudioDevice]) -> List[AudioDevice]:
        """
        Calculates the compensation delays needed to align all active devices.
        Formula: Delay_i = Max(HardwareLatency) - HardwareLatency_i
        """
        active_devices = [d for d in devices if d.enabled]
        if not active_devices:
            return devices

        max_latency = max(d.hardware_latency_ms for d in active_devices)

        for dev in devices:
            if dev.enabled:
                dev.compensation_delay_ms = round(max(0.0, max_latency - dev.hardware_latency_ms), 1)
            else:
                dev.compensation_delay_ms = 0.0

        return devices
