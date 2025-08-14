from pathlib import Path

from bids_cbrain_runner.utils import download_utils


class DummySFTP:
    """Minimal stub mimicking Paramiko's SFTPClient."""

    def __init__(self):
        self.get_calls = []

    def get(self, src, dst):
        self.get_calls.append((src, dst))
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        Path(dst).write_text("placeholder")


def test_flattened_download(monkeypatch, tmp_path):
    # Remote tree for one HippUnfold userfile
    tree = {
        "/uf/sub-001_ses-01_hippunfold": (["hippunfold", "logs", "work"], []),
        "/uf/sub-001_ses-01_hippunfold/hippunfold": (["anat"], []),
        "/uf/sub-001_ses-01_hippunfold/hippunfold/anat": ([], ["file.nii.gz"]),
        "/uf/sub-001_ses-01_hippunfold/logs": ([], ["run.log"]),
        "/uf/sub-001_ses-01_hippunfold/work": ([], ["work.txt"]),
    }

    def fake_listdirs(_, path):
        return tree.get(path, ([], []))

    monkeypatch.setattr(download_utils, "list_subdirs_and_files", fake_listdirs)

    sftp = DummySFTP()
    download_utils.flattened_download(
        sftp=sftp,
        remote_dir="/uf/sub-001_ses-01_hippunfold",
        local_root=str(tmp_path),
        tool_name="hippunfold",
        keep_dirs=["logs", "work"],
        wrapper="hippunfold",
    )

    assert (tmp_path / "sub-001" / "ses-01" / "anat" / "file.nii.gz").exists()
    assert (tmp_path / "logs" / "sub-001" / "ses-01" / "run.log").exists()
    assert (tmp_path / "work" / "sub-001" / "ses-01" / "work.txt").exists()
    assert not (tmp_path / "hippunfold").exists()


def test_flattened_download_keepdir_files(monkeypatch, tmp_path):
    """Files at the root of a keep-dir are copied even when subfolders exist."""

    tree = {
        "/uf/sub-001_ses-01_hippunfold": (["hippunfold", "work"], []),
        "/uf/sub-001_ses-01_hippunfold/hippunfold": (["anat"], []),
        "/uf/sub-001_ses-01_hippunfold/hippunfold/anat": ([], ["file.nii.gz"]),
        "/uf/sub-001_ses-01_hippunfold/work": (["sub-001"], ["root.txt"]),
        "/uf/sub-001_ses-01_hippunfold/work/sub-001": (["ses-01"], []),
        "/uf/sub-001_ses-01_hippunfold/work/sub-001/ses-01": ([], ["work.txt"]),
    }

    def fake_listdirs(_, path):
        return tree.get(path, ([], []))

    monkeypatch.setattr(download_utils, "list_subdirs_and_files", fake_listdirs)

    sftp = DummySFTP()
    download_utils.flattened_download(
        sftp=sftp,
        remote_dir="/uf/sub-001_ses-01_hippunfold",
        local_root=str(tmp_path),
        tool_name="hippunfold",
        keep_dirs=["work"],
        wrapper="hippunfold",
    )

    assert (tmp_path / "work" / "sub-001" / "ses-01" / "work.txt").exists()
    assert (tmp_path / "work" / "sub-001" / "ses-01" / "root.txt").exists()


def test_flattened_download_skip_overlaps(monkeypatch, tmp_path):
    """Keep-dirs also listed in skip-dirs should be ignored."""

    tree = {
        "/uf/sub-001_ses-01_hippunfold": (["hippunfold", "config", "logs"], []),
        "/uf/sub-001_ses-01_hippunfold/hippunfold": (["anat"], []),
        "/uf/sub-001_ses-01_hippunfold/hippunfold/anat": ([], ["file.nii.gz"]),
        "/uf/sub-001_ses-01_hippunfold/config": ([], ["settings.yml"]),
        "/uf/sub-001_ses-01_hippunfold/logs": ([], ["run.log"]),
    }

    def fake_listdirs(_, path):
        return tree.get(path, ([], []))

    monkeypatch.setattr(download_utils, "list_subdirs_and_files", fake_listdirs)

    sftp = DummySFTP()
    download_utils.flattened_download(
        sftp=sftp,
        remote_dir="/uf/sub-001_ses-01_hippunfold",
        local_root=str(tmp_path),
        tool_name="hippunfold",
        skip_dirs=["config"],
        keep_dirs=["config", "logs"],
        wrapper="hippunfold",
    )

    assert (tmp_path / "logs" / "sub-001" / "ses-01" / "run.log").exists()
    assert not (tmp_path / "config").exists()


