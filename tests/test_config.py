"""
Unit tests for ConfigManager and device calibration persistence
"""

import unittest
from pipesync.config import ConfigManager


class TestConfigManager(unittest.TestCase):

    def setUp(self):
        self.config = ConfigManager()

    def test_device_delay_persistence(self):
        test_device = "alsa_output.test_headphones"
        self.config.save_device_delay(test_device, 175.5)
        retrieved = self.config.get_calibrated_delay(test_device)
        self.assertEqual(retrieved, 175.5)

    def test_device_volume_persistence(self):
        test_device = "alsa_output.test_headphones"
        self.config.save_device_volume(test_device, 0.85)
        retrieved = self.config.get_saved_volume(test_device)
        self.assertEqual(retrieved, 0.85)


if __name__ == "__main__":
    unittest.main()
