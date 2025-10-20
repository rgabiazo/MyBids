"""Wrappers for external preprocessing tools."""

from .base import Tool, ToolSpec
from .aroma import AromaTool, AromaConfig
from .fmriprep import FmriprepTool, FmriprepConfig
from .epi_mask import EpiMaskTool, EpiMaskConfig, run_native as run_epi_mask_native
from .fsl import FslTool, FslConfig
from .mcflirt import McflirtTool, McflirtConfig

__all__ = [
    "Tool",
    "ToolSpec",
    "AromaTool",
    "AromaConfig",
    "FmriprepTool",
    "FmriprepConfig",
    "EpiMaskTool",
    "EpiMaskConfig",
    "run_epi_mask_native",
    "FslTool",
    "FslConfig",
    "McflirtTool",
    "McflirtConfig",
]
