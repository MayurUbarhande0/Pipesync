"""
Helvum Patchbay Wrapper and Graph Topology Bridge
"""

import logging
import os
import shutil
import subprocess
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class HelvumBridge:
    """Manages Helvum patchbay integration, execution, and graph topology visualization."""

    def __init__(self):
        self.helvum_path = shutil.which("helvum")
        self.process: Optional[subprocess.Popen] = None

    @property
    def is_available(self) -> bool:
        """Returns True if the 'helvum' binary is installed."""
        return self.helvum_path is not None

    def is_running(self) -> bool:
        """Checks if Helvum is currently running (either started by us or external)."""
        if self.process and self.process.poll() is None:
            return True
        try:
            res = subprocess.run(["pgrep", "-x", "helvum"], capture_output=True, timeout=1)
            return res.returncode == 0
        except Exception:
            return False

    def launch(self) -> bool:
        """Launches the Helvum patchbay GUI."""
        if not self.is_available:
            logger.error("Helvum is not installed on this system")
            return False

        if self.is_running():
            logger.info("Helvum is already running")
            return True

        try:
            logger.info(f"Launching Helvum from {self.helvum_path}")
            self.process = subprocess.Popen(
                [self.helvum_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to launch Helvum: {e}")
            return False

    def get_pipesync_links(self) -> List[Dict[str, str]]:
        """Queries pw-link to find all active links connecting PipeSync nodes."""
        links = []
        try:
            res = subprocess.run(["pw-link", "-l"], capture_output=True, text=True, timeout=2)
            current_target = None
            for line in res.stdout.splitlines():
                line = line.rstrip()
                if not line:
                    continue
                if line.startswith("  |<- "):
                    source = line[6:].strip()
                    if current_target and ("pipesync" in source or "pipesync" in current_target):
                        links.append({"source": source, "target": current_target})
                elif not line.startswith(" "):
                    current_target = line.strip()
        except Exception as e:
            logger.debug(f"Error querying links: {e}")

        return links
