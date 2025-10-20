from __future__ import annotations

"""Tool-specific configuration loaders."""

from pathlib import Path
from importlib.resources import files
import yaml

from pydantic import BaseModel, Field

from ..loader import _resolve_yaml


_DEFAULT_AROMA = files("bidscomatic.config.tools") / "aroma.yaml"
_DEFAULT_FMRIPREP = files("bidscomatic.config.tools") / "fmriprep.yaml"
_DEFAULT_EPI_MASK = files("bidscomatic.config.tools") / "epi_mask.yaml"
_DEFAULT_MCFLIRT = files("bidscomatic.config.tools") / "mcflirt.yaml"


class AromaConfigModel(BaseModel):
    """Pydantic model describing fMRIPost-AROMA defaults."""

    image: str = "nipreps/fmripost-aroma:0.0.12"
    prep_dir: Path = Path("derivatives/fmriprep")
    out_dir: Path = Path("derivatives/fmripost_aroma")
    work_dir: Path = Path("derivatives/work/fmripost_aroma")
    tf_dir: Path = Path("derivatives/templateflow")
    melodic_dim: int | str = -200
    denoising_method: str | None = "nonaggr"
    low_mem: bool = False
    n_procs: int = 1
    mem_mb: int = 16000
    omp_threads: int = 1
    clean_workdir: bool = False
    stop_on_first_crash: bool = False
    extra_args: list[str] = Field(default_factory=list)
    reset_bids_db: bool = False


def _resolve(root: Path | None) -> Path:
    """Return the resolved AROMA configuration path."""
    return _resolve_yaml(None, root, "aroma.yaml", _DEFAULT_AROMA)


def load_aroma_config(root: Path, overrides: dict | None = None) -> AromaConfigModel:
    """Load configuration for fMRIPost-AROMA."""

    overrides = overrides or {}
    path = _resolve(root)
    data = yaml.safe_load(path.read_text()) or {}
    image = data.get("image", "nipreps/fmripost-aroma:0.0.12")
    defaults = data.get("defaults", {})
    # top-level keys override defaults
    merged: dict = {**defaults, **{k: v for k, v in data.items() if k not in {"image", "defaults"}}}
    merged.update({k: v for k, v in overrides.items() if v is not None})
    cfg = AromaConfigModel(image=image, **merged)
    # Resolve relative paths against dataset root
    def _abspath(p: Path) -> Path:
        """Resolve *p* against *root* when relative."""
        return p if p.is_absolute() else (root / p)

    cfg.prep_dir = _abspath(cfg.prep_dir)
    cfg.out_dir = _abspath(cfg.out_dir)
    cfg.work_dir = _abspath(cfg.work_dir)
    cfg.tf_dir = _abspath(cfg.tf_dir)
    return cfg


class FmriprepConfigModel(BaseModel):
    """Pydantic model describing fMRIPrep defaults."""

    image: str = "nipreps/fmriprep:25.1.4"
    data_dir: Path = Path(".")
    out_dir: Path = Path("derivatives/fmriprep")
    work_dir: Path = Path("derivatives/work/fmriprep")
    tf_dir: Path = Path("derivatives/templateflow")
    fs_license: Path = Path("license.txt")
    anat_only: bool = False
    reconall: bool = False
    low_mem: bool = False
    n_procs: int = 1
    mem_mb: int = 16000
    omp_threads: int = 1
    reset_bids_db: bool = False
    extra_args: list[str] = Field(default_factory=list)


def _resolve_fmriprep(root: Path | None) -> Path:
    """Return the resolved fMRIPrep configuration path."""
    return _resolve_yaml(None, root, "fmriprep.yaml", _DEFAULT_FMRIPREP)


