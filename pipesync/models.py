"""
Data models for PipeSync
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pipesync.constants import (
    TYPE_OTHER,
    DEFAULT_DEVICE_LATENCIES_MS,
    DEFAULT_QUANTUM,
)


@dataclass
class AudioDevice:
    """Represents a PipeWire audio sink output device."""
    node_id: int
    name: str
    description: str
    device_type: str = TYPE_OTHER
    codec: Optional[str] = None
    hardware_latency_ms: float = 0.0
    compensation_delay_ms: float = 0.0
    volume: float = 1.0
    muted: bool = False
    enabled: bool = True
    ports: List[str] = field(default_factory=list)
    icon_name: str = "audio-headphones-symbolic"

    @property
    def total_latency_ms(self) -> float:
        """Physical latency (hardware + added compensation delay)."""
        return self.hardware_latency_ms + self.compensation_delay_ms

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "description": self.description,
            "device_type": self.device_type,
            "codec": self.codec,
            "hardware_latency_ms": self.hardware_latency_ms,
            "compensation_delay_ms": self.compensation_delay_ms,
            "volume": self.volume,
            "muted": self.muted,
            "enabled": self.enabled,
            "ports": self.ports,
            "icon_name": self.icon_name,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AudioDevice":
        return cls(
            node_id=data.get("node_id", 0),
            name=data.get("name", ""),
            description=data.get("description", ""),
            device_type=data.get("device_type", TYPE_OTHER),
            codec=data.get("codec"),
            hardware_latency_ms=data.get("hardware_latency_ms", 0.0),
            compensation_delay_ms=data.get("compensation_delay_ms", 0.0),
            volume=data.get("volume", 1.0),
            muted=data.get("muted", False),
            enabled=data.get("enabled", True),
            ports=data.get("ports", []),
            icon_name=data.get("icon_name", "audio-headphones-symbolic"),
        )


@dataclass
class OptimizerState:
    """Current PipeWire engine latency & buffer configuration."""
    quantum: int = DEFAULT_QUANTUM
    force_quantum: int = 0
    rate: int = 48000
    min_quantum: int = 32
    max_quantum: int = 2048
    buffer_latency_ms: float = 5.33
    is_low_latency_active: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "quantum": self.quantum,
            "force_quantum": self.force_quantum,
            "rate": self.rate,
            "min_quantum": self.min_quantum,
            "max_quantum": self.max_quantum,
            "buffer_latency_ms": round(self.buffer_latency_ms, 2),
            "is_low_latency_active": self.is_low_latency_active,
        }


@dataclass
class SyncProfile:
    """Saved profile for a specific group of devices and their calibrated delays."""
    name: str
    delays: Dict[str, float] = field(default_factory=dict)  # device_name -> delay_ms
    quantum: int = DEFAULT_QUANTUM
    video_delay_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "delays": self.delays,
            "quantum": self.quantum,
            "video_delay_ms": self.video_delay_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SyncProfile":
        return cls(
            name=data.get("name", "Default"),
            delays=data.get("delays", {}),
            quantum=data.get("quantum", DEFAULT_QUANTUM),
            video_delay_ms=data.get("video_delay_ms", 0.0),
        )
