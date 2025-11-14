"""Base classes for containerised tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from bidscomatic.engines import ExecutionEngine


@dataclass
class ToolSpec:
    """Specification returned by :class:`Tool.build_spec`.

    Attributes mirror the arguments of :func:`ExecutionEngine.run` for
    convenience.
    """

    image: str
    args: Sequence[str]
    volumes: Mapping[str, str]
    env: Mapping[str, str]
    entrypoint: str | None = None


class Tool:
    """Base class for wrappers around external utilities."""

    def execute(self, engine: ExecutionEngine) -> int:
        """Build a :class:`ToolSpec` and execute it with *engine*."""
        spec = self.build_spec()
        return engine.run(
            spec.image,
            spec.args,
            volumes=spec.volumes,
            env=spec.env,
            entrypoint=spec.entrypoint,
        )

    def build_spec(self) -> ToolSpec:
        """Return a :class:`ToolSpec` describing how to run this tool."""
        raise NotImplementedError
