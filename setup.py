from setuptools import setup, find_packages

setup(
    name="pipesync",
    version="1.0.0",
    description="Ultra-Low-Latency Multi-Device Audio Sharing & Synchronization for PipeWire & Helvum",
    license="MIT",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "": ["data/*", "data/*.wav", "data/*.desktop"],
    },
    entry_points={
        "console_scripts": [
            "pipesync = pipesync.cli:main",
            "pipesync-gui = pipesync.gui.app:main",
        ],
    },
    python_requires=">=3.8",
)
