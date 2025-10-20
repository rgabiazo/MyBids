from pathlib import Path
import shutil
import time

import numpy as np
import pandas as pd
import nibabel as nib
from click.testing import CliRunner

from bidscomatic.cli import main as cli_main


# ---------------------------------------------------------------------------
# Test data builders
# ---------------------------------------------------------------------------

def _setup_ds(root: Path) -> None:
    """Write a minimal dataset description file at the root.

    Args:
        root: Dataset root directory prepared by the test fixture.
    """

    (root / "dataset_description.json").write_text("{}")


def _func_dir(root: Path, sub: str, ses: str | None) -> Path:
    """Ensure the functional directory exists for a subject/session.

    Args:
        root: Dataset root directory prepared by the test fixture.
        sub: Participant label inserted into the path.
        ses: Optional session label inserted into the path.

    Returns:
        Path to the functional directory used by the tests.
    """
    parts = [f"sub-{sub}"]
    if ses:
        parts.append(f"ses-{ses}")
    parts.append("func")
    func = root.joinpath(*parts)
    func.mkdir(parents=True, exist_ok=True)
    return func


def _base_name(
    *,
    sub: str = "001",
    ses: str | None = None,
    task: str = "test",
    dir: str | None = None,
    run: str | None = None,
    space: str | None = None,
    res: str | None = None,
) -> str:
    """Compose a BIDS-compatible filename stem.

    Args:
        sub: Participant label inserted into the stem.
        ses: Optional session label inserted into the stem.
        task: Task label inserted into the stem.
        dir: Optional phase-encoding direction.
        run: Optional run number.
        space: Optional spatial normalization space.
        res: Optional resolution label.

    Returns:
        Filename stem without suffixes.
    """
    tokens = [f"sub-{sub}"]
    if ses:
        tokens.append(f"ses-{ses}")
    tokens.append(f"task-{task}")
    if dir:
        tokens.append(f"dir-{dir}")
    if run:
        tokens.append(f"run-{run}")
    if space:
        tokens.append(f"space-{space}")
    if res:
        tokens.append(f"res-{res}")
    return "_".join(tokens)


def _make_single_run(
    root: Path,
    *,
    sub: str = "001",
    ses: str | None = None,
    task: str = "test",
    dir: str | None = None,
    run: str | None = None,
    desc: str = "preproc",
    shape: tuple[int, int, int, int] = (3, 3, 3, 5),
    mask: bool = True,
    confounds: bool = True,
    par: bool = False,
    confounds_len: int | None = None,
    par_len: int | None = None,
) -> Path:
    """Create a single BOLD run and optional auxiliary files.

    Args:
        root: Dataset root directory prepared by the test fixture.
        sub: Participant label inserted into the file names.
        ses: Optional session label inserted into the file names.
        task: Task label inserted into the file names.
        dir: Optional phase-encoding direction label.
        run: Optional run index label.
        desc: Description label appended to the BOLD file name.
        shape: Image shape used when synthesising the NIfTI data.
        mask: Whether to create a brain mask alongside the BOLD run.
        confounds: Whether to create a confounds TSV.
        par: Whether to create a motion parameter ``.par`` file.
        confounds_len: Override for the confounds row count.
        par_len: Override for the motion parameter row count.

    Returns:
        Path to the functional directory containing the generated files.
    """

    func = _func_dir(root, sub, ses)
    base = _base_name(sub=sub, ses=ses, task=task, dir=dir, run=run)
    bold = func / f"{base}_desc-{desc}_bold.nii.gz"
    data = np.random.rand(*shape).astype("float32")
    nib.save(nib.Nifti1Image(data, affine=np.eye(4)), bold)
    if mask:
        m = func / f"{base}_desc-brain_mask.nii.gz"
        nib.save(nib.Nifti1Image(np.ones(shape[:3], dtype="uint8"), np.eye(4)), m)
    if confounds:
        conf = func / f"{base}_desc-confounds_timeseries.tsv"
        n = confounds_len if confounds_len is not None else shape[3]
        fd = np.linspace(0, 0.4, n)
        pd.DataFrame({"framewise_displacement": fd}).to_csv(conf, sep="\t", index=False)
    if par:
        par_path = func / f"{base}_bold_mcf.nii.gz.par"
        n = par_len if par_len is not None else shape[3]
        mp = np.zeros((n, 6), dtype="float32")
        np.savetxt(par_path, mp)
    return func


