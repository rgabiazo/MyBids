from __future__ import annotations

"""Execution back-ends for running containerised tools."""

from abc import ABC, abstractmethod
from typing import Mapping, Sequence


class ExecutionEngine(ABC):
    """Abstract execution engine.

    Concrete implementations launch processes (e.g., Docker, Singularity)
    that run external neuroimaging tools.  The interface is intentionally
    small so that new engines can be added without touching call sites.
    """

    @abstractmethod
    def run(
        self,
        image: str,
        args: Sequence[str],
        *,
        volumes: Mapping[str, str],
        env: Mapping[str, str],
        entrypoint: str | None = None,
    ) -> int:
        """Run *image* with *args*.

        Args:
            image: Container image identifier.
            args: Command line arguments passed to the image.
            volumes: Mapping of host paths → guest mount points.
            env: Environment variables visible inside the container.
            entrypoint: Optional process entrypoint overriding the image default.

        Returns:
            Process return code.
        """
        raise NotImplementedError
