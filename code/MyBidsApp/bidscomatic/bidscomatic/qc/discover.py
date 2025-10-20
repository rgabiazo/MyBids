"""Helpers for locating BOLD runs and auxiliary files."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import fnmatch
import glob
import os
import re

BOLD_SUFFIXES = (
    "_desc-preproc_bold.nii.gz",
    "_desc-nonaggrDenoised_bold.nii.gz",
    "_bold.nii.gz",
)

MASK_SUFFIXES = (
    "_desc-brain_mask.nii.gz",
    "_brain_mask.nii.gz",
    "_mask.nii.gz",
)

CONFOUNDS_SUFFIX = "_desc-confounds_timeseries.tsv"
PAR_SUFFIX = "_bold_mcf.nii.gz.par"

TOKEN_KEYS = ("sub", "ses", "task", "dir", "run", "acq", "space", "res", "desc")

@dataclass
class BoldRun:
    """Discovered BOLD run with metadata used for QC grouping."""

    label: str
    path: str
    tokens: Dict[str, Optional[str]]
    id_key: Tuple


def parse_tokens_from_bids(name: str) -> Dict[str, Optional[str]]:
    """Extract BIDS entities from a file name."""
    base = os.path.basename(name)
    stem = base.replace(".nii.gz", "").replace(".nii", "")
    tokens: Dict[str, Optional[str]] = {k: None for k in TOKEN_KEYS}
    for key in TOKEN_KEYS:
        m = re.search(rf"_{key}-([^_]+)", stem)
        if m:
            tokens[key] = m.group(1)
    return tokens


def id_key_from_tokens(tokens: Dict[str, Optional[str]]) -> Tuple:
    """Return a tuple key used to group runs for QC pairing."""
    return (
        tokens.get("sub"),
        tokens.get("ses"),
        tokens.get("task"),
        tokens.get("dir"),
        tokens.get("run"),
        tokens.get("acq"),
    )

def find_bold_files(inputs: List[str], recursive: bool, bold_globs: Optional[List[str]]) -> List[str]:
    """Discover BOLD NIfTI files under *inputs* honoring optional globs."""
    paths: List[str] = []

    def add_if_bold(p: str) -> None:
        """Append *p* when it looks like a functional BOLD image."""
        name = os.path.basename(p)
        if name.endswith(".nii.gz") and "_bold" in name and "boldref" not in name:
            paths.append(os.path.abspath(p))

    if bold_globs:
        for pattern in bold_globs:
            for root in inputs:
                target = os.path.join(root, pattern) if os.path.isdir(root) else pattern
                for p in glob.glob(target, recursive=recursive):
                    if os.path.isfile(p):
                        add_if_bold(p)
        return sorted(set(paths))

    for x in inputs:
        if os.path.isfile(x):
            add_if_bold(x)
        elif os.path.isdir(x):
            g = "**/*.nii.gz" if recursive else "*.nii.gz"
            for p in glob.glob(os.path.join(x, g), recursive=recursive):
                if os.path.isfile(p):
                    add_if_bold(p)
        else:
            for p in glob.glob(x, recursive=recursive):
                if os.path.isfile(p):
                    add_if_bold(p)
    return sorted(set(paths))


def classify_label(path: str, pre_tag: str, post_tag: str) -> str:
    """Return ``PRE``, ``POST`` or ``SINGLE`` classification for *path*."""
    name = os.path.basename(path)
    if post_tag in name:
        return "POST"
    if pre_tag in name:
        return "PRE"
    return "SINGLE"


def normalize_res(res: Optional[str]) -> Optional[str]:
    """Return ``res`` with leading zeros stripped, if numeric."""
    if res is None:
        return None
    try:
        return str(int(res))
    except Exception:
        return res


def space_res_pass(path: str, space_filter: Optional[str]) -> bool:
    """Return True if ``path`` matches a ``--space`` filter.

    Comparison ignores leading zeros in resolution fields so that
    ``res-2`` and ``res-02`` are treated as equivalent.
    """
    if not space_filter:
        return True
    tokens = parse_tokens_from_bids(path)
    m_space = re.search(r"([A-Za-z0-9]+)", space_filter)
    m_res = re.search(r"res-(\d+)", space_filter)
    filt_space = m_space.group(1) if m_space else None
    filt_res = normalize_res(m_res.group(1)) if m_res else None
    cand_space = tokens.get("space")
    cand_res = normalize_res(tokens.get("res"))
    if filt_space and cand_space != filt_space:
        return False
    if filt_res and cand_res != filt_res:
        return False
    return True


def task_pass(tokens: Dict[str, Optional[str]], task_filters: Optional[List[str]]) -> bool:
    """Return ``True`` when *tokens* satisfy the task filter list."""
    if not task_filters:
        return True
    tk = tokens.get("task")
    if not tk:
        return False
    for pat in task_filters:
        if fnmatch.fnmatchcase(tk.lower(), pat.lower()):
            return True
    return False


def discover_runs(
    all_paths: List[str],
    pre_tag: str,
    post_tag: str,
    space_filter: Optional[str],
    task_filters: Optional[List[str]],
) -> List[BoldRun]:
    """Construct :class:`BoldRun` objects filtered by task and space."""
    out: List[BoldRun] = []
    for p in all_paths:
        if not space_res_pass(p, space_filter):
            continue
        toks = parse_tokens_from_bids(p)
        if not task_pass(toks, task_filters):
            continue
        lab = classify_label(p, pre_tag, post_tag)
        out.append(BoldRun(label=lab, path=p, tokens=toks, id_key=id_key_from_tokens(toks)))
    return out


def replace_suffix_any(bold_path: str, new_suffixes: Tuple[str, ...]) -> List[str]:
    """Return candidate paths replacing the BOLD suffix with *new_suffixes*."""
    base = os.path.basename(bold_path)
    dirn = os.path.dirname(bold_path)
    stem = base
    for sfx in BOLD_SUFFIXES:
        if base.endswith(sfx):
            stem = base[: -len(sfx)]
            break
    if stem == base and "_bold.nii.gz" in base:
        stem = base.replace("_bold.nii.gz", "")
    return [os.path.join(dirn, stem + ns) for ns in new_suffixes]


def find_mask_for_bold(bold_path: str) -> Optional[str]:
    """Locate a mask file corresponding to *bold_path* if present."""
    for cand in replace_suffix_any(bold_path, MASK_SUFFIXES):
        if os.path.exists(cand):
            return cand
    return None


def find_confounds_for_bold(bold_path: str) -> Optional[str]:
    """Locate the confounds TSV for *bold_path* when available."""
    for cand in replace_suffix_any(bold_path, (CONFOUNDS_SUFFIX,)):
        if os.path.exists(cand):
            return cand
    return None


def find_par_for_bold(bold_path: str) -> Optional[str]:
    """Locate the MCFLIRT ``.par`` file associated with *bold_path*."""
    for cand in replace_suffix_any(bold_path, (PAR_SUFFIX,)):
        if os.path.exists(cand):
            return cand
    return None