def _make_pair_run(
    root: Path,
    *,
    sub: str = "001",
    ses: str | None = "01",
    task: str = "test",
    dir: str | None = None,
    run: str | None = None,
    space: str | None = "MNI152NLin6Asym",
    res: str | None = "02",
    shape: tuple[int, int, int, int] = (2, 2, 2, 5),
) -> Path:
    """Create a pre/post processed pair sharing a mask.

    Args:
        root: Dataset root directory prepared by the test fixture.
        sub: Participant label inserted into the file names.
        ses: Optional session label inserted into the file names.
        task: Task label inserted into the file names.
        dir: Optional phase-encoding direction label.
        run: Optional run index label.
        space: Spatial normalization space used in the file names.
        res: Resolution label used in the file names.
        shape: Image shape used when synthesising the NIfTI data.

    Returns:
        Path to the functional directory containing the generated files.
    """

    func = _func_dir(root, sub, ses)
    base = _base_name(sub=sub, ses=ses, task=task, dir=dir, run=run, space=space, res=res)
    bold_pre = func / f"{base}_desc-preproc_bold.nii.gz"
    bold_post = func / f"{base}_desc-nonaggrDenoised_bold.nii.gz"
    data = np.random.rand(*shape).astype("float32")
    nib.save(nib.Nifti1Image(data, np.eye(4)), bold_pre)
    nib.save(nib.Nifti1Image(data, np.eye(4)), bold_post)
    mask = func / f"{base}_desc-brain_mask.nii.gz"
    nib.save(nib.Nifti1Image(np.ones(shape[:3], dtype="uint8"), np.eye(4)), mask)
    return func


def test_qc_single():
    """Verify QC single behavior."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _setup_ds(root)
        func = _make_single_run(root, ses="01")
        result = runner.invoke(
            cli_main,
            [
                "--bids-root",
                str(root),
                "qc",
                "-i",
                str(func),
                "--calc-dvars",
                "--calc-tsnr",
                "--fd-from",
                "confounds",
            ],
        )
        assert result.exit_code == 0, result.output
        csv_path = Path("qc_single.csv")
        assert csv_path.exists()
        assert "mean_FD_mm" in csv_path.read_text()


def test_qc_writes_at_dataset_root():
    """Verify QC writes AT dataset root behavior."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _setup_ds(root)
        func = _make_single_run(root, ses="01")
        result = runner.invoke(
            cli_main,
            [
                "--bids-root",
                str(root),
                "qc",
                "-i",
                str(func),
                "--fd-from",
                "confounds",
            ],
        )
        assert result.exit_code == 0, result.output
        stem = next(func.glob("*_desc-preproc_bold.nii.gz")).name.replace(".nii.gz", "")
        assert (root / "qc" / func.relative_to(root) / stem).exists()


