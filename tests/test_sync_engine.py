"""
Unit tests for sync engine mechanics
"""

import unittest
from pipesync.sync_engine import SyncEngine
from pipesync.models import AudioDevice
from pipesync.constants import TYPE_WIRED


class TestSyncEngine(unittest.TestCase):

    def setUp(self):
        self.engine = SyncEngine()

    def test_unique_branch_name(self):
        dev = AudioDevice(
            node_id=62,
            name="alsa_output.pci-0000:00:1f.3.HiFi__Speaker__sink",
            description="Speaker",
            device_type=TYPE_WIRED,
        )
        branch_name = self.engine._generate_unique_branch_name(dev)
        self.assertIn("62", branch_name)
        self.assertTrue(branch_name.startswith("pipesync_br_"))

    def test_heal_branches_not_running(self):
        self.assertEqual(self.engine.heal_branches(), 0)

    def test_get_active_audio_streams_type(self):
        streams = self.engine.get_active_audio_streams()
        self.assertIsInstance(streams, list)


if __name__ == "__main__":
    unittest.main()
