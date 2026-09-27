"""
Unit tests for data models
"""

import unittest
from pipesync.models import AudioDevice, OptimizerState, SyncProfile
from pipesync.constants import TYPE_BLUETOOTH, TYPE_WIRED


class TestModels(unittest.TestCase):

    def test_audio_device_total_latency(self):
        dev = AudioDevice(
            node_id=10,
            name="test_sink",
            description="Test Sink",
            device_type=TYPE_WIRED,
            hardware_latency_ms=5.0,
            compensation_delay_ms=180.0,
        )
        self.assertEqual(dev.total_latency_ms, 185.0)

    def test_audio_device_serialization(self):
        dev = AudioDevice(
            node_id=42,
            name="bluez_output.test",
            description="Sony WH-1000XM4",
            device_type=TYPE_BLUETOOTH,
            codec="ldac",
            hardware_latency_ms=160.0,
            compensation_delay_ms=0.0,
        )
        data = dev.to_dict()
        restored = AudioDevice.from_dict(data)
        self.assertEqual(restored.node_id, 42)
        self.assertEqual(restored.name, "bluez_output.test")
        self.assertEqual(restored.codec, "ldac")
        self.assertEqual(restored.hardware_latency_ms, 160.0)

    def test_optimizer_state_serialization(self):
        state = OptimizerState(quantum=256, rate=48000, buffer_latency_ms=5.33)
        data = state.to_dict()
        self.assertEqual(data["quantum"], 256)
        self.assertEqual(data["rate"], 48000)
        self.assertEqual(data["buffer_latency_ms"], 5.33)


if __name__ == "__main__":
    unittest.main()