def test_qc_header_and_inputs(caplog):
    """Verify QC header AND inputs behavior."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _setup_ds(root)
        func = _make_pair_run(root)
        with caplog.at_level("INFO"):
            result = runner.invoke(
                cli_main,
                [
                    "-v",
                    "--bids-root",
                    str(root),
                    "qc",
                    "-i",
                    str(func),
                    "--calc-dvars",
                    "--calc-tsnr",
                    "--pairs-only",
                ],
            )
        assert result.exit_code == 0, result.output
        assert "DVARS | FD | tSNR" in caplog.text
        assert "Found 2 BOLD file(s) in 1 group" in caplog.text
        assert "Inputs:" in caplog.text
        assert "pre :" in caplog.text
        assert "post:" in caplog.text
        assert "Progress" in caplog.text


def test_qc_pair_series_and_overwrite():
    """Ensure per-run series are written and --overwrite recomputes."""

    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _setup_ds(root)
        func = _make_pair_run(root)
        cmd = [
            "--bids-root",
            str(root),
            "qc",
            "-i",
            str(func),
            "--calc-dvars",
            "--calc-tsnr",
            "--pairs-only",
            "--space",
            "MNI152NLin6Asym_res-2",
            "--save-series",
        ]
        # Initial run
        result = runner.invoke(cli_main, cmd)
        assert result.exit_code == 0, result.output
        pair_csv = Path("qc_pairs.csv")
        assert pair_csv.exists()
        pre_stem = next(func.glob("*_desc-preproc_bold.nii.gz")).name.replace(".nii.gz", "")
        dvars_file = root / "qc" / func.relative_to(root) / pre_stem / f"{pre_stem}_dvars.tsv"
        assert dvars_file.exists()
        mtime_csv = pair_csv.stat().st_mtime
        mtime_dvars = dvars_file.stat().st_mtime
        # Second run without --overwrite should skip
        time.sleep(1)
        result2 = runner.invoke(cli_main, cmd)
        assert result2.exit_code == 0, result2.output
        assert pair_csv.stat().st_mtime == mtime_csv
        assert dvars_file.stat().st_mtime == mtime_dvars
        # Third run with --overwrite should update
        time.sleep(1)
        result3 = runner.invoke(cli_main, cmd + ["--overwrite"])
        assert result3.exit_code == 0, result3.output
        assert pair_csv.stat().st_mtime > mtime_csv
        assert dvars_file.stat().st_mtime > mtime_dvars


def test_qc_handles_sessions():
    """Datasets without ``ses`` or with multiple sessions are processed."""

    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _setup_ds(root)
        # sub-001 without session
        _make_single_run(root, sub="001", ses=None)
        # sub-002 with two sessions
        _make_single_run(root, sub="002", ses="01")
        _make_single_run(root, sub="002", ses="02")
        result = runner.invoke(
            cli_main,
            [
                "--bids-root",
                str(root),
                "qc",
                "-i",
                str(root),
                "--recursive",
                "--fd-from",
                "confounds",
            ],
        )
        assert result.exit_code == 0, result.output
        df = pd.read_csv("qc_single.csv")
        assert len(df) == 3


def test_qc_multiple_runs_grouping():
    """Runs with dir/run tokens are grouped separately."""

    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _setup_ds(root)
        func = _make_pair_run(root, dir="AP", run="01")
        _make_pair_run(root, dir="PA", run="02")
        result = runner.invoke(
            cli_main,
            [
                "--bids-root",
                str(root),
                "qc",
                "-i",
                str(func),
                "--calc-dvars",
                "--pairs-only",
                "--space",
                "MNI152NLin6Asym_res-2",
            ],
        )
        assert result.exit_code == 0, result.output
        df = pd.read_csv("qc_pairs.csv")
        assert set(df["id"]) == {"01_test_AP_01", "01_test_PA_02"}


def test_qc_naive_mask_fallback():
    """Verify QC naive mask fallback behavior."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _setup_ds(root)
        func = _make_single_run(root, ses="01", mask=False)
        result = runner.invoke(
            cli_main,
            [
                "--bids-root",
                str(root),
                "qc",
                "-i",
                str(func),
                "--calc-dvars",
                "--allow-naive-mask",
                "--fd-from",
                "confounds",
            ],
        )
        assert result.exit_code == 0, result.output
        assert Path("qc_single.csv").exists()


def test_qc_fd_from_par():
    """Verify QC FD from PAR behavior."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _setup_ds(root)
        func = _make_single_run(root, ses="01", confounds=False, par=True)
        result = runner.invoke(
            cli_main,
            [
                "--bids-root",
                str(root),
                "qc",
                "-i",
                str(func),
                "--fd-from",
                "par",
            ],
        )
        assert result.exit_code == 0, result.output
        df = pd.read_csv("qc_single.csv")
        assert not df["mean_FD_mm"].isnull().any()


def test_qc_mask_shape_mismatch():
    """Verify QC mask shape mismatch behavior."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _setup_ds(root)
        func = _func_dir(root, "001", "01")
        base = _base_name(sub="001", ses="01")
        bold = func / f"{base}_desc-preproc_bold.nii.gz"
        data = np.random.rand(2, 2, 2, 4).astype("float32")
        nib.save(nib.Nifti1Image(data, np.eye(4)), bold)
        mask = func / f"{base}_desc-brain_mask.nii.gz"
        nib.save(nib.Nifti1Image(np.ones((3, 3, 3), dtype="uint8"), np.eye(4)), mask)
        result = runner.invoke(
            cli_main,
            ["--bids-root", str(root), "qc", "-i", str(func)],
        )
        assert result.exit_code != 0
        assert "Mask shape" in result.output