def test_flattened_download_no_wrapper(monkeypatch, tmp_path):
    """Flatten outputs when the remote userfile lacks an explicit wrapper."""

    tree = {
        "/uf/sub-002-2908862": (["logs", "sub-002"], ["dataset_description.json", "CITATION.bib"]),
        "/uf/sub-002-2908862/sub-002": (["ses-01"], []),
        "/uf/sub-002-2908862/sub-002/ses-01": (["anat"], []),
        "/uf/sub-002-2908862/sub-002/ses-01/anat": ([], ["brain.nii.gz"]),
        "/uf/sub-002-2908862/logs": (["20250803"], []),
        "/uf/sub-002-2908862/logs/20250803": ([], ["log.txt"]),
    }

    def fake_listdirs(_, path):
        return tree.get(path, ([], []))

    monkeypatch.setattr(download_utils, "list_subdirs_and_files", fake_listdirs)

    sftp = DummySFTP()
    download_utils.flattened_download(
        sftp=sftp,
        remote_dir="/uf/sub-002-2908862",
        local_root=str(tmp_path),
        tool_name="fmriprep",
        keep_dirs=["logs"],
        skip_files=["dataset_description.json"],
        wrapper="fmriprep",
    )

    assert (tmp_path / "sub-002" / "ses-01" / "anat" / "brain.nii.gz").exists()
    assert (tmp_path / "logs" / "20250803" / "log.txt").exists()
    assert not (tmp_path / "dataset_description.json").exists()
    assert (tmp_path / "CITATION.bib").exists()


def test_flattened_download_subject_dirs(monkeypatch, tmp_path):
    """Keep-dirs can be relocated under the subject hierarchy."""

    tree = {
        "/uf/sub-002-2912033": (["QC", "Recon"], []),
        "/uf/sub-002-2912033/QC": (["sub-002"], ["report.html", "nextflow.run.command"]),
        "/uf/sub-002-2912033/QC/sub-002": ([], ["sub-002.html"]),
        "/uf/sub-002-2912033/Recon": (["fsaverage", "sub-002"], []),
        "/uf/sub-002-2912033/Recon/fsaverage": ([], ["lh.area"]),
        "/uf/sub-002-2912033/Recon/sub-002": (["mri"], []),
        "/uf/sub-002-2912033/Recon/sub-002/mri": ([], ["brain.mgz"]),
    }

    def fake_listdirs(_, path):
        return tree.get(path, ([], []))

    monkeypatch.setattr(download_utils, "list_subdirs_and_files", fake_listdirs)

    sftp = DummySFTP()
    download_utils.flattened_download(
        sftp=sftp,
        remote_dir="/uf/sub-002-2912033",
        local_root=str(tmp_path),
        tool_name="deepprep",
        keep_dirs=["QC", "Recon"],
        subject_dirs=["QC", "Recon"],
        wrapper="deepprep",
    )

    assert (tmp_path / "QC" / "sub-002" / "report.html").exists()
    assert (tmp_path / "QC" / "sub-002" / "nextflow.run.command").exists()
    assert (tmp_path / "QC" / "sub-002" / "sub-002.html").exists()
    assert (tmp_path / "Recon" / "sub-002" / "fsaverage" / "lh.area").exists()
    assert (tmp_path / "Recon" / "sub-002" / "mri" / "brain.mgz").exists()
    assert not (tmp_path / "Recon" / "sub-002" / "sub-002").exists()


def test_flattened_download_subject_dirs_dataset_description(monkeypatch, tmp_path):
    """dataset_description.json in subject-dirs stays at the top level."""

    tree = {
        "/uf/sub-002-2912033": (["QC"], []),
        "/uf/sub-002-2912033/QC": (["sub-002"], ["dataset_description.json"]),
        "/uf/sub-002-2912033/QC/sub-002": ([], ["sub-002.html"]),
    }

    def fake_listdirs(_, path):
        return tree.get(path, ([], []))

    monkeypatch.setattr(download_utils, "list_subdirs_and_files", fake_listdirs)

    sftp = DummySFTP()
    download_utils.flattened_download(
        sftp=sftp,
        remote_dir="/uf/sub-002-2912033",
        local_root=str(tmp_path),
        tool_name="deepprep",
        keep_dirs=["QC"],
        subject_dirs=["QC"],
        wrapper="deepprep",
    )

    assert (tmp_path / "QC" / "dataset_description.json").exists()
    assert not (tmp_path / "QC" / "sub-002" / "dataset_description.json").exists()
    assert (tmp_path / "QC" / "sub-002" / "sub-002.html").exists()


