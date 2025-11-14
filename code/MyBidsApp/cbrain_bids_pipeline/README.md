# cbrain_bids_pipeline

> **One-command bridge between a local BIDS dataset and the [CBRAIN](https://github.com/aces/cbrain) neuro‑informatics platform.**  
> *Ships with first‑class support for **HippUnfold**, **fMRIPrep**, and **DeepPrep**; more CBRAIN tools will be added in future minor releases.*

---

## Contents

- [Overview](#overview)
- [Quick‑start cheatsheet](#quick-start-cheatsheet)
  - [From zero to first output (5 steps)](#from-zero-to-first-output-5-steps)
- [Highlights](#highlights)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
  - [Where do config files live?](#where-do-config-files-live)
  - [YAML files](#yaml-files)
  - [Environment variables](#environment-variables)
- [Tool name mapping](#tool-name-mapping)
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

## Quick‑start cheatsheet

> **Naming style used throughout this README**  
> Narrative text (paper/tool names): **HippUnfold**, **fMRIPrep**, **DeepPrep**.  
> CLI & YAML keys: **hippunfold**, **FMRIprepBidsSubject** (CBRAIN tool name for fMRIPrep), **deepprep**.

### From zero to first output (5 steps)

1) **Validate** your BIDS dataset:

```bash
cbrain-cli --bids-validator sub-* ses-*
```

2) **Create a project** (CBRAIN calls these *groups*):

```bash
cbrain-cli --create-group "DemoProject" --group-description "hello-world run"
```

3) **Upload a tiny subset** (one subject/session) and register it on provider **51**:

```bash
cbrain-cli --upload-bids-and-sftp-files sub-001 ses-01 anat   --upload-register --upload-dp-id 51 --upload-group-id DemoProject
```

4) **Launch one task** (pick *one* of the following):

- **HippUnfold (minimal)**

```bash
cbrain-cli --launch-tool hippunfold   --group-id DemoProject   --tool-param interface_userfile_ids=UFID   --tool-param subject_dir=UFID
```

- **fMRIPrep (requires a FreeSurfer license)**

```bash
# Upload your FreeSurfer license.txt first and note its userfile ID (e.g., 7201)
cbrain-cli --launch-tool FMRIprepBidsSubject   --group-id DemoProject   --tool-param interface_userfile_ids='[7201,UFID]'   --tool-param bids_dir=UFID   --tool-param fs_license_file=7201   --tool-param anat_only=true --tool-param low_mem=true
```

> Replace **UFID** with the CBRAIN *userfile ID* of your uploaded subject. A practical way to find it is `cbrain-cli --list-userfiles-group DemoProject`.

5) **Check status → download** the first result:

```bash
# Check until the task shows 'Completed'
cbrain-cli --task-status DemoProject --task-type hippunfold

# Then download HippUnfold outputs into derivatives/hippunfold
cbrain-cli download --tool hippunfold   --output-type HippunfoldOutput   --group DemoProject --flatten --skip-dirs config logs work
```

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

**Option A — clone this repo directly**

```bash
git clone https://github.com/your-org/cbrain_bids_pipeline.git
cd cbrain_bids_pipeline
```

**Option B — this project lives inside a larger repo**  
If you vendor this project as a subfolder of a larger repository, `cd` into that subdirectory before installing. For example:

```bash
git clone https://github.com/example-user/MyBids.git
cd MyBids/code/MyBidsApp/cbrain_bids_pipeline   # adjust if your layout differs
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

### Where do config files live?

By default the CLI looks for configuration **in your current project** first and then in your **user config directory**:

1. **Project‑local**: `./cbrain/` (e.g., `./cbrain/servers.yaml`, `./cbrain/tools.yaml`, `./cbrain/defaults.yaml`)
2. **User‑level**: `~/.config/cbrain_bids_pipeline/`

If a file exists in both places, the **project‑local** version is used. This keeps team settings with the repo while allowing personal overrides at `~/.config`.


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
CBRAIN_USERNAME=alice@example.com CBRAIN_PASSWORD='your_password'   cbrain-cli --bids-validator sub-* ses-*
```

---

## Tool name mapping

| CLI / YAML key          | CBRAIN portal display name | Notes                            |
|-------------------------|----------------------------|----------------------------------|
| `hippunfold`            | HippUnfold                 |                                  |
| `FMRIprepBidsSubject`   | fMRIPrep                   | CBRAIN tool wrapper name         |
| `deepprep`              | DeepPrep                   |                                  |

> CBRAIN’s wrapper tool name for **fMRIPrep** is **FMRIprepBidsSubject**. Use that exact key with `--launch-tool` and in `tools.yaml`.

---

## CLI Usage

### Listing resources

Use these commands to inspect CBRAIN's available tools, their configurations, existing projects, and execution servers before launching jobs.

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

Initialize a CBRAIN project (group) to organize uploaded datasets and launched tasks.

```bash
cbrain-cli --create-group "MyTrial"   --group-description "test dataset"
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
cbrain-cli --upload-bids-and-sftp-files sub-* --upload-register   --upload-dp-id 51 --upload-group-id 456
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
cbrain-cli --upload-bids-and-sftp-files dataset_description.json   --upload-register --upload-dp-id 51 --upload-group-id NewProject
```

```bash
cbrain-cli --upload-bids-and-sftp-files sub-* ses-01 anat   --upload-register --upload-dp-id 51   --upload-filetypes BidsSubject   --upload-group-id NewProject
```

```console
$ cbrain-cli --upload-bids-and-sftp-files sub-* ses-01 anat   --upload-register --upload-dp-id 51   --upload-filetypes BidsSubject   --upload-group-id DemoProject
INFO: token retrieved for user@example.com
INFO: Uploaded 6 file(s) to provider 51
INFO: Registered 6 userfile(s) in project DemoProject
```

Missing folders are skipped entirely. Single files inside `derivatives/` are uploaded at the dataset root (e.g., `derivatives/license.txt` → `/license.txt`).

**Dry run** without transferring files:

```bash
cbrain-cli --upload-bids-and-sftp-files sub-* ses-01 anat   --upload-dp-id 51 --upload-dry-run
```

Example uploading the same file to two different providers:

```console
$ cbrain-cli   --upload-bids-and-sftp-files participants.tsv   --upload-register   --upload-dp-id 51   --upload-group-id DemoBids
...
$ cbrain-cli   --upload-bids-and-sftp-files participants.tsv   --upload-register   --upload-dp-id 32   --upload-group-id DemoBids
...
```

---

## Launching tasks

Create tasks directly with `--launch-tool`. The examples below show **batch** and **single‑userfile** launches for **HippUnfold**, **fMRIPrep**, and **DeepPrep**, using multi‑line CLI blocks consistent with the rest of this README.

> **Conventions used below**
>
> - **Batch** = `--launch-tool-batch-group` + `--launch-tool-batch-type` → one task per matching userfile.  
> - **Single** = `--group-id` + `--tool-param interface_userfile_ids=...` (and, if required, `subject_dir` or `bids_dir`).  
> - **FreeSurfer license** = set `--tool-param fs_license_file=<UFID>` and include the same ID in `interface_userfile_ids` so tools can mount it.

### HippUnfold — batch

```console
(.venv) user@host DemoProject % cbrain-cli --launch-tool hippunfold \
  --tool-param modality=T1w \
  --launch-tool-batch-group DemoProject \
  --launch-tool-batch-type BidsSubject \
  --launch-tool-bourreau-id 104 \
  --launch-tool-results-dp-id 51
INFO: token retrieved for user@example.com
INFO: Task created for 'hippunfold' on cluster 'rorqual':
{ "id": 123456, "type": "BoutiquesTask::Hippunfold", ... }
```

### HippUnfold — single userfile

```console
(.venv) user@host DemoProject % cbrain-cli --launch-tool hippunfold \
  --group-id DemoProject \
  --tool-param interface_userfile_ids=9001 \
  --tool-param subject_dir=9001 \
  --launch-tool-bourreau-id 104 \
  --launch-tool-results-dp-id 51
INFO: token retrieved for user@example.com
INFO: Task created for 'hippunfold' on cluster 'rorqual':
{ "id": 123457, "type": "BoutiquesTask::Hippunfold", ... }
```

### fMRIPrep — single subject

```console
(.venv) user@host SampleBidsProject % cbrain-cli --launch-tool FMRIprepBidsSubject \
    --group-id SampleBidsProject \
    --tool-param bids_dir=6067624 \
    --tool-param interface_userfile_ids='[6085435,6067624]' \
    --tool-param fs_license_file=6085435 \
    --tool-param output_spaces='["T1w","MNI152NLin2009cAsym:res-2"]' \
    --tool-param use_aroma=true \
    --tool-param output_layout=bids \
    --launch-tool-bourreau-id 104 \
    --launch-tool-results-dp-id 51 \
    --tool-param output_dir_name="{full_noex}-{task_id}" \
    --tool-param low_mem=true \
    --tool-param cbrain_enable_output_cache_cleaner=false
INFO: Retrieved new CBRAIN token for user 'demo_user'
INFO: Task created for 'FMRIprepBidsSubject' on cluster 'rorqual':
{ "id": 234567, "type": "BoutiquesTask::FMRIprepBidsSubject", ... }
```

### fMRIPrep — **Recon-all** for single subject

```console
(.venv) user@host ExampleBidsProject % cbrain-cli --launch-tool FMRIprepBidsSubject \
    --group-id SampleBidsTest \
    --tool-param bids_dir=6067750 \
    --tool-param interface_userfile_ids='[6067675,6067750]' \
    --tool-param fs_license_file=6067675 \
    --tool-param output_spaces='["fsnative","fsaverage6"]' \
    --tool-param anat_only=true \
    --tool-param longitudinal=true \
    --tool-param output_layout=bids \
    --launch-tool-bourreau-id 104 \
    --launch-tool-results-dp-id 51 \
    --tool-param output_dir_name="{full_noex}-{task_id}" \
    --tool-param cbrain_enable_output_cache_cleaner=false
INFO: Retrieved new CBRAIN token for user 'demo_user'
INFO: Task created for 'FMRIprepBidsSubject' on cluster 'rorqual':
{
  "id": 3051583,
  "type": "BoutiquesTask::FMRIprepBidsSubject",
  "user_id": 9999,
  "group_id": 12346,
  "bourreau_id": 104,
  "tool_config_id": 8909,
  "batch_id": 3051583,
  "params": {
    "invoke": {
      "output_dir_name": "{full_noex}-{task_id}",
      "low_mem": "0",
      "anat_only": true,
      "boilerplate": "0",
      "longitudinal": true,
      "bold2t1w_dof": 6,
      "use_bbr": "0",
      "output_layout": "bids",
      "medial_surface_nan": "0",
      "use_aroma": "0",
      "return_all_components": "0",
      "aroma_melodic_dimensionality": -200,
      "skull_strip_template": "OASIS30ANTs",
      "skull_strip_fixed_seed": "0",
      "fmap_bspline": "0",
      "fmap_no_demean": "0",
      "use_syn_sdc": "0",
      "force_syn": "0",
      "no_submm_recon": "0",
      "no_reconall": "0",
      "resource_monitor": "0",
      "reports_only": "0",
      "write_graph": "0",
      "stop_on_first_crash": "0",
      "notrack": "0",
      "sloppy": "0",
      "bids_dir": 6067750,
      "fs_license_file": 6067675,
      "output_spaces": [
        "fsnative",
        "fsaverage6"
      ]
    },
    "cbrain_enable_output_cache_cleaner": false,
    "interface_userfile_ids": [
      "6067675",
      "6067750"
    ]
  },
  "status": "New",
  "created_at": "2025-10-16T01:43:15.000-04:00",
  "updated_at": "2025-10-16T01:43:15.000-04:00",
  "run_number": null,
  "results_data_provider_id": 51,
  "cluster_workdir_size": null,
  "workdir_archived": false,
  "workdir_archive_userfile_id": null,
  "description": null
}
```

### fMRIPrep — batch

```console
(.venv) user@host BrainProject % cbrain-cli --launch-tool FMRIprepBidsSubject \
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
INFO: token retrieved for user@example.com
INFO: Task created for 'FMRIprepBidsSubject' on cluster 'fir':
{ "id": 234567, "type": "BoutiquesTask::FMRIprepBidsSubject", ... }
```

### DeepPrep — **anatomical only**, single subject 

> **Task labels.** DeepPrep expects BOLD runs with a task label (e.g., `task1`, `rest`, `motor`, etc.). If you want to run anatomical processing, provide task label a placeholder and set anat_only=true.

```console
(.venv) user@host DemoProject % cbrain-cli --launch-tool deepprep   
    --group-id SampleBidsTest \
    --launch-tool-group-id SampleBidsProject \
    --launch-tool-bourreau-id 110 \
    --launch-tool-results-dp-id 51 \
    --tool-param bids_dir=6067624
    --tool-param interface_userfile_ids='[6085435,6067624]' \
    --tool-param fs_license_file=6085435 \
    --tool-param bold_task_type="assocmemory" \
    --tool-param anat_only=true \
    --custom-output 'output_dir_name="{bids_dir}-{cortthickness}"' \ 
    --tool-param cbrain_enable_output_cache_cleaner=false
INFO: Retrieved new CBRAIN token for user 'demo_user'
INFO: [INFO] Custom output output_dir_name resolved to sub-002-cortthickness
INFO: Task created for 'deepprep' on cluster 'fir':
{
  "id": 3061480,
  "type": "BoutiquesTask::DeepPrep",
  "user_id": 9999,
  "group_id": 12345,
  "bourreau_id": 110,
  "tool_config_id": 10697,
  "batch_id": 3061480,
  "params": {
    "invoke": {
      "anat_only": true,
      "bold_only": "0",
      "bold_sdc": true,
      "bold_confounds": true,
      "bold_skip_frames": 0,
      "bold_cifti": "0",
      "bold_surface_spaces": "fsaverage6",
      "bold_volume_space": "MNI152NLin6Asym",
      "bold_volume_res": "02",
      "ignore_error": false,
      "bids_dir": 6067624,
      "fs_license_file": 6085435,
      "bold_task_type": "assocmemory",
      "output_dir_name": "sub-002-cortthickness"
    },
    "cbrain_enable_output_cache_cleaner": "false",
    "interface_userfile_ids": [
      "6085435",
      "6067624"
    ]
  },
  "status": "New",
  "created_at": "2025-10-17T07:39:22.000-04:00",
  "updated_at": "2025-10-17T07:39:22.000-04:00",
  "run_number": null,
  "results_data_provider_id": 51,
  "cluster_workdir_size": null,
  "workdir_archived": false,
  "workdir_archive_userfile_id": null,
  "description": null
}
```

### DeepPrep — fMRI preprocessing **batch** 

```console
(.venv) user@host DemoProject % cbrain-cli --launch-tool deepprep
    --launch-tool-batch-group SampleBidsProject \
    --launch-tool-batch-type BidsSubject \
    --launch-tool-bourreau-id 110 \
    --launch-tool-results-dp-id 51 \
    --tool-param interface_userfile_ids='[6085435]' \
    --tool-param fs_license_file=6085435 \
    --tool-param bold_task_type="assocmemory" \
    --custom-output 'output_dir_name="{bids_dir}-{bold_task_type}"' \
    --tool-param cbrain_enable_output_cache_cleaner=false 
INFO: Retrieved new CBRAIN token for user 'demo_user'
INFO: [BATCH 6067624] Launching 'deepprep' (dry_run=False)…
INFO: [INFO] Custom output output_dir_name resolved to sub-002-assocmemory
INFO: Task created for 'deepprep' on cluster 'fir':
{
  "id": 3061486,
  "type": "BoutiquesTask::DeepPrep",
  "user_id": 9999,
  "group_id": 12345,
  "bourreau_id": 110,
  "tool_config_id": 10697,
  "batch_id": 3061486,
  "params": {
    "invoke": {
      "anat_only": "0",
      "bold_only": "0",
      "bold_sdc": true,
      "bold_confounds": true,
      "bold_skip_frames": 0,
      "bold_cifti": "0",
      "bold_surface_spaces": "fsaverage6",
      "bold_volume_space": "MNI152NLin6Asym",
      "bold_volume_res": "02",
      "ignore_error": false,
      "fs_license_file": 6085435,
      "bold_task_type": "assocmemory",
      "bids_dir": 6067624,
      "output_dir_name": "sub-002-assocmemory"
    },
    "cbrain_enable_output_cache_cleaner": "false",
    "interface_userfile_ids": [
      "6067624",
      "6085435"
    ]
  },
  "status": "New",
  "created_at": "2025-10-17T09:16:48.000-04:00",
  "updated_at": "2025-10-17T09:16:48.000-04:00",
  "run_number": null,
  "results_data_provider_id": 51,
  "cluster_workdir_size": null,
  "workdir_archived": false,
  "workdir_archive_userfile_id": null,
  "description": null
}
```

> **Notes**
>
> - DeepPrep tasks may fail on some clusters due to out‑of‑memory errors. Use `cbrain-cli --error-recover <task_id>` to retry **without** re‑uploading inputs, or `cbrain-cli --error-recover-failed MyProj --task-type deepprep` to re‑run failed DeepPrep tasks for a project, again without re‑uploading inputs.
> - **Single vs. batch recap**: For a **single** userfile, pass `--group-id PROJECT` along with `--tool-param interface_userfile_ids=UFID` and (if required) `--tool-param subject_dir=UFID`. For **batch**, specify `--launch-tool-batch-group PROJECT` to create one task per matching userfile.
> - **FreeSurfer license**: The value for `--tool-param fs_license_file` must be the CBRAIN **userfile ID** of your uploaded `license.txt`. Include that same ID in `interface_userfile_ids`.

---

### Custom output naming

Use `--custom-output` to build descriptive derivative directories without
manually typing task IDs.  Templates follow Python's ``str.format`` syntax and
can reference any parameter passed via `--tool-param`.  Unknown placeholders are
kept as literal text, making it easy to mix dynamic values with fixed suffixes.

```console
$ cbrain-cli --launch-tool deepprep   --launch-tool-group-id SampleBidsProject   --launch-tool-bourreau-id 110   --launch-tool-results-dp-id 51   --tool-param bids_dir=123457   --tool-param interface_userfile_ids='[89101115,123457]'   --tool-param fs_license_file=8910111   --tool-param bold_task_type="assocmemory"   --tool-param anat_only=true   --custom-output 'output_dir_name="{bids_dir}-{cortthickness}"'   --tool-param cbrain_enable_output_cache_cleaner=false
INFO: Retrieved new CBRAIN token for user 'demo_user'
INFO: [INFO] Custom output output_dir_name resolved to sub-002-cortthickness
INFO: Task created for 'deepprep' on cluster 'fir':
{
  "id": 3333333,
  "type": "BoutiquesTask::DeepPrep",
  "user_id": 9999,
  "group_id": 11111,
  "bourreau_id": 110,
  "tool_config_id": 10697,
  "batch_id": 7777777,
  "params": {
    "invoke": {
      "anat_only": true,
      "bold_only": "0",
      "bold_sdc": true,
      "bold_confounds": true,
      "bold_skip_frames": 0,
      "bold_cifti": "0",
      "bold_surface_spaces": "fsaverage6",
      "bold_volume_space": "MNI152NLin6Asym",
      "bold_volume_res": "02",
      "ignore_error": false,
      "bids_dir": 123457,
      "fs_license_file": 8910111,
      "bold_task_type": "assocmemory",
      "output_dir_name": "sub-002-cortthickness"
    },
    "cbrain_enable_output_cache_cleaner": "false",
    "interface_userfile_ids": [
      "8910111",
      "123457"
    ]
  },
  "status": "New",
  "created_at": "2025-10-17T07:39:22.000-04:00",
  "updated_at": "2025-10-17T07:39:22.000-04:00",
  "run_number": null,
  "results_data_provider_id": 51,
  "cluster_workdir_size": null,
  "workdir_archived": false,
  "workdir_archive_userfile_id": null,
  "description": null
}
```

In the example above, the CLI resolves the CBRAIN userfile ID in `bids_dir` to the
subject name and expands the template to `sub-002-cortthickness`. 

**Tips**

* `{tool_name}` is always available inside templates.
* CBRAIN-specific placeholders for some tools (e.g., FmriPrep) such as `{full_noex}` still work via
  `--tool-param` when you prefer server-side expansion.
* Batch launches apply the template to every subject automatically, so
  `--custom-output 'output_dir_name="{bids_dir}-{cortthickness}"'` produces one
  directory per participant.

---

### Monitoring & retrying

Track task status and automatically rerun jobs that fail or were interrupted.

```bash
# Retry one task by ID
cbrain-cli --retry-task 123456

# Retry all failed tasks in a project
cbrain-cli --retry-failed DemoProject

# Retry only failed HippUnfold tasks
cbrain-cli --retry-failed DemoProject --task-type hippunfold
```

`--task-type` accepts a case‑insensitive prefix (e.g., `hippun` matches `BoutiquesTask::Hippunfold`) or a numeric `tool_config_id`.

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

Retrieve derivatives with `cbrain-cli download`:

```bash
cbrain-cli download --tool hippunfold   --output-type HippunfoldOutput --group 42
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

**Example (store fMRIPrep results under `derivatives/fmriprep`)**

```bash
cbrain-cli download --tool FMRIprepBidsSubject   --output-type FmriPrepOutput --group DemoProject   --output-dir fmriprep --flatten --skip-dirs logs
```

> If you intentionally want a different layout (e.g., to merge results into a multi‑tool tree), use `--output-dir` and `--download-path-map` to remap directories.

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
cbrain-cli download --tool deepprep   --alias derivatives DeepPrep BOLD sub-* ses-* func "6cat=assocmemory"   --group DemoProject
```

> The optional `sub-*` / `ses-*` placeholders are ignored when determining the base directory, so the command automatically descends into the `sub-*/ses-*` hierarchy.

---

### Deleting

Remove uploaded files or entire projects from CBRAIN. Use `--dry-delete` to preview actions before they run.

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

Integrate the pipeline into your own Python scripts by calling its helper functions directly.

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