def test_qc_pairs_only_unmatched():
    """Verify QC pairs only unmatched behavior."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _setup_ds(root)
        func = _make_single_run(root, ses="01")  # only PRE
        result = runner.invoke(
            cli_main,
            [
                "--bids-root",
                str(root),
                "qc",
                "-i",
                str(func),
                "--pairs-only",
            ],
        )
        assert result.exit_code == 0, result.output
        assert not Path("qc_pairs.csv").exists()


def test_qc_task_filtering():
    """Verify QC task filtering behavior."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _setup_ds(root)
        func = _make_single_run(root, ses="01", task="memory")
        _make_single_run(root, ses="01", task="rest")
        result = runner.invoke(
            cli_main,
            [
                "--bids-root",
                str(root),
                "qc",
                "-i",
                str(func),
                "--task",
                "mem*",
                "--fd-from",
                "confounds",
            ],
        )
        assert result.exit_code == 0, result.output
        df = pd.read_csv("qc_single.csv")
        assert len(df) == 1
        Path("qc_single.csv").unlink()
        # Mismatched pattern results in no output
        result2 = runner.invoke(
            cli_main,
            [
                "--bids-root",
                str(root),
                "qc",
                "-i",
                str(func),
                "--task",
                "foo",
            ],
        )
        assert result2.exit_code == 0
        assert not Path("qc_single.csv").exists()


def test_qc_mask_reuse_from_pre():
    """Verify QC mask reuse from PRE behavior."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _setup_ds(root)
        func = _make_pair_run(root)
        pre_dir = func
        post_dir = root / "post" / "sub-001" / "ses-01" / "func"
        post_dir.mkdir(parents=True, exist_ok=True)
        post = next(pre_dir.glob("*_desc-nonaggrDenoised_bold.nii.gz"))
        shutil.move(str(post), post_dir / post.name)
        result = runner.invoke(
            cli_main,
            [
                "--bids-root",
                str(root),
                "qc",
                "-i",
                str(pre_dir),
                "-i",
                str(post_dir),
                "--calc-dvars",
                "--pairs-only",
            ],
        )
        assert result.exit_code == 0, result.output
        df = pd.read_csv("qc_pairs.csv")
        assert len(df) == 1


def test_qc_fd_auto_uses_par():
    """Verify QC FD auto uses PAR behavior."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _setup_ds(root)
        func = _make_single_run(root, ses="01", confounds=False, par=True)
        result = runner.invoke(
            cli_main,
            [
                "--bids-root",
                str(root),
                "qc",
                "-i",
                str(func),
                "--fd-from",
                "auto",
            ],
        )
        assert result.exit_code == 0, result.output
        df = pd.read_csv("qc_single.csv")
        assert not df["mean_FD_mm"].isnull().any()


def test_qc_write_tsnr_nifti():
    """Verify QC write tsnr nifti behavior."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _setup_ds(root)
        func = _make_single_run(root, ses="01")
        result = runner.invoke(
            cli_main,
            [
                "--bids-root",
                str(root),
                "qc",
                "-i",
                str(func),
                "--calc-tsnr",
                "--write-tsnr-nifti",
            ],
        )
        assert result.exit_code == 0, result.output
        stem = "sub-001_ses-01_task-test_desc-preproc_bold"
        tsnr_img = root / "qc" / func.relative_to(root) / stem / f"{stem}_desc-tsnr.nii.gz"
        assert tsnr_img.exists()


def test_qc_missing_mask_requires_flag():
    """Verify QC missing mask requires flag behavior."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _setup_ds(root)
        func = _make_single_run(root, ses="01", mask=False)
        result = runner.invoke(
            cli_main,
            [
                "--bids-root",
                str(root),
                "qc",
                "-i",
                str(func),
            ],
        )
        assert result.exit_code != 0
        assert "Mask not found" in str(result.exception)


