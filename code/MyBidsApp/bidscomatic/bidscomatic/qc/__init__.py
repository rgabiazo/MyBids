"""Lightweight fMRI quality-control helpers."""

from .metrics import (
    fd_from_confounds,
    fd_power_from_par,
    stream_dvars,
    stream_tsnr,
    load_mask,
)
from .discover import (
    find_bold_files,
    discover_runs,
)
from .report import (
    write_pairwise_csv,
    write_single_csv,
)

__all__ = [
    'fd_from_confounds','fd_power_from_par','stream_dvars','stream_tsnr','load_mask',
    'find_bold_files','discover_runs','write_pairwise_csv','write_single_csv',
]
