import re
from pathlib import Path

from setuptools import setup, find_packages


def read_version():
    init_file = Path(__file__).parent / "pipesync" / "__init__.py"
    match = re.search(
        r'^__version__\s*=\s*"([^"]+)"',
        init_file.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    if not match:
        raise RuntimeError("Could not determine package version")
    return match.group(1)

setup(
    name="pipesync",
    version=read_version(),
    description="Ultra-Low-Latency Multi-Device Audio Sharing & Synchronization for PipeWire & Helvum",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "": ["data/*", "data/*.wav", "data/*.desktop"],
    },
    data_files=[
        ("share/applications", ["data/org.pipewire.PipeSync.desktop"]),
    ],
    entry_points={
        "console_scripts": [
            "pipesync = pipesync.cli:main",
            "pipesync-gui = pipesync.gui.app:main",
        ],
    },
    python_requires=">=3.8",
)