def test_qc_bold_glob_discovery():
    """Verify QC BOLD glob discovery behavior."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _setup_ds(root)
        func = _make_single_run(root, ses="01")
        result = runner.invoke(
            cli_main,
            [
                "--bids-root",
                str(root),
                "qc",
                "-i",
                str(root),
                "--bold-glob",
                "sub-001/ses-01/func/*_desc-preproc_bold.nii.gz",
                "--calc-dvars",
                "--fd-from",
                "confounds",
            ],
        )
        assert result.exit_code == 0, result.output
        assert Path("qc_single.csv").exists()


def test_qc_missing_fd_warns(caplog):
    """Verify QC missing FD warns behavior."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _setup_ds(root)
        func = _make_single_run(root, ses="01", confounds=False, par=False)
        with caplog.at_level("WARNING"):
            result = runner.invoke(
                cli_main,
                [
                    "--bids-root",
                    str(root),
                    "qc",
                    "-i",
                    str(func),
                ],
            )
        assert result.exit_code == 0, result.output
        assert "fd_missing" in caplog.text
        df = pd.read_csv("qc_single.csv")
        assert df["mean_FD_mm"].isnull().all()


def test_qc_fd_prefers_confounds():
    """Verify QC FD prefers confounds behavior."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _setup_ds(root)
        func = _make_single_run(root, ses="01", confounds=True, par=True)
        result = runner.invoke(
            cli_main,
            ["--bids-root", str(root), "qc", "-i", str(func), "--fd-from", "auto"],
        )
        assert result.exit_code == 0, result.output
        df = pd.read_csv("qc_single.csv")
        # Confounds FD is non-zero, par FD would be zero
        assert (df["mean_FD_mm"] > 0).all()


def test_qc_write_tsnr_requires_calc():
    """Verify QC write tsnr requires calc behavior."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _setup_ds(root)
        func = _make_single_run(root, ses="01")
        result = runner.invoke(
            cli_main,
            ["--bids-root", str(root), "qc", "-i", str(func), "--write-tsnr-nifti"],
        )
        assert result.exit_code != 0
        assert "requires --calc-tsnr" in result.output


def test_qc_save_series_fd_tsnr():
    """Verify QC save series FD tsnr behavior."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _setup_ds(root)
        func = _make_single_run(root, ses="01")
        result = runner.invoke(
            cli_main,
            [
                "--bids-root",
                str(root),
                "qc",
                "-i",
                str(func),
                "--calc-dvars",
                "--calc-tsnr",
                "--save-series",
            ],
        )
        assert result.exit_code == 0, result.output
        stem = "sub-001_ses-01_task-test_desc-preproc_bold"
        qc_dir = root / "qc" / func.relative_to(root) / stem
        assert (qc_dir / f"{stem}_dvars.tsv").exists()
        assert (qc_dir / f"{stem}_fd.tsv").exists()
        assert (qc_dir / f"{stem}_tsnr.tsv").exists()


def test_qc_fd_length_mismatch():
    """Verify QC FD length mismatch behavior."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _setup_ds(root)
        func = _make_single_run(root, ses="01", confounds=True, par=False, confounds_len=2)
        result = runner.invoke(
            cli_main,
            ["--bids-root", str(root), "qc", "-i", str(func)],
        )
        assert result.exit_code != 0
        assert "FD series length" in result.output


def test_qc_single_volume_tsnr_nan():
    """Verify QC single volume tsnr NAN behavior."""
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _setup_ds(root)
        func = _make_single_run(root, ses="01", shape=(3, 3, 3, 1))
        result = runner.invoke(
            cli_main,
            ["--bids-root", str(root), "qc", "-i", str(func), "--calc-tsnr"],
        )
        assert result.exit_code == 0, result.output
        df = pd.read_csv("qc_single.csv")
        assert df["tSNR_mean"].isnull().all()
