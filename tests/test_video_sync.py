"""
Unit tests for video player offset calculations
"""

import unittest
from pipesync.video_sync import VideoSyncHelper
from pipesync.models import AudioDevice
from pipesync.constants import TYPE_BLUETOOTH, TYPE_WIRED


class TestVideoSync(unittest.TestCase):

    def test_video_sync_offset_three_devices(self):
        # 2 wired earphones + 1 bluetooth
        wired1 = AudioDevice(
            node_id=1,
            name="wired1",
            description="Wired 1",
            device_type=TYPE_WIRED,
            hardware_latency_ms=5.0,
            compensation_delay_ms=185.0,
        )
        bluetooth = AudioDevice(
            node_id=2,
            name="bt",
            description="Bluetooth Earbuds",
            device_type=TYPE_BLUETOOTH,
            hardware_latency_ms=190.0,
            compensation_delay_ms=0.0,
        )

        devices = [wired1, bluetooth]
        info = VideoSyncHelper.calculate_video_offset(devices)

        self.assertEqual(info["group_latency_ms"], 190.0)
        self.assertEqual(info["player_audio_delay_ms"], -190.0)
        self.assertEqual(info["vlc_setting"], "-190 ms")
        self.assertEqual(info["mpv_setting"], "-0.190")

    def test_video_sync_empty_devices(self):
        info = VideoSyncHelper.calculate_video_offset([])
        self.assertEqual(info["group_latency_ms"], 0.0)
        self.assertEqual(info["player_audio_delay_ms"], 0.0)


if __name__ == "__main__":
    unittest.main()
