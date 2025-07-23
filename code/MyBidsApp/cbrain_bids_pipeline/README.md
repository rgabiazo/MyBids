# cbrain\_bids\_pipeline

> **One-command bridge between a local BIDS dataset and the [CBRAIN](https://github.com/aces/cbrain) neuro‑informatics platform.**
> *Currently ships with first‑class support for **HippUnfold**; more CBRAIN tools will be added in future minor releases.*

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
```

**`defaults.yaml`** – Where derivatives land inside the BIDS tree

```yaml
cbrain:
  hippunfold:
    hippunfold_output_dir: derivatives/hippunfold
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
| **Launch** HippUnfold on project MyTrial | [`cbrain-cli --launch-tool hippunfold --group-id MyTrial --param modality=T1w`](#launching) |
| **Download** derivatives             | [`cbrain-cli download --tool hippunfold --group MyTrial --flatten --skip-dirs config logs work`](#downloading) |
| **Monitor** a task                   | `cbrain-cli --task-status 456789` |
| **List HippUnfold tasks in a project** | `cbrain-cli --task-status MyTrial --task-type hipp` |
| **Delete a userfile**                | [`cbrain-cli --delete-userfile 123 --dry-delete`](#deleting) |
| **Purge filetype from project**      | [`cbrain-cli --delete-group MyTrial --delete-filetype BidsSubject`](#deleting) |

When ``--task-status`` receives a number, ``cbrain-cli`` first checks if it
matches an existing project ID. If no such project exists, the value is treated
as a task identifier.

The default `tools.yaml` keeps `config`, `logs` and `work` directories when fetching HippUnfold outputs.  Specifying
`--skip-dirs` overrides this so the listed folders will not be downloaded.

When downloading a single userfile with `--id`, the `--group` option can be omitted.

Use `--task-status <PROJECT>` together with `--task-type` to list tasks for a
specific CBRAIN tool. The filter accepts a case-insensitive prefix of the task
`type` (e.g. `hipp` matches `BoutiquesTask::Hippunfold`) or a numeric
`tool_config_id`.

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

### Launching

Create tasks directly from the CLI with `--launch-tool`:

```bash
cbrain-cli --launch-tool hippunfold \
    --override-tool-config-id 5035 \
    --tool-param modality=T1w \
    --launch-tool-batch-group DemoProject \
    --launch-tool-batch-type BidsSubject \
    --launch-tool-bourreau-id 56 \
    --launch-tool-results-dp-id 51
```

```console
$ cbrain-cli --launch-tool hippunfold \
    --override-tool-config-id 5035 \
    --tool-param modality=T1w \
    --launch-tool-batch-group DemoProject \
    --launch-tool-batch-type BidsSubject \
    --launch-tool-bourreau-id 56 \
    --launch-tool-results-dp-id 51
INFO: token retrieved for user@example.com
Created task ID=9001 for project DemoProject
{
  "id": 123456,
  "type": "BoutiquesTask::Hippunfold",
  "user_id": 42,
  "group_id": 77,
  "bourreau_id": 56,
  "tool_config_id": 5035,
  "batch_id": 123456,
  "params": {
    "invoke": {
      "modality": "T1w",
      "subject_dir": 6000
    },
    "interface_userfile_ids": ["6000"],
    "cbrain_enable_output_cache_cleaner": false
  }
}
```

Launches can target either a **single userfile** or an entire project. Use
`--group-id PROJECT` together with `--tool-param interface_userfile_ids=UFID` and
`--tool-param subject_dir=UFID` to run on one file.  Alternatively, specify
`--launch-tool-batch-group PROJECT` to create one task per matching userfile.
Project references accept numeric IDs or names.

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

* **CBRAIN** – Sherif T., et al. *Front Neuroinform* 2014;8:54. doi:10.3389/fninf.2014.00054  
* **Boutiques** – Glatard T., et al. *GigaScience* 2018;7:giy016. doi:10.1093/gigascience/giy016  
* **BIDS** – Gorgolewski K.J., et al. *Sci Data* 2016;3:160044. doi:10.1038/sdata.2016.44  
* **HippUnfold** – de Kraker L., et al. *eLife* 2022;11:e77945. doi:10.7554/eLife.77945  

We thank the **McGill Centre for Integrative Neuroscience** and **Pierre Rioux** for providing the CBRAIN infrastructure and assistance.

---

## 🔖  License

This repo is MIT‑licensed; generated OpenAPI client code inherits **GPL‑3.0** from the upstream CBRAIN Swagger spec.

---

## Roadmap

*Future roadmap*: add automatic support for **FSL**, **fMRIPrep**, **FreeSurfer**, and more CBRAIN tools — stay tuned! ✨
