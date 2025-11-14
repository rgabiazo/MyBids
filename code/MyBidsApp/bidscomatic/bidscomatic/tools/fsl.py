"""Generic wrapper for FSL container execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from .base import Tool, ToolSpec


@dataclass
class FslConfig:
    """Configuration for running FSL commands in a container."""

    image: str = "fsl/fsl:6.0.7.5"


@dataclass
class FslTool(Tool):
    """Run arbitrary FSL command inside a container."""

    cfg: FslConfig
    command: Sequence[str]
    volumes: Mapping[str, str] = field(default_factory=dict)
    env: Mapping[str, str] = field(default_factory=dict)

    def build_spec(self) -> ToolSpec:  # type: ignore[override]
        """Return the container specification for the configured command."""
        return ToolSpec(self.cfg.image, self.command, self.volumes, self.env)
