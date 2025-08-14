"""Path helpers for remote SFTP operations."""

from __future__ import annotations

from typing import Mapping, Sequence, Tuple, Dict
from pathlib import Path

from bids_cbrain_runner.api.config_loaders import load_pipeline_config

def infer_derivatives_root_from_steps(
    steps: Sequence[str], cfg: Mapping[str, object] | None = None
) -> str:
    """Return a derivatives root extended by non-wildcard steps.

    Args:
        steps: Wildcard components provided to the upload command.
        cfg: Optional pipeline configuration dictionary. When omitted,
            :func:`load_pipeline_config` is consulted.

    Returns:
        str: The configured ``derivatives_root`` possibly extended with
        constant path components from ``steps``.
    """
    if cfg is None:
        cfg = load_pipeline_config()

    base = get_root("derivatives", cfg) or "derivatives"
    parts = list(Path(base).parts)

    if steps[: len(parts)] != parts:
        # Steps do not start with the configured derivatives root.
        return base

    tail = steps[len(parts) :]
    for idx, comp in enumerate(tail):
        if any(ch in comp for ch in "*?[]"):
            break
        if idx == len(tail) - 1 and "." in comp:
            break
        parts.append(comp)

    return "/".join(parts)

def get_root(name: str, cfg: Mapping[str, object]) -> str | None:
    """Return the configured root directory for *name*.

    Args:
        name: Short root identifier such as ``"derivatives"``.
        cfg: Pipeline configuration mapping.

    Returns:
        str | None: The configured root value when available.
    """
    roots = cfg.get("roots", {}) if cfg else {}
    return roots.get(f"{name}_root") or cfg.get(f"{name}_root")


def build_remote_path(
    path_tuple: Sequence[str],
    is_direct_file: bool,
    derivatives_root: str | None = "/",
    *,
    cfg: Mapping[str, object] | None = None,
) -> str:
    """Return the remote directory path corresponding to ``path_tuple``.

    Args:
        path_tuple: Sequence of path components relative to the dataset root.
        is_direct_file: Whether ``path_tuple`` refers directly to a file rather
            than a directory.
        derivatives_root: Base directory used when ``path_tuple`` is empty. This
            is typically the current working directory of the SFTP connection.
        cfg: Optional pipeline configuration mapping.

    Returns:
        str: Absolute remote path mirroring ``path_tuple`` while handling
        ``derivatives`` special cases for single files.
    """
    if derivatives_root is None:
        derivatives_root = "/"

    if cfg is None:
        cfg = load_pipeline_config()
    deriv_name: str = get_root("derivatives", cfg) or "derivatives"
    deriv_parts = Path(deriv_name).parts

    base = (derivatives_root or "/").rstrip("/")

    if not path_tuple:
        return base or "/"

    parts = list(path_tuple[:-1] if is_direct_file else path_tuple)

    if is_direct_file and parts[: len(deriv_parts)] == list(deriv_parts):
        # Place any single file within the derivatives hierarchy directly at
        # the dataset root rather than reproducing the intermediate
        # sub-directories.
        return base or "/"

    if parts[: len(deriv_parts)] == list(deriv_parts):
        parts = parts[len(deriv_parts) :]

    prefix = base if base.startswith("/") or not base else "/" + base
    if prefix and prefix != "/":
        return prefix + ("/" + "/".join(parts) if parts else "")

    return "/" + "/".join(parts) if parts else "/"


def remap_path_tuple(
    path_tuple: Sequence[str], path_map: Dict[str, str] | None = None
) -> Tuple[str, ...]:
    """Return a new tuple with suffixes replaced according to *path_map*.

    The mapping keys are treated as trailing path components relative to the
    dataset root.  When the joined ``path_tuple`` ends with a given key, that
    suffix is replaced by the corresponding value.  This allows callers to
    insert additional directories on the remote side without modifying the
    local layout.

    Args:
        path_tuple: Original local path components.
        path_map: Dictionary mapping local suffixes to remote replacements.

    Returns:
        Tuple[str, ...]: Modified components after applying the first matching
        replacement. When no mapping applies the original tuple is returned
        unchanged.
    """
    if not path_map:
        return tuple(path_tuple)

    joined = "/".join(path_tuple)
    for src, dst in path_map.items():
        if joined.endswith(src):
            prefix = joined[: len(joined) - len(src)].rstrip("/")
            new_path = f"{prefix}/{dst}" if prefix else dst
            return tuple(p for p in new_path.split("/") if p)
    return tuple(path_tuple)
