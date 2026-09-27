"""
Unit tests for device detector and sync delay calculations
"""

import unittest
from pipesync.device_detector import DeviceDetector
from pipesync.models import AudioDevice
from pipesync.constants import (
    TYPE_BLUETOOTH,
    TYPE_WIRED,
    TYPE_USB,
    TYPE_SPEAKER,
)


class TestDeviceDetector(unittest.TestCase):

    def setUp(self):
        self.detector = DeviceDetector()

    def test_classify_bluetooth_device(self):
        props = {
            "node.description": "Immortal 131",
            "api.bluez5.codec": "sbc",
            "device.bus": "bluetooth",
        }
        dev_type, icon, codec, latency = self.detector.classify_device(props, "bluez_output.A5_C2_52_C5_60_9D.1")
        self.assertEqual(dev_type, TYPE_BLUETOOTH)
        self.assertEqual(codec, "sbc")
        self.assertEqual(latency, 210.0)

    def test_classify_wired_headphones(self):
        props = {
            "node.description": "Built-in Audio Analog Headphones",
            "device.form-factor": "headphone",
        }
        dev_type, icon, codec, latency = self.detector.classify_device(props, "alsa_output.pci-0000_00_1f.3.HiFi__Headphones__sink")
        self.assertEqual(dev_type, TYPE_WIRED)
        self.assertEqual(latency, 5.0)

    def test_calculate_sync_delays_three_devices(self):
        """
        Simulate user setup: 2 wired earphones + 1 Bluetooth earphone.
        """
        wired1 = AudioDevice(
            node_id=1,
            name="alsa_sink.wired1",
            description="Wired Earphone 1 (3.5mm)",
            device_type=TYPE_WIRED,
            hardware_latency_ms=5.0,
        )
        wired2 = AudioDevice(
            node_id=2,
            name="alsa_sink.wired2",
            description="Wired Earphone 2 (USB-C)",
            device_type=TYPE_USB,
            hardware_latency_ms=8.0,
        )
        bluetooth = AudioDevice(
            node_id=3,
            name="bluez_sink.earbuds",
            description="Bluetooth Earbuds (Immortal 131)",
            device_type=TYPE_BLUETOOTH,
            codec="sbc",
            hardware_latency_ms=190.0,
        )

        devices = [wired1, wired2, bluetooth]
        aligned = self.detector.calculate_sync_delays(devices)

        # Bluetooth should have 0 added delay (it's already the slowest)
        self.assertEqual(bluetooth.compensation_delay_ms, 0.0)
        self.assertEqual(bluetooth.total_latency_ms, 190.0)

        # Wired 1 should be delayed by 185.0ms (190 - 5)
        self.assertEqual(wired1.compensation_delay_ms, 185.0)
        self.assertEqual(wired1.total_latency_ms, 190.0)

        # Wired 2 should be delayed by 182.0ms (190 - 8)
        self.assertEqual(wired2.compensation_delay_ms, 182.0)
        self.assertEqual(wired2.total_latency_ms, 190.0)

        # All 3 devices must output sound at the exact same physical moment!
        self.assertEqual(wired1.total_latency_ms, wired2.total_latency_ms)
        self.assertEqual(wired2.total_latency_ms, bluetooth.total_latency_ms)


if __name__ == "__main__":
    unittest.main()