def test_flattened_download_path_map(monkeypatch, tmp_path):
    tree = {
        "/uf/sub-002-2912033": (["BOLD"], []),
        "/uf/sub-002-2912033/BOLD": (["sub-002"], []),
        "/uf/sub-002-2912033/BOLD/sub-002": (["anat"], []),
        "/uf/sub-002-2912033/BOLD/sub-002/anat": ([], ["sub-002_dseg.nii.gz"]),
    }

    def fake_listdirs(_, path):
        return tree.get(path, ([], []))

    monkeypatch.setattr(download_utils, "list_subdirs_and_files", fake_listdirs)

    sftp = DummySFTP()
    download_utils.flattened_download(
        sftp=sftp,
        remote_dir="/uf/sub-002-2912033",
        local_root=str(tmp_path),
        tool_name="deepprep",
        keep_dirs=["BOLD"],
        path_map={"anat": ["ses-01/anat", "ses-02/anat"]},
    )

    assert (tmp_path / "BOLD" / "sub-002" / "ses-01" / "anat" / "sub-002_dseg.nii.gz").exists()
    assert (tmp_path / "BOLD" / "sub-002" / "ses-02" / "anat" / "sub-002_dseg.nii.gz").exists()


def test_flattened_download_path_map_normalize_session(monkeypatch, tmp_path):
    tree = {
        "/uf/sub-002-2912033": (["BOLD"], []),
        "/uf/sub-002-2912033/BOLD": (["sub-002"], []),
        "/uf/sub-002-2912033/BOLD/sub-002": (["anat"], []),
        "/uf/sub-002-2912033/BOLD/sub-002/anat": ([], ["sub-002_dseg.nii.gz"]),
    }

    def fake_listdirs(_, path):
        return tree.get(path, ([], []))

    monkeypatch.setattr(download_utils, "list_subdirs_and_files", fake_listdirs)

    sftp = DummySFTP()
    download_utils.flattened_download(
        sftp=sftp,
        remote_dir="/uf/sub-002-2912033",
        local_root=str(tmp_path),
        tool_name="deepprep",
        keep_dirs=["BOLD"],
        path_map={"anat": ["ses-01/anat", "ses-02/anat"]},
        normalize_session=True,
    )

    assert (
        tmp_path
        / "BOLD"
        / "sub-002"
        / "ses-01"
        / "anat"
        / "sub-002_ses-01_dseg.nii.gz"
    ).exists()
    assert (
        tmp_path
        / "BOLD"
        / "sub-002"
        / "ses-02"
        / "anat"
        / "sub-002_ses-02_dseg.nii.gz"
    ).exists()


def test_flattened_download_normalize_subject(monkeypatch, tmp_path):
    tree = {
        "/uf/sub-001_tool": (["tool"], []),
        "/uf/sub-001_tool/tool": (["anat"], []),
        "/uf/sub-001_tool/tool/anat": ([], ["seg.nii.gz"]),
    }

    def fake_listdirs(_, path):
        return tree.get(path, ([], []))

    monkeypatch.setattr(download_utils, "list_subdirs_and_files", fake_listdirs)

    sftp = DummySFTP()
    download_utils.flattened_download(
        sftp=sftp,
        remote_dir="/uf/sub-001_tool",
        local_root=str(tmp_path),
        tool_name="tool",
        wrapper="tool",
        normalize_subject=True,
    )

    assert (tmp_path / "sub-001" / "anat" / "sub-001_seg.nii.gz").exists()


def test_flattened_download_normalize_session_and_subject(monkeypatch, tmp_path):
    tree = {
        "/uf/sub-001_ses-01_tool": (["tool"], []),
        "/uf/sub-001_ses-01_tool/tool": (["anat"], []),
        "/uf/sub-001_ses-01_tool/tool/anat": ([], ["file.gii"]),
    }

    def fake_listdirs(_, path):
        return tree.get(path, ([], []))

    monkeypatch.setattr(download_utils, "list_subdirs_and_files", fake_listdirs)

    sftp = DummySFTP()
    download_utils.flattened_download(
        sftp=sftp,
        remote_dir="/uf/sub-001_ses-01_tool",
        local_root=str(tmp_path),
        tool_name="tool",
        wrapper="tool",
        normalize_session=True,
        normalize_subject=True,
    )

    assert (
        tmp_path
        / "sub-001"
        / "ses-01"
        / "anat"
        / "sub-001_ses-01_file.gii"
    ).exists()
