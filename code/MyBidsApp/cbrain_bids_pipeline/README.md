# cbrain_bids_pipeline

> **One-command bridge between a local BIDS dataset and the [CBRAIN](https://github.com/aces/cbrain) neuro‑informatics platform.**  
> *Ships with first‑class support for **HippUnfold**, **fMRIPrep**, and **DeepPrep**; more CBRAIN tools will be added in future minor releases.*

---

## Contents

- [Overview](#overview)
- [Highlights](#highlights)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
  - [YAML files](#yaml-files)
  - [Environment variables](#environment-variables)
- [Quick‑start cheatsheet](#quick-start-cheatsheet)
- [CLI Usage](#cli-usage)
  - [Listing resources](#listing-resources)
  - [Creating a new CBRAIN project](#creating-a-new-cbrain-project)
  - [Uploading](#uploading)
  - [Launching tasks](#launching-tasks)
  - [Monitoring & retrying](#monitoring--retrying)
  - [Error recovery](#error-recovery)
  - [Downloading](#downloading)
  - [Aliasing task names](#aliasing-task-names)
  - [Deleting](#deleting)
- [Python API](#python-api)
- [Troubleshooting](#troubleshooting)
- [Contributing / Development](#contributing--development)
- [Citations & acknowledgements](#citations--acknowledgements)
- [License](#license)
- [Roadmap](#roadmap)

---

## Overview

This CLI and Python helper connect a local, BIDS‑structured dataset to CBRAIN. It validates your BIDS tree, syncs it to data providers via SFTP, registers files, launches BIDS‑aware tools on specific clusters, monitors/retries tasks, and downloads derivatives into your `derivatives/` tree.

---

## Highlights

- **BIDS‑aware** – runs the *bids‑validator*; understands `sub-*/ses-*` hierarchy.
- **Zero‑boilerplate CBRAIN tasks** – discovers `tool_config_id` & `bourreau_id` automatically.
- **SFTP sync helpers** – compare / upload / download only the delta.
- **Config in YAML, secrets in env vars** – opinionated defaults; easy overrides.
- **Pure Python ≥ 3.8** – no compiled extensions; macOS & Linux tested.

> **Terminology.** In CBRAIN, *projects* are called **groups**. Most commands accept either a numeric ID or a project/group **name**.

---

## Prerequisites

| Requirement                                                       | Notes                                                                  |
| ----------------------------------------------------------------- | ---------------------------------------------------------------------- |
| macOS / Linux with Homebrew (macOS) or a modern package manager   | On Windows use **WSL 2** and follow the Linux steps inside your distro |
| Python ≥ 3.8 (CPython)                                            | PyPy not supported                                                     |
| Node.js & npm                                                     | Needed to install and run the BIDS Validator                           |
| BIDS Validator                                                    | `npm install -g bids-validator`                                        |
| CBRAIN account                                                    | API token **and** SFTP password enabled in your portal profile         |

---

## Installation

Clone the repo:

```bash
git clone https://github.com/rgabiazo/MyBids.git
cd MyBids/code/MyBidsApp/cbrain_bids_pipeline
```

Create and activate a virtual environment (optional but recommended):

```bash
python -m venv .venv && source .venv/bin/activate
# (Windows PowerShell): .\.venv\Scripts\Activate.ps1
```

Install the runner and companions (choose one):

```bash
# A) Local editable install (subdir)
pip install -e bids_cbrain_runner/
```

```bash
# B) Dev helper from repo root (if available)
# from repo root: ./code/dev_install.sh
# from this folder: ../../dev_install.sh
```

> If you only need the runner itself: `pip install -e bids_cbrain_runner/`.

---

## Configuration

Three YAML files drive runtime behavior.

| File               | Purpose                                                     |
|--------------------|-------------------------------------------------------------|
| **`servers.yaml`** | SFTP endpoints & Data‑Provider IDs                          |
| **`tools.yaml`**   | Tool ↔ bourreau mapping, versions, skip/keep dirs           |
| **`defaults.yaml`**| Where derivatives land inside the BIDS tree                 |

### YAML files

**`servers.yaml`** – SFTP endpoints & Data‑Provider IDs

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

**`tools.yaml`** – Tool ↔ bourreau mapping, versions, skip/keep dirs

```yaml
tools:
  hippunfold:
    version: "1.3.2"
    default_cluster: beluga
    clusters:
      beluga:   { tool_config_id: 5035, bourreau_id: 56 }
      cedar:    { tool_config_id: 5032, bourreau_id: 23 }
      rorqual:  { tool_config_id: 8954, bourreau_id: 104 }
    keep_dirs: [config, logs, work]

  FMRIprepBidsSubject:
    version: "23.0.2"
    default_cluster: beluga
    clusters:
      beluga:   { tool_config_id: 4538,  bourreau_id: 56 }
      cedar:    { tool_config_id: 4532,  bourreau_id: 23 }
      fir:      { tool_config_id: 10658, bourreau_id: 110 }
      rorqual:  { tool_config_id: 8909,  bourreau_id: 104 }
    keep_dirs: [config, logs, work]

  deepprep:
    version: "24.1.2"
    default_cluster: rorqual
    clusters:
      fir:      { tool_config_id: 10697, bourreau_id: 110 }
      nibi:     { tool_config_id: 9920,  bourreau_id: 107 }
      rorqual:  { tool_config_id: 8894,  bourreau_id: 104 }
    keep_dirs: [BOLD, QC, Recon, WorkDir]
```

**`defaults.yaml`** – Where derivatives land inside the BIDS tree

```yaml
cbrain:
  hippunfold:
    hippunfold_output_dir: derivatives/hippunfold
  FMRIprepBidsSubject:
    FMRIprepBidsSubject_output_dir: derivatives/fmriprep
```

### Environment variables

Environment variables **override YAML**—ideal for CI/CD and secrets:

```bash
export CBRAIN_USERNAME="alice@example.com"
export CBRAIN_PASSWORD="••••••••"
export CBRAIN_PERSIST=1   # write refreshed tokens back to cbrain.yaml
export CBRAIN_TIMEOUT=60  # HTTP request timeout in seconds (default 60)
```

For one‑off commands you can also inline credentials:

```bash
CBRAIN_USERNAME=alice@example.com CBRAIN_PASSWORD=•••••••• \
  cbrain-cli --bids-validator sub-* ses-*
```

---

## Quick‑start cheatsheet

| Task                                                                                  | Command                                                                                        |
| ------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| **Validate** dataset                                                                  | `cbrain-cli --bids-validator sub-* ses-*`                                                      |
| **Compare** local vs. remote                                                          | `cbrain-cli --check-bids-and-sftp-files sub-* ses-* anat`                                      |
| **Create project**                                                                    | `cbrain-cli --create-group DemoProject --group-description "test dataset"`                     |
| **Create** local task alias                                                           | `cbrain-cli --alias "6cat=assocmemory"`                                                        |
| **Enable** verbose logs *(append to any command)*                                     | `cbrain-cli --debug-logs`                                                                      |
| **Preview upload (dry‑run)**                                                          | `cbrain-cli --upload-bids-and-sftp-files sub-* --upload-dp-id 51 --upload-dry-run`             |
| **Upload** & register                                                                 | `cbrain-cli --upload-bids-and-sftp-files sub-* --upload-register --upload-dp-id 51`            |
| **Launch** HippUnfold on project *MyTrial*                                            | `cbrain-cli --launch-tool hippunfold --group-id MyTrial --param modality=T1w`                  |
| **Launch** fMRIPrep on project *DemoBids*                                             | `cbrain-cli --launch-tool FMRIprepBidsSubject --group-id DemoBids`                             |
| **Launch** DeepPrep on project *NeuroPilot*                                           | `cbrain-cli --launch-tool deepprep --group-id NeuroPilot --tool-param bold_task_type=rest`     |
| **Monitor** a task *(numeric IDs: checked as **project ID** first, else **task ID**)* | `cbrain-cli --task-status 456789`                                                              |
| **List** HippUnfold tasks in a project                                                | `cbrain-cli --task-status MyTrial --task-type hipppunfold`                                     |
| **Retry** a failed task                                                               | `cbrain-cli --retry-task 456789`                                                               |
| **Retry** all failed tasks in project                                                 | `cbrain-cli --retry-failed MyTrial`                                                            |
| **Retry** failed HippUnfold tasks                                                     | `cbrain-cli --retry-failed MyTrial --task-type hippunfold`                                     |
| **Recover** all failed on cluster HippUnfold tasks in a project                       | `cbrain-cli --error-recover-failed DemoProject --task-type hippunfold`                         |
| **Download** derivatives                                                              | `cbrain-cli download --tool hippunfold --group MyTrial --flatten --skip-dirs config logs work` |
| **Delete** a userfile                                                                 | `cbrain-cli --delete-userfile 123 --dry-delete`                                                |
| **Purge** filetype from project                                                       | `cbrain-cli --delete-group MyTrial --delete-filetype BidsSubject`                              |

---

## CLI Usage

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
Found 5 execution servers:
 - ID=56 name='beluga' online=True read_only=False
 - ID=23 name='cedar'  online=True read_only=False
 - ID=110 name='fir'   online=True read_only=False
 - ID=107 name='nibi'  online=True read_only=False
 - ID=104 name='rorqual' online=True read_only=False

$ cbrain-cli --list-userfiles-provider 51
Found 2 userfile(s) on provider 51.
 - ID=2000 name=sub-001_T1w.nii.gz type=BidsSubject group=42

$ cbrain-cli --group-and-provider DemoProject 51
Found 2 userfile(s) in group DemoProject on provider 51.
```

#### Listing userfiles

```console
$ cbrain-cli --list-userfiles
Found 8 userfile(s).
 - ID=1234 sub-001/anat/T1w.nii.gz provider=3
 - ID=1235 sub-001/anat/T1w.json   provider=3

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

### Creating a new CBRAIN project

```bash
cbrain-cli --create-group "MyTrial" \
  --group-description "test dataset"
```

On success:

```text
Created group ID=12345 name=MyTrial
```

You can then reference this project (by **ID or name**) with other commands such as `--upload-group-id` or `--launch-tool`:

```console
$ cbrain-cli --create-group "DemoProject" --group-description "demo project"
INFO: token retrieved for user@example.com
Created group ID=42 name=DemoProject
```

---

### Uploading

#### Uploading to another project

CBRAIN userfiles can belong to multiple projects. When uploading to a second project, provide the destination via `--upload-group-id` (ID or name):

```bash
cbrain-cli --upload-bids-and-sftp-files sub-* --upload-register \
  --upload-dp-id 51 --upload-group-id 456
```

> **Note** Re‑uploading a file with the same name to the **same** Data Provider is skipped; each provider keeps a single copy per filename.

Reassign already registered files later with `update_userfile_group_and_move`:

```bash
cbrain-cli --modify-file --userfile-id 123456 --new-group-id MyProject
```

Optionally relocate the file when combined with `--move-to-provider`.

---

#### Upload BIDS files

Use `--upload-bids-and-sftp-files` with one or more file globs:

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

Missing folders are skipped entirely. Single files inside `derivatives/` are uploaded at the dataset root (e.g., `derivatives/license.txt` → `/license.txt`).

**Dry run** without transferring files:

```bash
cbrain-cli --upload-bids-and-sftp-files sub-* ses-01 anat \
  --upload-dp-id 51 --upload-dry-run
```

Example uploading the same file to two different providers:

```console
$ cbrain-cli \
  --upload-bids-and-sftp-files participants.tsv \
  --upload-register \
  --upload-dp-id 51 \
  --upload-group-id DemoBids
...
$ cbrain-cli \
  --upload-bids-and-sftp-files participants.tsv \
  --upload-register \
  --upload-dp-id 32 \
  --upload-group-id DemoBids
...
```

---

#### Upload derivative files

Ignore `derivatives/` during validation:

```bash
echo "derivatives/" >> .bidsignore
```

Upload specific derivative files:

```bash
cbrain-cli --upload-bids-and-sftp-files derivatives license.txt \
  --upload-register --upload-dp-id 51 \
  --upload-filetypes TextFile \
  --upload-group-id DemoProject
```

Reshape remote layout:

```bash
cbrain-cli --upload-bids-and-sftp-files derivatives DeepPrep BOLD sub-01 \
  --upload-remote-root fmriprep/BOLD \
  --upload-path-map anat=ses-01/anat
```

Wildcards for subsets (e.g., topup‑corrected BOLD):

```bash
cbrain-cli --upload-bids-and-sftp-files derivatives fsl topup 'sub-*' ses-01 func '*_desc-topupcorrected_bold.nii.gz' \
  --upload-register --upload-dp-id 51 \
  --upload-filetypes NiftiFile \
  --upload-group-id DemoProject
```

Upload an entire derivatives folder:

```bash
cbrain-cli --upload-bids-and-sftp-files derivatives fsl level-1 preprocessing_preICA sub-* ses-01 func \
  --upload-register --upload-dp-id 51 \
  --upload-filetypes File \
  --upload-group-id DemoProject
```

---

### Launching tasks

Create tasks directly with `--launch-tool`. The examples show **batch** and **single‑userfile** launches for **HippUnfold**, **fMRIPrep**, and **DeepPrep**.

#### HippUnfold — batch

```bash
cbrain-cli --launch-tool hippunfold \
  --tool-param modality=T1w \
  --launch-tool-batch-group DemoProject \
  --launch-tool-batch-type BidsSubject \
  --launch-tool-bourreau-id 104 \
  --launch-tool-results-dp-id 51
```

```console
INFO: token retrieved for user@example.com
Task created for 'hippunfold' on cluster 'rorqual':
{
  "id": 123456,
  "type": "BoutiquesTask::Hippunfold",
  ...
}
```

#### HippUnfold — single userfile

```bash
cbrain-cli --launch-tool hippunfold \
  --group-id DemoProject \
  --tool-param interface_userfile_ids=9001 \
  --tool-param subject_dir=9001 \
  --launch-tool-bourreau-id 104 \
  --launch-tool-results-dp-id 51
```

```console
INFO: token retrieved for user@example.com
Task created for 'hippunfold' on cluster 'rorqual':
{
  "id": 123457,
  "type": "BoutiquesTask::Hippunfold",
  ...
}
```

#### fMRIPrep — batch

```bash
cbrain-cli --launch-tool FMRIprepBidsSubject \
  --tool-param interface_userfile_ids='[7201]' \
  --tool-param fs_license_file=7201 \
  --tool-param output_spaces='["MNI152NLin6Asym","MNI152NLin2009cAsym:res-2"]' \
  --tool-param anat_only=true \
  --tool-param low_mem=true \
  --tool-param no_reconall=true \
  --launch-tool-batch-group BrainProject \
  --launch-tool-batch-type BidsSubject \
  --launch-tool-bourreau-id 110 \
  --launch-tool-results-dp-id 51
```

```console
INFO: token retrieved for user@example.com
Task created for 'FMRIprepBidsSubject' on cluster 'fir':
{
  "id": 234567,
  "type": "BoutiquesTask::FMRIprepBidsSubject",
  ...
}
```

#### fMRIPrep — single userfile

```bash
cbrain-cli --launch-tool FMRIprepBidsSubject \
  --group-id BrainProject \
  --tool-param interface_userfile_ids='[7201,8201]' \
  --tool-param bids_dir=8201 \
  --tool-param fs_license_file=7201 \
  --tool-param output_dir_name=sub-001-run1 \
  --tool-param output_spaces='["MNI152NLin6Asym","MNI152NLin2009cAsym:res-2"]' \
  --tool-param anat_only=true \
  --tool-param low_mem=true \
  --tool-param no_reconall=true \
  --launch-tool-batch-type BidsSubject \
  --launch-tool-bourreau-id 110 \
  --launch-tool-results-dp-id 51
```

```console
INFO: token retrieved for user@example.com
Task created for 'FMRIprepBidsSubject' on cluster 'fir':
{
  "id": 234568,
  "type": "BoutiquesTask::FMRIprepBidsSubject",
  ...
}
```

#### DeepPrep — batch

DeepPrep expects BOLD runs whose task label is one of `6cat`, `rest`, `motor`, or `rest motor`. If your files use a different label, create symlinks and update the JSON `TaskName` so filenames contain one of these values:

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
  --launch-tool-bourreau-id 110 \
  --launch-tool-results-dp-id 51 \
  --tool-param interface_userfile_ids='[8123]' \
  --tool-param fs_license_file=8123 \
  --tool-param bold_task_type=rest \
  --tool-param output_dir_name="{full_noex}-{task_id}" \
  --tool-param cbrain_enable_output_cache_cleaner=false
```

```console
INFO: token retrieved for user@example.com
Task created for 'deepprep' on cluster 'fir':
{
  "id": 345678,
  "type": "BoutiquesTask::DeepPrep",
  ...
}
```

#### DeepPrep — single userfile

```bash
cbrain-cli --launch-tool deepprep \
  --group-id PilotStudy \
  --tool-param interface_userfile_ids='[8123,8124]' \
  --tool-param bids_dir=8124 \
  --tool-param fs_license_file=8123 \
  --tool-param bold_task_type=rest \
  --launch-tool-bourreau-id 110 \
  --launch-tool-results-dp-id 51 \
  --tool-param output_dir_name="{full_noex}-{task_id}" \
  --tool-param cbrain_enable_output_cache_cleaner=false
```

```console
INFO: token retrieved for user@example.com
Task created for 'deepprep' on cluster 'fir':
{
  "id": 345679,
  "type": "BoutiquesTask::DeepPrep",
  ...
}
```

> **Note:** DeepPrep tasks may fail on some clusters due to out‑of‑memory errors. Use `cbrain-cli --error-recover <task_id>` to retry **without** re‑uploading inputs, or `cbrain-cli --error-recover-failed MyProj --task-type DeepPrep` to re‑run failed DeepPrep tasks for a project, again without re‑uploading inputs.

**Single vs. batch**: For a **single** userfile, pass `--group-id PROJECT` along with `--tool-param interface_userfile_ids=UFID` and (if required) `--tool-param subject_dir=UFID`. For **batch**, specify `--launch-tool-batch-group PROJECT` to create one task per matching userfile.

**FreeSurfer license**: The value for `--tool-param fs_license_file` must be the CBRAIN **userfile ID** of your uploaded `license.txt`. Include that same ID in `interface_userfile_ids` so the tools can mount it.

---

### Monitoring & retrying

```bash
# Retry one task by ID
cbrain-cli --retry-task 123456

# Retry all failed tasks in a project
cbrain-cli --retry-failed DemoProject

# Retry only failed HippUnfold tasks
cbrain-cli --retry-failed DemoProject --task-type hipp
```

`--task-type` accepts a case‑insensitive prefix (e.g., `hipp` matches `BoutiquesTask::Hippunfold`) or a numeric `tool_config_id`.

---

### Error recovery

Ask CBRAIN to trigger built‑in recovery for tasks in a recoverable state:

```bash
# Recover a single task by ID
cbrain-cli --error-recover 123456

# Recover every failed or erroring task in a project
cbrain-cli --error-recover-failed DemoProject

# Limit to a particular task type
cbrain-cli --error-recover-failed DemoProject --task-type hippunfold
```

---

### Downloading

Retrieve derivatives (CLI supports `cbrain-cli download` and `bids-cbrain-cli download`):

```bash
bids-cbrain-cli download --tool hippunfold \
  --output-type HippunfoldOutput --group 42
```

```console
INFO: token retrieved for user@example.com
Downloading /sub-001_res-123456 → ./derivatives/hippunfold
INFO: Download complete
```

You can also fetch a **single** CBRAIN file via `--id <USERFILE>` (omit `--group`). Additional options:

- `--flatten` – drop wrapper directory so outputs land directly under subject/session;
- `--skip-dirs <NAME ...>` – ignore folders like `logs` or `work`;
- `--only-dirs <PATTERN ...>` – restrict downloads (e.g., `sub-*/figures`, `sub-*/ses-*/anat`);
- `--output-dir NAME` – write under `derivatives/NAME` instead of the default;
- `--download-path-map REMOTE=LOCAL` – place a remote directory under a different relative path (repeatable);
- `--normalize session|subject` – ensure filenames include session/subject labels.

Example (store fMRIPrep results under `derivatives/DeepPrep/BOLD`):

```bash
bids-cbrain-cli download --tool FMRIprepBidsSubject \
  --output-type FmriPrepOutput --group DemoProject \
  --output-dir DeepPrep/BOLD --flatten --skip-dirs logs
```

Example flattened tree:

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

---

### Aliasing task names

Duplicate BIDS `task-` files with a new label using `--alias`. Non‑JSONs are symlinked; JSON sidecars are copied by default with `"task-OLD"` replaced inside.

```bash
# create assocmemory copies of all task-6cat files
cbrain-cli --alias "6cat=assocmemory"

# restrict to subject/session and link JSON sidecars
cbrain-cli --alias "6cat=assocmemory,sub=002,ses=01,json=link"
```

Combine aliasing with other operations:

```bash
# alias before uploading
cbrain-cli --alias "assocmemory=6cat" --upload-bids-and-sftp-files sub-005

# or alias after downloading derivatives
cbrain-cli download --tool deepprep \
  --alias derivatives DeepPrep BOLD sub-* ses-* func "6cat=assocmemory" \
  --group DemoProject
```

> The optional `sub-*` / `ses-*` placeholders are ignored when determining the base directory, so the command automatically descends into the `sub-*/ses-*` hierarchy.

---

### Deleting

Preview with `--dry-delete`:

```bash
cbrain-cli --delete-userfile 123
cbrain-cli --delete-group MyTrial --delete-filetype BidsSubject
cbrain-cli --delete-group 12345 --delete-filetype BidsSubject HippunfoldOutput
```

```console
INFO: token retrieved for user@example.com
INFO: userfile 2000 deleted

INFO: 2 file(s) removed from project DemoProject
```

These helpers rely on CBRAIN OpenAPI endpoints for consistent error handling and authentication. Deletions return `HTTP 200` or `302` (redirects are not followed automatically).

---

## Python API

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

## Troubleshooting

If a download seems stuck, set a request timeout via the `CBRAIN_TIMEOUT` env var or the `--timeout` option (default: 60 seconds).

---

## Contributing / Development

Install dev dependencies and run checks:

```bash
pytest -c ../pytest.ini -vv    # unit tests (offline)
ruff check .                   # style & lint
pre-commit install             # git hooks
```

---

## Citations & acknowledgements

- **DeepPrep** – Ren J., et al. *Nat. Methods.* 2025;22(3):473–476.  
- **HippUnfold** – de Kraker L., et al. *eLife* 2023;12:e82835.  
- **fMRIPrep** – Esteban O., et al. *Nat. Methods.* 2019;16(1):111–116.  
- **Boutiques** – Glatard T., et al. *GigaScience* 2018;7(5):giy016.  
- **BIDS** – Gorgolewski K.J., et al. *Sci. Data* 2016;3:160044.  
- **CBRAIN** – Sherif T., et al. *Front. Neuroinform.* 2014;8:54.

Thanks to the **McGill Centre for Integrative Neuroscience** and **Pierre Rioux** for CBRAIN infrastructure and assistance. 

---

## License

This repo is released under the **MIT License** – see the top‑level `LICENSE` file for details.

---

## Roadmap

Automatic support for **FSL**, **FreeSurfer**, and more CBRAIN tools.