def load_fmriprep_config(root: Path, overrides: dict | None = None) -> FmriprepConfigModel:
    """Load configuration for fMRIPrep."""

    overrides = overrides or {}
    path = _resolve_fmriprep(root)
    data = yaml.safe_load(path.read_text()) or {}
    image = data.get("image", "nipreps/fmriprep:25.1.4")
    defaults = data.get("defaults", {})
    merged: dict = {**defaults, **{k: v for k, v in data.items() if k not in {"image", "defaults"}}}
    merged.update({k: v for k, v in overrides.items() if v is not None})
    cfg = FmriprepConfigModel(image=image, **merged)

    def _abspath(p: Path) -> Path:
        """Resolve *p* against *root* when relative."""
        return p if p.is_absolute() else (root / p)

    cfg.data_dir = _abspath(cfg.data_dir)
    cfg.out_dir = _abspath(cfg.out_dir)
    cfg.work_dir = _abspath(cfg.work_dir)
    cfg.tf_dir = _abspath(cfg.tf_dir)
    cfg.fs_license = _abspath(cfg.fs_license)
    return cfg


class EpiMaskConfigModel(BaseModel):
    """Pydantic model describing EPI mask defaults."""

    image: str = "nipreps/fmriprep:25.1.4"
    prep_dir: Path = Path("derivatives/fmriprep")
    low_mem: bool = False
    n_procs: int = 1
    mem_mb: int = 4000
    omp_threads: int = 1
    overwrite: bool = False
    extra_args: list[str] = Field(default_factory=list)


def _resolve_epi_mask(root: Path | None) -> Path:
    """Return the resolved EPI mask configuration path."""
    return _resolve_yaml(None, root, "epi_mask.yaml", _DEFAULT_EPI_MASK)


def load_epi_mask_config(root: Path, overrides: dict | None = None) -> EpiMaskConfigModel:
    """Load configuration for EPI mask generation."""

    overrides = overrides or {}
    path = _resolve_epi_mask(root)
    data = yaml.safe_load(path.read_text()) or {}
    image = data.get("image", "nipreps/fmriprep:25.1.4")
    defaults = data.get("defaults", {})
    merged: dict = {**defaults, **{k: v for k, v in data.items() if k not in {"image", "defaults"}}}
    merged.update({k: v for k, v in overrides.items() if v is not None})
    cfg = EpiMaskConfigModel(image=image, **merged)

    def _abspath(p: Path) -> Path:
        """Resolve *p* against *root* when relative."""
        return p if p.is_absolute() else (root / p)

    cfg.prep_dir = _abspath(cfg.prep_dir)
    return cfg


class McflirtConfigModel(BaseModel):
    """Configuration for FSL MCFLIRT."""

    image: str = "fsl/fsl:6.0.7.5"
    pattern: str = "*_desc-nonaggrDenoised_bold.nii.gz"
    ref: str = "middle"
    width: int = 747
    height: int = 167


def _resolve_mcflirt(root: Path | None) -> Path:
    """Return the resolved MCFLIRT configuration path."""
    return _resolve_yaml(None, root, "mcflirt.yaml", _DEFAULT_MCFLIRT)


def load_mcflirt_config(root: Path, overrides: dict | None = None) -> McflirtConfigModel:
    """Load configuration for MCFLIRT."""

    overrides = overrides or {}
    path = _resolve_mcflirt(root)
    data = yaml.safe_load(path.read_text()) or {}
    image = data.get("image", "fsl/fsl:6.0.7.5")
    defaults = data.get("defaults", {})
    merged: dict = {**defaults, **{k: v for k, v in data.items() if k not in {"image", "defaults"}}}
    merged.update({k: v for k, v in overrides.items() if v is not None})
    cfg = McflirtConfigModel(image=image, **merged)
    return cfg

__all__ = [
    "AromaConfigModel",
    "load_aroma_config",
    "FmriprepConfigModel",
    "load_fmriprep_config",
    "EpiMaskConfigModel",
    "load_epi_mask_config",
    "McflirtConfigModel",
    "load_mcflirt_config",
]
