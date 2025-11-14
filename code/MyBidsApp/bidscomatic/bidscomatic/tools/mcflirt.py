"""Tool wrapper for FSL MCFLIRT."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from .base import Tool, ToolSpec


@dataclass
class McflirtConfig:
    """Configuration for MCFLIRT container execution."""

    image: str = "fsl/fsl:6.0.7.5"
    in_file: Path | None = None
    out_dir: Path | None = None
    ref: str = "middle"
    extra_args: Sequence[str] = field(default_factory=list)


class McflirtTool(Tool):
    """Build a container spec to run MCFLIRT."""

    def __init__(self, cfg: McflirtConfig):
        """Store the configuration object."""
        self.cfg = cfg

    def build_spec(self) -> ToolSpec:  # type: ignore[override]
        """Return the container spec for MCFLIRT."""
        if self.cfg.in_file is None or self.cfg.out_dir is None:
            raise ValueError("in_file and out_dir must be specified")
        vols = {
            str(self.cfg.in_file.parent): "/data:ro",
            str(self.cfg.out_dir): "/out",
        }
        args = [
            "mcflirt",
            "-in",
            f"/data/{self.cfg.in_file.name}",
            "-out",
            "/out/prefiltered_func_data_mcf",
        ]
        args.extend(self.cfg.extra_args)
        return ToolSpec(self.cfg.image, args, vols, {})
