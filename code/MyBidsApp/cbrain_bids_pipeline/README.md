# cbrain\_bids\_pipeline

> **One-command bridge between a local BIDS dataset and the [CBRAIN](https://github.com/aces/cbrain) neuro‑informatics platform.**
> *Currently ships with first‑class support for **HippUnfold** and **fMRIPrep**; more CBRAIN tools will be added in future minor releases.*

---

## ✨  Highlights

* **BIDS‑aware** – runs the *bids‑validator*, understands sub‑/ses‑hierarchy.
* **Zero‑boilerplate CBRAIN tasks** – discovers `tool_config_id` & `bourreau_id` automatically.
* **SFTP sync helpers** – compare / upload / download only the delta.
* **Config in YAML, secrets in env vars** – opinionated defaults, easy overrides.
* **Pure Python ≥ 3.8** – no compiled extensions; macOS & Linux tested.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Runtime configuration](#runtime-configuration)
  - [YAML files](#yaml-files)
  - [Env-var overrides](#env-var-overrides)
- [Quick-start cheatsheet](#quick-start-cheatsheet)
- [Operational commands](#operational-commands)
  - [Listing resources](#listing-resources)
  - [Uploading](#uploading)
  - [Launching](#launching)
  - [Retrying failed tasks](#retrying-failed-tasks)
  - [Error recovery](#error-recovery)
  - [Downloading](#downloading)
  - [Deleting](#deleting)
- [Python API](#python-api)
- [Troubleshooting](#troubleshooting)
- [Contributing / Development](#contributing--development)
- [Citations & acknowledgements](#citations--acknowledgements)
- [License](#license)
- [Roadmap](#roadmap)

---

## 📋  Prerequisites

| Requirement                                                       | Notes                                                                  |
| ----------------------------------------------------------------- | ---------------------------------------------------------------------- |
| macOS / Linux with Homebrew (macOS) or any modern package manager | On Windows use **WSL 2** and follow the Linux steps inside your distro |
| Python ≥ 3.8 (CPython)                                            | PyPy not supported                                                     |
| Node.js & npm                                                     | Needed to install and run the BIDS Validator                           |
| BIDS Validator                                                    | `npm install -g bids-validator`                                        |
| CBRAIN account                                                    | API token **and** SFTP password must be enabled in your portal profile |

---

## 🚀  Installation

```bash
# clone the monorepo
git clone https://github.com/your-org/MyBids.git
cd MyBids/code/cbrain_bids_pipeline

# (optional) set up a virtual environment in the current directory
python -m venv .venv && source .venv/bin/activate

# install the runner and its companions in editable mode
../dev_install.sh
```

> If you only need the runner itself: `pip install -e bids_cbrain_runner/`.

---

## 🗂️  Runtime configuration

| File               | Purpose                                                     |
|--------------------|-------------------------------------------------------------|
| **`servers.yaml`** | SFTP endpoints & Data-Provider IDs                          |
| **`tools.yaml`**   | Tool-ID ↔ bourreau mapping, versions, skip/keep dirs        |
| **`defaults.yaml`**| Where derivatives land inside the BIDS tree                 |

### YAML files

**`servers.yaml`** – SFTP endpoints & Data-Provider IDs

```yaml
data_providers:
  sftp_1:
    host: ace-cbrain-1.cbrain.mcgill.ca
    port: 7500
    cbrain_id: 51
  sftp_2:
    host: ace-cbrain-2.cbrain.mcgill.ca
    port: 7500
    cbrain_id: 32
```

**`tools.yaml`** – Tool-ID ↔ bourreau mapping, versions, skip/keep dirs

```yaml
tools:
  hippunfold:
    version: "1.3.2"
    default_cluster: beluga
    clusters:
      beluga:
        tool_config_id: 5035
        bourreau_id: 56
    keep_dirs: [config, logs, work]
  fmriprep:
    version: "23.0.2"
    default_cluster: beluga
    clusters:
      beluga:
        tool_config_id: 4538
        bourreau_id: 56
      rorqual:
        tool_config_id: 8909
        bourreau_id: 104
    keep_dirs: [config, logs, work]
```

**`defaults.yaml`** – Where derivatives land inside the BIDS tree

```yaml
cbrain:
  hippunfold:
    hippunfold_output_dir: derivatives/hippunfold
  fmriprep:
    fmriprep_output_dir: derivatives/fmriprep
```


### Env-var overrides

Environment variables **override YAML** – perfect for CI/CD secrets:

```bash
export CBRAIN_USERNAME="alice@example.com"
export CBRAIN_PASSWORD="••••••••"
export CBRAIN_PERSIST=1   # re-write refreshed tokens back to cbrain.yaml
export CBRAIN_TIMEOUT=60  # HTTP request timeout in seconds (defaults to 60)
```

For one-off commands you may also specify the credentials inline:

```bash
CBRAIN_USERNAME=alice@example.com CBRAIN_PASSWORD=•••••••• \
    cbrain-cli --bids-validator sub-* ses-*
```
---

## 🛠️  Quick‑start cheatsheet

| Task                                 | Command |
| ------------------------------------ | --------------------------------------------------------- |
| **Validate** dataset                 | `cbrain-cli --bids-validator sub-* ses-*` |
| **Compare** local vs. remote         | `cbrain-cli --check-bids-and-sftp-files sub-* ses-* anat` |
| **Create project**                   | `cbrain-cli --create-group DemoProject --group-description "test dataset"` |
| **Upload** & register                | [`cbrain-cli --upload-bids-and-sftp-files sub-* --upload-register --upload-dp-id 51`](#uploading) |
| **Preview upload**                   | [`cbrain-cli --upload-bids-and-sftp-files sub-* --upload-dp-id 51 --upload-dry-run`](#uploading) |
| **Launch** HippUnfold on project MyTrial | [`cbrain-cli --launch-tool hippunfold --group-id MyTrial --param modality=T1w`](#launching) |
| **Launch** fMRIPrep on project DemoBids | [`cbrain-cli --launch-tool fmriprep --group-id DemoBids`](#launching) |
| **Launch** DeepPrep on project NeuroPilot | [`cbrain-cli --launch-tool deepprep --group-id NeuroPilot --tool-param bold_task_type=rest`](#launching) |
| **Download** derivatives             | [`cbrain-cli download --tool hippunfold --group MyTrial --flatten --skip-dirs config logs work`](#downloading) |
| **Monitor** a task                   | `cbrain-cli --task-status 456789` |
| **List HippUnfold tasks in a project** | `cbrain-cli --task-status MyTrial --task-type hipp` |
| **Retry a failed task**              | `cbrain-cli --retry-task 456789` |
| **Retry all failed tasks in project** | `cbrain-cli --retry-failed MyTrial` |
| **Retry failed HippUnfold tasks**    | `cbrain-cli --retry-failed MyTrial --task-type hipp` |
| **Delete a userfile**                | [`cbrain-cli --delete-userfile 123 --dry-delete`](#deleting) |
| **Purge filetype from project**      | [`cbrain-cli --delete-group MyTrial --delete-filetype BidsSubject`](#deleting) |
| **Create task alias**               | `cbrain-cli --alias "6cat=assocmemory"` |

When ``--task-status`` receives a number, ``cbrain-cli`` first checks if it
matches an existing project ID. If no such project exists, the value is treated
as a task identifier.

The default `tools.yaml` keeps `config`, `logs` and `work` directories when fetching HippUnfold outputs.  Specifying
`--skip-dirs` overrides this so the listed folders will not be downloaded.

When downloading a single userfile with `--id`, the `--group` option can be omitted.

Use `--task-status <PROJECT>` or `--retry-failed <PROJECT>` together with
`--task-type` to list or retry tasks for a specific CBRAIN tool. The filter
accepts a case-insensitive prefix of the task `type` (e.g. `hipp` matches
`BoutiquesTask::Hippunfold`) or a numeric `tool_config_id`.

Add `--debug-logs` to any command for verbose output.

## ⚙️  Operational commands

### Listing resources

```console
$ cbrain-cli --list-tools
Found 2 tools:
 - ID=500 name='HippUnfold' desc=Hippocampal segmentation
 - ID=501 name='FMRIPrep' desc=Functional preprocessing

$ cbrain-cli --list-tool-bourreaus hippunfold
Configurations for 'hippunfold':
tool_config_id   bourreau_id
--------------   -----------
5035             56

$ cbrain-cli --list-groups
Found 1 group:
 - ID=42 name=DemoProject desc='demo project'

$ cbrain-cli --list-exec-servers
Found 2 execution servers:
 - ID=10 name='ClusterA' online=True read_only=False
 - ID=11 name='ClusterB' online=True read_only=False

$ cbrain-cli --list-userfiles-provider 51
Found 2 userfile(s) on provider 51.
 - ID=2000 name=sub-001_T1w.nii.gz type=BidsSubject group=42

$ cbrain-cli --group-and-provider DemoProject 51
Found 2 userfile(s) in group DemoProject on provider 51.
```

#### Listing userfiles

The `cbrain-cli` tool provides helpers for listing your uploaded files. They
can be invoked directly:

```console
$ cbrain-cli --list-userfiles
Found 8 userfile(s).
 - ID=1234 sub-001/anat/T1w.nii.gz provider=3
 - ID=1235 sub-001/anat/T1w.json provider=3

$ cbrain-cli --list-userfiles-provider 4
Found 2 userfile(s) on provider 4.
 - ID=2000 name=sub-001_task-rest_bold.nii.gz type=BidsSubject group=77

$ cbrain-cli --list-userfiles-group Trial
Found 5 userfile(s) in group Trial.
 - ID=2100 name=sub-001_T1w.nii.gz type=File provider=3

$ cbrain-cli --group-and-provider Trial 4
Found 1 userfile(s) in group Trial on provider 4.
```

---

### Uploading

#### Uploading to another project

CBRAIN userfiles can belong to multiple projects. When uploading files to a
second project, provide the destination project via `--upload-group-id`
(either numeric ID or name):

```bash
cbrain-cli --upload-bids-and-sftp-files sub-* --upload-register \
  --upload-dp-id 51 --upload-group-id 456
```

> **Note** Re-uploading a file with the same name to the same Data Provider is
> skipped. Each provider keeps a single copy per filename—see the later note in
> this README for details.

Already registered files may be reassigned later using
`update_userfile_group_and_move`. The CLI exposes this via
`--modify-file --new-group-id` (ID **or** name):

```bash
cbrain-cli --modify-file --userfile-id 123456 --new-group-id MyProject
```

`update_userfile_group_and_move` will update the project and can optionally
relocate the file when combined with `--move-to-provider`.

---

#### Creating a new CBRAIN project

The CLI can create fresh CBRAIN *groups* (projects) directly from the
command line.  Use `--create-group` with an optional `--group-description`:

```bash
cbrain-cli --create-group "MyTrial" \
               --group-description "test dataset"
```

On success the portal replies with the numeric project ID:

```text
Created group ID=12345 name=MyTrial
```

You can then reference this project (by ID or name) with other commands such as
`--upload-group-id` or `--launch-tool`.

```console
$ cbrain-cli --create-group "DemoProject" --group-description "demo project"
INFO: token retrieved for user@example.com
Created group ID=42 name=DemoProject
```

---


#### Uploading BIDS files

Use `--upload-bids-and-sftp-files` to push data to CBRAIN. The option accepts one or more file globs:

```bash
cbrain-cli --upload-bids-and-sftp-files dataset_description.json \
  --upload-register --upload-dp-id 51 --upload-group-id NewProject
```

```bash
cbrain-cli --upload-bids-and-sftp-files sub-* ses-01 anat \
  --upload-register --upload-dp-id 51 \
  --upload-filetypes BidsSubject \
  --upload-group-id NewProject
```


```console
$ cbrain-cli --upload-bids-and-sftp-files sub-* ses-01 anat \
  --upload-register --upload-dp-id 51 \
  --upload-filetypes BidsSubject \
  --upload-group-id DemoProject
INFO: token retrieved for user@example.com
INFO: Uploaded 6 file(s) to provider 51
INFO: Registered 6 userfile(s) in project DemoProject
```

Missing folders are skipped entirely; if a subject lacks an `anat` directory,
its `func` or `fmap` data won't be uploaded by mistake.
Single files inside a `derivatives/` folder are uploaded directly at the
dataset root (e.g. `derivatives/license.txt` becomes `/license.txt`).

To check what would be synchronised **without** actually transferring files,
append `--upload-dry-run`:

```bash
cbrain-cli --upload-bids-and-sftp-files sub-* ses-01 anat \
  --upload-dp-id 51 --upload-dry-run
```

> **Note**
> Each CBRAIN Data Provider keeps a single copy of any given filename. If the
> target provider already contains a file with the same name, the upload is
> skipped. You can however store identical files on different providers by
> repeating the command with another `--upload-dp-id`.

Example:

```console
$ cbrain-cli --create-group "DemoBids" --group-description "testing"
INFO: token retrieved for alice@example.com
INFO: Created group 'DemoBids' with ID 777
Created group ID=777 name=DemoBids

$ cbrain-cli \
  --upload-bids-and-sftp-files participants.tsv \
  --upload-register \
  --upload-dp-id 51 \
  --upload-group-id DemoBids
INFO: Retrieved new CBRAIN token for user 'alice@example.com'
INFO: Running bids-validator on: /path/to/DemoBids
INFO: BIDS validator passed with no *critical* errors.
INFO: [UPLOAD] Scanning local path: /path/to/DemoBids
INFO: [CHECK] Files present *only locally* (missing on remote /): ['participants.tsv']
INFO: [UPLOAD] Uploading participants.tsv → /participants.tsv
INFO: [UPLOAD] Newly uploaded files (by top-level folder):
Uploaded Summary
{
    "participants.tsv": [
        "participants.tsv"
    ]
}
INFO: [UPLOAD] Registering 1 new userfiles on provider 51…
[SUCCESS] Files registered on provider 51
NOTICE: Registering 1 userfile(s) in background.

$ cbrain-cli \
  --upload-bids-and-sftp-files participants.tsv \
  --upload-register \
  --upload-dp-id 32 \
  --upload-group-id DemoBids
INFO: Retrieved new CBRAIN token for user 'alice@example.com'
INFO: Running bids-validator on: /path/to/DemoBids
INFO: BIDS validator passed with no *critical* errors.
INFO: [UPLOAD] Scanning local path: /path/to/DemoBids
INFO: [CHECK] Files present *only locally* (missing on remote /): ['participants.tsv']
INFO: [UPLOAD] Uploading participants.tsv → /participants.tsv
INFO: [UPLOAD] Newly uploaded files (by top-level folder):
Uploaded Summary
{
    "participants.tsv": [
        "participants.tsv"
    ]
}
INFO: [UPLOAD] Registering 1 new userfiles on provider 32…
[SUCCESS] Files registered on provider 32
NOTICE: Registering 1 userfile(s) in background.
```

#### Uploading derivative files

Add a `.bidsignore` file at the BIDS root so that the validator skips your
`derivatives/` tree:

```bash
echo "derivatives/" >> .bidsignore
```

With this in place you can upload derivative outputs just like raw BIDS files.
Single files are specified with their path components under `derivatives/`:

```bash
cbrain-cli --upload-bids-and-sftp-files derivatives license.txt \
           --upload-register \
           --upload-dp-id 51 \
           --upload-filetypes TextFile \
          --upload-group-id DemoProject
```

To reshape the remote layout, use `--upload-remote-root` to choose the
destination top-level directory and `--upload-path-map` to rewrite trailing
segments.  The following command uploads `derivatives/DeepPrep/BOLD/sub-01`
but moves the `anat` folder under `ses-01` and stores everything beneath
`fmriprep/BOLD` on the SFTP server:

```bash
cbrain-cli --upload-bids-and-sftp-files derivatives DeepPrep BOLD sub-01 \
  --upload-remote-root fmriprep/BOLD \
  --upload-path-map anat=ses-01/anat
```

Wildcards may target subsets of derivative data. The following example uploads
topup‑corrected BOLD runs:

```bash
cbrain-cli --upload-bids-and-sftp-files derivatives fsl topup 'sub-*' ses-01 func '*_desc-topupcorrected_bold.nii.gz' \
  --upload-register \
  --upload-dp-id 51 \
  --upload-filetypes NiftiFile \
  --upload-group-id DemoProject
```

To push an entire directory of derivatives use the folder names followed by the
subject/session pattern:

```bash
cbrain-cli --upload-bids-and-sftp-files derivatives fsl level-1 preprocessing_preICA sub-* ses-01 func \
  --upload-register --upload-dp-id 51 \
  --upload-filetypes File \
  --upload-group-id DemoProject
```

### Launching

Create tasks directly from the CLI with `--launch-tool`. Examples below show
batch and single-userfile launches for **HippUnfold**, **fMRIPrep**, and **DeepPrep**.

#### HippUnfold – batch

```bash
cbrain-cli --launch-tool hippunfold \
    --tool-param modality=T1w \
    --launch-tool-batch-group DemoProject \
    --launch-tool-batch-type BidsSubject \
    --launch-tool-bourreau-id 104 \
    --launch-tool-results-dp-id 51
```

```console
$ cbrain-cli --launch-tool hippunfold \
    --tool-param modality=T1w \
    --launch-tool-batch-group DemoProject \
    --launch-tool-batch-type BidsSubject \
    --launch-tool-bourreau-id 104 \
    --launch-tool-results-dp-id 51
INFO: token retrieved for user@example.com
Task created for 'hippunfold' on cluster 'rorqual':
{
  "id": 123456,
  "type": "BoutiquesTask::Hippunfold",
  ...
}
```

#### HippUnfold – single userfile

```bash
cbrain-cli --launch-tool hippunfold \
    --group-id DemoProject \
    --tool-param interface_userfile_ids=9001 \
    --tool-param subject_dir=9001 \
    --launch-tool-bourreau-id 104 \
    --launch-tool-results-dp-id 51
```

```console
$ cbrain-cli --launch-tool hippunfold \
    --group-id DemoProject \
    --tool-param interface_userfile_ids=9001 \
    --tool-param subject_dir=9001 \
    --launch-tool-bourreau-id 104 \
    --launch-tool-results-dp-id 51
INFO: token retrieved for user@example.com
Task created for 'hippunfold' on cluster 'rorqual':
{
  "id": 123457,
  "type": "BoutiquesTask::Hippunfold",
  ...
}
```

#### fMRIPrep – batch

```bash
cbrain-cli --launch-tool fmriprep \
    --tool-param interface_userfile_ids='[8100]' \
    --tool-param fs_license_file=8100 \
    --tool-param output_spaces='["T1w","MNI152NLin2009cAsym:res-2"]' \
    --launch-tool-batch-group DemoProject \
    --launch-tool-batch-type BidsSubject \
    --launch-tool-bourreau-id 56 \
    --launch-tool-results-dp-id 51
```

```console
$ cbrain-cli --launch-tool fmriprep \
    --tool-param interface_userfile_ids='[8100]' \
    --tool-param fs_license_file=8100 \
    --tool-param output_spaces='["T1w","MNI152NLin2009cAsym:res-2"]' \
    --launch-tool-batch-group DemoProject \
    --launch-tool-batch-type BidsSubject \
    --launch-tool-bourreau-id 56 \
    --launch-tool-results-dp-id 51
INFO: token retrieved for user@example.com
Task created for 'fmriprep' on cluster 'beluga':
{
  "id": 234567,
  "type": "BoutiquesTask::FMRIprepBidsSubject",
  ...
}
```

#### fMRIPrep – single userfile

```bash
cbrain-cli --launch-tool fmriprep \
    --group-id DemoProject \
    --tool-param interface_userfile_ids='[9100,8100]' \
    --tool-param bids_dir=8100 \
    --tool-param fs_license_file=9100 \
    --tool-param output_spaces='["T1w"]' \
    --launch-tool-batch-type BidsSubject \
    --launch-tool-bourreau-id 23 \
    --launch-tool-results-dp-id 51
```

```console
$ cbrain-cli --launch-tool fmriprep \
    --group-id DemoProject \
    --tool-param interface_userfile_ids='[9100,8100]' \
    --tool-param bids_dir=8100 \
    --tool-param fs_license_file=9100 \
    --tool-param output_spaces='["T1w"]' \
    --launch-tool-batch-type BidsSubject \
    --launch-tool-bourreau-id 23 \
    --launch-tool-results-dp-id 51
INFO: token retrieved for user@example.com
Task created for 'fmriprep' on cluster 'cedar':
{
  "id": 234568,
  "type": "BoutiquesTask::FMRIprepBidsSubject",
  ...
}
```

#### fMRIPrep – rorqual

```bash
cbrain-cli --launch-tool fmriprep \
    --group-id DemoProject \
    --tool-param interface_userfile_ids='[9100,8100]' \
    --tool-param bids_dir=8100 \
    --tool-param fs_license_file=9100 \
    --tool-param output_spaces='["T1w"]' \
    --launch-tool-batch-type BidsSubject \
    --launch-tool-bourreau-id 104 \
    --launch-tool-results-dp-id 51
```

```console
$ cbrain-cli --launch-tool fmriprep \
    --group-id DemoProject \
    --tool-param interface_userfile_ids='[9100,8100]' \
    --tool-param bids_dir=8100 \
    --tool-param fs_license_file=9100 \
    --tool-param output_spaces='["T1w"]' \
    --launch-tool-batch-type BidsSubject \
    --launch-tool-bourreau-id 104 \
    --launch-tool-results-dp-id 51
INFO: token retrieved for user@example.com
Task created for 'fmriprep' on cluster 'rorqual':
{
  "id": 234569,
  "type": "BoutiquesTask::FMRIprepBidsSubject",
  ...
}
```

#### DeepPrep – batch

DeepPrep expects BOLD runs whose task label is one of `6cat`, `rest`, `motor`, or `rest motor`. If your files use a different label, create symlinks and update the JSON `TaskName` so that the filenames contain one of these values:

```bash
cd /path/to/sub-123/ses-01/func
for run in 01 02; do
  ln -s sub-123_ses-01_task-mem_dir-AP_run-${run}_bold.nii.gz \
        sub-123_ses-01_task-rest_dir-AP_run-${run}_bold.nii.gz
  jq '.TaskName = "rest"' sub-123_ses-01_task-mem_dir-AP_run-${run}_bold.json \
        > tmp.$$.json && mv tmp.$$.json \
        sub-123_ses-01_task-rest_dir-AP_run-${run}_bold.json
done
```

```bash
cbrain-cli --launch-tool deepprep \
    --launch-tool-batch-group PilotStudy \
    --launch-tool-batch-type BidsSubject \
    --launch-tool-bourreau-id 88 \
    --launch-tool-results-dp-id 42 \
    --tool-param interface_userfile_ids='[8123]' \
    --tool-param fs_license_file=8123 \
    --tool-param bold_task_type=rest \
    --tool-param output_dir_name='{full_noex}-{task_id}'
```

```console
$ cbrain-cli --launch-tool deepprep \\
    --launch-tool-batch-group PilotStudy \\
    --launch-tool-batch-type BidsSubject \\
    --launch-tool-bourreau-id 88 \\
    --launch-tool-results-dp-id 42 \\
    --tool-param interface_userfile_ids='[8123]' \\
    --tool-param fs_license_file=8123 \\
    --tool-param bold_task_type=rest \\
    --tool-param output_dir_name='{full_noex}-{task_id}'
INFO: token retrieved for user@example.com
Task created for 'deepprep' on cluster 'dragon':
{
  "id": 345678,
  "type": "BoutiquesTask::DeepPrep",
  ...
}
```

#### DeepPrep – single userfile

```bash
cbrain-cli --launch-tool deepprep \
    --group-id PilotStudy \
    --tool-param interface_userfile_ids='[8123,8124]' \
    --tool-param bids_dir=8124 \
    --tool-param fs_license_file=8123 \
    --tool-param bold_task_type=rest \
    --tool-param output_dir_name='{full_noex}-{task_id}' \
    --launch-tool-bourreau-id 88 \
    --launch-tool-results-dp-id 42
```

```console
$ cbrain-cli --launch-tool deepprep \\
    --group-id PilotStudy \\
    --tool-param interface_userfile_ids='[8123,8124]' \\
    --tool-param bids_dir=8124 \\
    --tool-param fs_license_file=8123 \\
    --tool-param bold_task_type=rest \\
    --tool-param output_dir_name='{full_noex}-{task_id}' \\
    --launch-tool-bourreau-id 88 \\
    --launch-tool-results-dp-id 42
INFO: token retrieved for user@example.com
Task created for 'deepprep' on cluster 'dragon':
{
  "id": 345679,
  "type": "BoutiquesTask::DeepPrep",
  ...
}
```

> **Note:** DeepPrep tasks may fail on some clusters due to out-of-memory errors. Use `cbrain-cli --error-recover <task_id>` to retry without re-uploading inputs.

Launches can target either a **single userfile** or an entire project. Use
`--group-id PROJECT` together with `--tool-param interface_userfile_ids=UFID`
and `--tool-param subject_dir=UFID` to run on one file. Alternatively,
specify `--launch-tool-batch-group PROJECT` to create one task per matching
userfile. Project references accept numeric IDs or names.

The value passed to `--tool-param fs_license_file` must be the CBRAIN
**userfile ID** of your uploaded `license.txt`. Include this same ID in the
`interface_userfile_ids` list so that fMRIPrep and DeepPrep can mount
the file. DeepPrep also requires `--tool-param bold_task_type` to match the task
label embedded in your BOLD filenames. Use `cbrain-cli --list-userfiles` or the portal to look up
userfile IDs after uploading.

### Retrying failed tasks

Resubmit tasks that ended in an error without re-uploading files.

```bash
# Retry one task by ID
cbrain-cli --retry-task 123456

# Retry all failed tasks in a project
cbrain-cli --retry-failed DemoProject

# Retry only failed HippUnfold tasks in that project
cbrain-cli --retry-failed DemoProject --task-type hipp
```

The optional `--task-type` filter accepts a case-insensitive prefix of the task
type (e.g. `hipp` matches `BoutiquesTask::Hippunfold`) or a numeric
`tool_config_id`.

### Error recovery

If a task ends in a recoverable error state, ask CBRAIN to trigger its built‑in
error recovery logic. This attempts to fix transient issues (e.g. lost network
mounts) without re-uploading inputs or creating a fresh task.

```bash
# Recover a single task by ID
cbrain-cli --error-recover 123456

# Recover every failed or erroring task in a project
cbrain-cli --error-recover-failed DemoProject

# Limit recovery to a particular task type
cbrain-cli --error-recover-failed DemoProject --task-type hippunfold
```

Both commands ignore tasks that are not in a recoverable state.

### Downloading

Retrieve derivatives with `bids-cbrain-cli download`:

```bash
bids-cbrain-cli download --tool hippunfold \
    --output-type HippunfoldOutput --group 42
```
Downloading /sub-001_res-999999-1 → ./derivatives/hippunfold

```console
$ bids-cbrain-cli download --tool hippunfold \
    --output-type HippunfoldOutput --group DemoProject
INFO: token retrieved for user@example.com
Downloading /sub-001_res-123456 → ./derivatives/hippunfold
INFO: Download complete
```

Specify `--id <USERFILE>` to fetch a **single** CBRAIN file and
omit `--group`. Project references given to `--group` work with both the
numeric ID and the project name. The command also understands:

* `--flatten` – remove the extra wrapper directory so outputs land directly
  under the subject/session hierarchy;
* `--skip-dirs <NAME ...>` – ignore unwanted folders such as `logs` or
  `work`.
* `--download-path-map REMOTE=LOCAL` – place a remote directory under a
  different relative path (may be provided multiple times);
* `--normalize session` – ensure filenames inside session folders include
  the session label.
* `--normalize subject` – ensure filenames include the subject label.
* `--normalize session subject` – apply both subject and session labels.

Example directory tree after a flattened download:

```text
derivatives/hippunfold/
└─ sub-001/
   ├─ ses-01/
   │  └─ anat/
   │     └─ sub-001_desc-hippunfold_dseg.nii.gz
   ├─ config/
   ├─ logs/
   └─ work/
```

### Aliasing task names

Duplicate BIDS *task* files with a new label using ``--alias``. The command
creates relative symlinks for non-JSON files and, by default, copies JSON
sidecars while replacing occurrences of ``task-OLD`` inside the file.

```bash
# create assocmemory copies of all task-6cat files
cbrain-cli --alias "6cat=assocmemory"

# restrict to a specific subject/session and link JSON sidecars
cbrain-cli --alias "6cat=assocmemory,sub=002,ses=01,json=link"
```

The flag may be combined with other operations. For instance, run the aliasing
before uploading:

```bash
cbrain-cli --alias "assocmemory=6cat" --upload-bids-and-sftp-files sub-005
```

Or apply it after downloading derivatives:

```bash
cbrain-cli download --tool deepprep \
    --alias derivatives DeepPrep BOLD "6cat=assocmemory" \
    --group DemoProject
```

The optional `sub-*`, `ses-*` and `func` placeholders from earlier versions
are ignored; the alias command automatically descends into the usual
`sub-*/ses-*/func` hierarchy.

### Deleting

Remove unwanted outputs from CBRAIN with the following flags.  Add
`--dry-delete` to preview actions without removing files:

```bash
cbrain-cli --delete-userfile 123
cbrain-cli --delete-group MyTrial --delete-filetype BidsSubject
cbrain-cli --delete-group 12345 --delete-filetype BidsSubject HippunfoldOutput
```

```console
$ cbrain-cli --delete-userfile 2000
INFO: token retrieved for user@example.com
INFO: userfile 2000 deleted

$ cbrain-cli --delete-group DemoProject --delete-filetype HippunfoldOutput
INFO: 2 file(s) removed from project DemoProject
```

These helpers rely on the CBRAIN OpenAPI endpoints for consistent
error handling and authentication.

Deletions return ``HTTP 200`` or ``302``; redirects are not followed
automatically.

---

## 🧩  Python API

```python
from bids_cbrain_runner.commands.tool_launcher import launch_tool
from bids_cbrain_runner.api.config_loaders import load_tools_config

launch_tool(
    base_url="https://portal.cbrain.mcgill.ca",
    token="CBRAIN_API_TOKEN",
    tools_cfg=load_tools_config(),
    tool_name="hippunfold",
    group_id=123,
    extra_params={"modality": "T1w", "subject_dir": "sub-001"},
)
```

---

## Contributing / Development

Install the additional development dependencies and run the checks:

```bash
pytest -c ../pytest.ini -vv           # run unit tests (offline)
ruff check .         # style & lint
pre-commit install   # git hooks
```

---

## Troubleshooting

If a download seems stuck, specify a request timeout via the
`CBRAIN_TIMEOUT` environment variable or the `--timeout` option. The runner
defaults to 60 seconds.

---

## 📚  Citations & acknowledgements

* **DeepPrep** – Ren J., et al. *Nat. Methods.* 2025;22(3):473–476.
* **HippUnfold** – de Kraker L., et al. *eLife* 2023;12\:e82835.
* **fMRIPrep** – Esteban O., et al. *Nat. Methods.* 2019;16(1):111–116.
* **Boutiques** – Glatard T., et al. *GigaScience* 2018;7(5)\:giy016.
* **BIDS** – Gorgolewski K.J., et al. *Sci. Data* 2016;3:160044.
* **CBRAIN** – Sherif T., et al. *Front. Neuroinform.* 2014;8:54. 

We thank the **McGill Centre for Integrative Neuroscience** and **Pierre Rioux** for providing the CBRAIN infrastructure and assistance.

---

## 🔖  License

This repo is MIT‑licensed; generated OpenAPI client code inherits **GPL‑3.0** from the upstream CBRAIN Swagger spec.

---

## Roadmap

*Future roadmap*: add automatic support for **FSL**, **FreeSurfer**, and more CBRAIN tools — stay tuned! ✨
