"""
Video Player Synchronization Calculator and MPV IPC Integration
"""

import json
import logging
import os
import socket
from typing import List, Optional, Dict
from pipesync.models import AudioDevice

logger = logging.getLogger(__name__)


class VideoSyncHelper:
    """
    Calculates the exact video-audio alignment offset for media players (MPV, VLC)
    when all earphones are synchronized to the slowest device.
    """

    @staticmethod
    def calculate_video_offset(devices: List[AudioDevice]) -> Dict[str, any]:
        """
        Calculates the audio delay needed in media players so that
        the synchronized multi-headphone audio matches video on screen.
        """
        active_devices = [d for d in devices if d.enabled]
        if not active_devices:
            return {
                "group_latency_ms": 0.0,
                "player_audio_delay_ms": 0.0,
                "vlc_setting": "0 ms",
                "mpv_setting": "0.000",
                "explanation": "No active audio devices.",
            }

        # The effective physical latency of the entire synchronized group
        # is the total arrival latency of the slowest device.
        group_latency_ms = max(d.total_latency_ms for d in active_devices)

        # To align audio with video, media player audio must lead (negative delay)
        # or video must lag (positive delay).
        player_audio_delay_ms = -group_latency_ms

        return {
            "group_latency_ms": round(group_latency_ms, 1),
            "player_audio_delay_ms": round(player_audio_delay_ms, 1),
            "vlc_setting": f"{player_audio_delay_ms:.0f} ms",
            "vlc_hotkey": "Press 'j' in VLC to shift audio earlier by 50ms",
            "mpv_setting": f"{player_audio_delay_ms / 1000.0:.3f}",
            "mpv_hotkey": "Press 'Ctrl + -' in MPV to shift audio earlier",
            "explanation": (
                f"All {len(active_devices)} devices are synchronized to {group_latency_ms:.1f}ms. "
                f"To align video with all earphones simultaneously, set audio track delay to "
                f"{player_audio_delay_ms:.0f}ms in your media player."
            ),
        }

    @staticmethod
    def send_mpv_ipc_delay(delay_sec: float, socket_path: str = "/tmp/mpvsocket") -> bool:
        """
        Attempts to send audio-delay command to a running MPV instance via IPC UNIX socket.
        """
        if not os.path.exists(socket_path):
            return False

        try:
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.settimeout(0.2)
            client.connect(socket_path)
            cmd = json.dumps({"command": ["set_property", "audio-delay", delay_sec]}) + "\n"
            client.sendall(cmd.encode("utf-8"))
            client.close()
            logger.info(f"Updated MPV audio-delay to {delay_sec:.3f}s via IPC socket {socket_path}")
            return True
        except Exception as e:
            logger.debug(f"Could not connect to MPV IPC socket: {e}")
            return False
