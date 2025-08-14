from bids_cbrain_runner.utils import paths as paths_mod
from bids_cbrain_runner.utils.paths import (
    build_remote_path,
    infer_derivatives_root_from_steps,
)


def test_file_at_root(monkeypatch):
    monkeypatch.setattr(paths_mod, "load_pipeline_config", lambda: {"derivatives_root": "derivatives"})
    path = ("dataset_description.json",)
    assert build_remote_path(path, True, "/") == "/"


def test_file_inside_derivatives(monkeypatch):
    monkeypatch.setattr(paths_mod, "load_pipeline_config", lambda: {"derivatives_root": "derivatives"})
    path = ("derivatives", "license.txt")
    assert build_remote_path(path, True, "/") == "/"


def test_file_deep_inside_derivatives(monkeypatch):
    monkeypatch.setattr(paths_mod, "load_pipeline_config", lambda: {"derivatives_root": "derivatives"})
    path = (
        "derivatives",
        "fsl",
        "topup",
        "sub-01",
        "ses-01",
        "func",
        "file.nii.gz",
    )
    assert build_remote_path(path, True, "/") == "/"


def test_nested_directories(monkeypatch):
    monkeypatch.setattr(paths_mod, "load_pipeline_config", lambda: {"derivatives_root": "derivatives"})
    path = ("sub-01", "ses-01", "anat")
    assert build_remote_path(path, False, "/") == "/sub-01/ses-01/anat"


def test_roots_section(monkeypatch):
    monkeypatch.setattr(
        paths_mod,
        "load_pipeline_config",
        lambda: {"roots": {"derivatives_root": "outputs"}},
    )
    path = ("outputs", "file.txt")
    assert build_remote_path(path, True, "/") == "/"


def test_strip_derivatives_directory(monkeypatch):
    monkeypatch.setattr(paths_mod, "load_pipeline_config", lambda: {"derivatives_root": "derivatives"})
    path = ("derivatives", "fsl", "lvl1")
    assert build_remote_path(path, False, "/") == "/fsl/lvl1"


def test_strip_derivatives_directory_custom_root(monkeypatch):
    monkeypatch.setattr(
        paths_mod,
        "load_pipeline_config",
        lambda: {"roots": {"derivatives_root": "outputs"}},
    )
    path = ("outputs", "fsl", "lvl1")
    assert build_remote_path(path, False, "/") == "/fsl/lvl1"


def test_strip_nested_derivatives_root(monkeypatch):
    monkeypatch.setattr(
        paths_mod,
        "load_pipeline_config",
        lambda: {"derivatives_root": "derivatives/fsl/level-1/preprocessing_preICA"},
    )
    path = (
        "derivatives",
        "fsl",
        "level-1",
        "preprocessing_preICA",
        "subject",
        "ses",
    )
    assert build_remote_path(path, False, "/") == "/subject/ses"


def test_strip_nested_derivatives_root_file(monkeypatch):
    monkeypatch.setattr(
        paths_mod,
        "load_pipeline_config",
        lambda: {"derivatives_root": "derivatives/fsl/level-1/preprocessing_preICA"},
    )
    path = (
        "derivatives",
        "fsl",
        "level-1",
        "preprocessing_preICA",
        "license.txt",
    )
    assert build_remote_path(path, True, "/") == "/"


def test_infer_derivatives_root_from_steps(monkeypatch):
    monkeypatch.setattr(
        paths_mod,
        "load_pipeline_config",
        lambda: {"derivatives_root": "derivatives"},
    )
    root = infer_derivatives_root_from_steps(
        [
            "derivatives",
            "fsl",
            "level-1",
            "preprocessing_preICA",
            "sub-*",
        ]
    )
    assert root == "derivatives/fsl/level-1/preprocessing_preICA"


def test_infer_derivatives_root_no_match(monkeypatch):
    monkeypatch.setattr(
        paths_mod,
        "load_pipeline_config",
        lambda: {"derivatives_root": "derivatives"},
    )
    root = infer_derivatives_root_from_steps(["sub-*", "ses-01"])
    assert root == "derivatives"


def test_infer_derivatives_root_ignores_filename(monkeypatch):
    monkeypatch.setattr(
        paths_mod,
        "load_pipeline_config",
        lambda: {"derivatives_root": "derivatives"},
    )
    root = infer_derivatives_root_from_steps([
        "derivatives",
        "some",
        "file.txt",
    ])
    assert root == "derivatives/some"


def test_build_remote_path_with_remote_root(monkeypatch):
    monkeypatch.setattr(
        paths_mod,
        "load_pipeline_config",
        lambda: {"derivatives_root": "derivatives/DeepPrep/BOLD"},
    )
    path = ("derivatives", "DeepPrep", "BOLD", "sub-01", "anat")
    res = build_remote_path(path, False, "fmriprep/BOLD")
    assert res == "/fmriprep/BOLD/sub-01/anat"


def test_remap_path_tuple_suffix():
    from bids_cbrain_runner.utils.paths import remap_path_tuple

    original = ("sub-01", "anat")
    mapped = remap_path_tuple(original, {"anat": "ses-01/anat"})
    assert mapped == ("sub-01", "ses-01", "anat")
