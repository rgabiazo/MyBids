"""Utility helpers for CBRAIN file type guessing."""

from __future__ import annotations

import fnmatch
from typing import Mapping

from bids_cbrain_runner.api.config_loaders import load_pipeline_config


def guess_filetype(name: str, cfg: Mapping[str, object] | None = None) -> str:
    """Return the CBRAIN file type for *name* based on pattern rules.

    Args:
        name: Basename or folder name whose type should be inferred.
        cfg: Pipeline configuration dictionary. When ``None``, it is loaded via
            :func:`load_pipeline_config`.

    Returns:
        The guessed CBRAIN filetype. Defaults to the ``fallback`` value from the
        configuration.
    """
    if cfg is None or "filetype_inference" not in cfg:
        cfg = load_pipeline_config()

    inference = cfg.get("filetype_inference", {}) if cfg else {}
    patterns: Mapping[str, str] = inference.get("patterns", {})
    fallback: str = inference.get("fallback", "BidsSubject")

    for pattern, ftype in patterns.items():
        if fnmatch.fnmatch(name, pattern):
            return ftype
    return fallback
