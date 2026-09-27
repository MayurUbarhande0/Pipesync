"""
PipeWire Engine Latency & Quantum Optimizer
"""

import logging
import re
import subprocess
from typing import Dict, Any

from pipesync.constants import (
    QUANTUM_PRESETS,
    DEFAULT_QUANTUM,
)
from pipesync.models import OptimizerState

logger = logging.getLogger(__name__)


class PipeWireOptimizer:
    """Manages PipeWire clock, quantum, and low-latency parameters."""

    def __init__(self):
        self._initial_state: OptimizerState = self.get_current_state()

    def get_current_state(self) -> OptimizerState:
        """Queries PipeWire 'settings' metadata for clock and quantum configuration."""
        state = OptimizerState()
        try:
            res = subprocess.run(
                ["pw-metadata", "-n", "settings"],
                capture_output=True,
                text=True,
                check=True,
                timeout=3,
            )
            for line in res.stdout.splitlines():
                if "clock.quantum" in line:
                    match = re.search(r"value:'(\d+)'", line)
                    if match:
                        state.quantum = int(match.group(1))
                elif "clock.force-quantum" in line:
                    match = re.search(r"value:'(\d+)'", line)
                    if match:
                        state.force_quantum = int(match.group(1))
                elif "clock.rate" in line:
                    match = re.search(r"value:'(\d+)'", line)
                    if match:
                        state.rate = int(match.group(1))
                elif "clock.min-quantum" in line:
                    match = re.search(r"value:'(\d+)'", line)
                    if match:
                        state.min_quantum = int(match.group(1))
                elif "clock.max-quantum" in line:
                    match = re.search(r"value:'(\d+)'", line)
                    if match:
                        state.max_quantum = int(match.group(1))

            effective_quantum = state.force_quantum if state.force_quantum > 0 else state.quantum
            if state.rate > 0:
                state.buffer_latency_ms = (effective_quantum / state.rate) * 1000.0
            state.is_low_latency_active = effective_quantum <= 256

        except Exception as e:
            logger.warning(f"Failed to query pw-metadata: {e}")

        return state

    def set_quantum(self, quantum: int, force: bool = False) -> bool:
        """
        Sets the active PipeWire quantum buffer size.
        If force=True, forces all nodes to adhere to this quantum.
        """
        if quantum not in QUANTUM_PRESETS and quantum not in [32, 64, 128, 256, 512, 1024, 2048]:
            logger.error(f"Invalid quantum {quantum}")
            return False

        try:
            # Set clock.quantum
            subprocess.run(
                ["pw-metadata", "-n", "settings", "0", "clock.quantum", str(quantum)],
                check=True,
                capture_output=True,
                timeout=3,
            )

            # Set force-quantum if requested
            force_val = str(quantum) if force else "0"
            subprocess.run(
                ["pw-metadata", "-n", "settings", "0", "clock.force-quantum", force_val],
                check=True,
                capture_output=True,
                timeout=3,
            )

            logger.info(f"Updated PipeWire quantum to {quantum} (forced={force})")
            return True
        except Exception as e:
            logger.error(f"Failed to set PipeWire quantum: {e}")
            return False

    def optimize_for_sharing(self, target_quantum: int = DEFAULT_QUANTUM) -> bool:
        """
        Applies low-latency tuning optimal for multi-device synchronized audio:
        Reduces buffer size down to 256 samples (5.3ms) or 128 samples (2.7ms)
        to minimize internal PipeWire scheduling overhead.
        """
        logger.info(f"Applying low-latency multi-device audio sharing profile ({target_quantum} samples)")
        return self.set_quantum(target_quantum, force=False)

    def restore_defaults(self) -> bool:
        """Restores default quantum settings (1024 samples, unforced)."""
        logger.info("Restoring default PipeWire quantum settings (1024 samples)")
        return self.set_quantum(1024, force=False)
