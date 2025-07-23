# **bidscomatic**

*A CLI toolkit to unzip, convert & organise DICOM studies into a BIDS‑compliant layout*

---

## ✨ Key features

| Capability                         | Why it matters                                                                                                          |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| **One‑line DICOM → BIDS pipeline** | `bidscomatic-cli convert` wraps *dcm2niix* in parallel and writes deterministic folder trees.                           |
| **YAML‑driven mapping**            | Opinionated defaults ship in `resources/default_*.yaml`, yet every study can override series‑to‑BIDS rules per dataset. |
| **Idempotent & safe**              | Existing files are **never** overwritten unless `--overwrite` is supplied.                                              |
| **Rich sub‑commands**              | Unzip archives, curate participants & events, build questionnaires – all from one CLI.                                  |
| **Pure‑Python, MIT‑licensed**      | No compiled extensions; runs on Linux & macOS with Python ≥ 3.9.                                                        |

---

## 🚀 Installation

> **Prerequisites**
>
> * Python ≥ 3.9
> * [`dcm2niix`](https://github.com/rordenlab/dcm2niix) available on your `$PATH`
> * Node.js & npm (install via your OS package manager)
> * `bids-validator` (`npm install -g bids-validator`) – required to use the `validate` sub-command

### Installing `dcm2niix`

`bidscomatic` expects the `dcm2niix` binary to be discoverable on your
`PATH`.  For Most Linux distributions and Homebrew provide packages:

```bash
# Ubuntu/Debian
sudo apt install dcm2niix

# macOS (Homebrew)
brew install dcm2niix
```

Alternatively download a pre-built release from the
[`dcm2niix` GitHub page](https://github.com/rordenlab/dcm2niix/releases) and
place the binary somewhere listed in your `PATH` environment variable.

### Installing Node.js

Node.js is required for the BIDS Validator used by the `validate` sub-command.
Install it via your package manager if you do not already have it:

```bash
# macOS (Homebrew)
brew install node

# Ubuntu/Debian
sudo apt install nodejs npm
```

Afterwards install the validator with `npm install -g bids-validator` if you
plan to run `bidscomatic-cli validate`.

### a) Editable install inside a larger repo

```bash
# From your repository root (monorepo style)
pip install -e path/to/bidscomatic
```

### b) Stand‑alone development clone

```bash
git clone https://github.com/<your‑org>/bidscomatic.git
cd bidscomatic
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"   # core + testing/lint extras
```

---

## ⚡ 90‑second quick‑start

```bash
# 1 Extract study archives (ZIP/TAR) into DICOM folders
bidscomatic-cli unzip ~/Downloads/MRI_archives --rm-archives
# plain text [INFO] messages (no JSON)

# 2 Convert every DICOM series → NIfTI under sourcedata/nifti
bidscomatic-cli convert /path/to/dicom --merge-by-name -j 8

# 3 Organise NIfTIs into BIDS folders
bidscomatic-cli bids sourcedata/nifti \
    --anat t1w,t2w \
    --func task=nback,rest \
    --dwi --epi --overwrite
bidscomatic-cli validate
```

Result: a fully‑fledged BIDS dataset ready for *fMRIPrep*, *QSIPrep*, etc.

## 📂 Example dataset structure

After initialising a project you may see a directory tree similar to:

```text
MyStudy/
├── code/
├── dataset_description.json
├── LICENSE
├── README.md
└── sourcedata/
    ├── behavioural_task/
    │   ├── run1_taskA/
    │   │   ├── img01.bmp
    │   │   └── ...             # additional stimulus files
    │   ├── run1_taskB/
    │   └── ...                 # more runs and tasks
    ├── cfmm2tar/
    │   ├── metadata.json
    │   └── sub-001/
    │       └── ExampleStudy/
    │           ├── study_20240101.attached.tar
    │           ├── study_20240101.tar
    │           └── study_20240101.uid
    ├── dicom/
    │   ├── metadata.json
    │   ├── sub-001/
    │   │   └── ses-01/
    │   │       └── ExampleStudy/
    │           ├── study_20240101.attached.tar
    │           ├── study_20240101.tar
    │           └── study_20240101.uid
    └── phenotype_raw/
        └── questionnaire.csv
```

Use `bidscomatic-cli unzip` to extract archives into `sourcedata/dicom`.
Run `bidscomatic-cli convert sourcedata/dicom` to create NIfTIs under
`sourcedata/nifti`, then organise them with `bidscomatic-cli bids`.
When generating `events.tsv`, pass `--create-stimuli-directory`
to copy any referenced images into `<BIDS_ROOT>/stimuli`.

---

## 🔧 Command reference (cheat‑sheet)

| Sub‑command      | What it does                                                      |
| ---------------- | ----------------------------------------------------------------- |
| `init`           | Create an empty BIDS dataset (writes `dataset_description.json`; renames folder unless `--no-rename-root`). |
| `unzip`          | Extract archives & optionally delete them or their DICOM folders. |
| `convert`        | Parallel DICOM → NIfTI conversion powered by *dcm2niix*.          |
| `bids`           | Move NIfTIs into `anat/`, `func/`, `dwi/`, `fmap/` folders.       |
| `dataset-description` | Create or update `dataset_description.json`.                |
| `participants`   | Merge metadata & update `participants.tsv` (values can be recoded). |
| `events`         | Turn behavioural sheets into `*_events.tsv`.                      |
| `questionnaires` | Split questionnaire CSV → tidy TSV(s) in `phenotype/` (auto-detects subjects; use `--all-subjects` to disable). |
| `phenotype-json` | Create or update JSON side-cars for questionnaire TSVs. |
| `validate`       | Run the Node bids-validator on the dataset. |

Each command exposes `--help` with exhaustive options and live examples.

All sub-commands emit plain-text `[INFO]` messages by default unless `--verbose`
or `--debug` is specified.

Example:

```bash
bidscomatic-cli participants --map-values group=0:control,1:intervention
```

Another common task is creating `events.tsv` files from behavioural sheets:

```bash
bidscomatic-cli events sourcedata/behavioural_task \
  --img-col image_file --accuracy-col is_correct \
  --onset-cols onset_Run1 --rt-cols rt_Run1 \
  --duration 3 --trialtype-patterns 'foo=bar' \
  --task demo
```

By default the `stim_file` column stores only the file name relative to the
`stimuli` directory.  Add `--keep-raw-stim` to preserve the original path.

Use `--create-stimuli-directory` to automatically copy all referenced images
into `<BIDS_ROOT>/stimuli` the first time you generate the events files.
Relative paths are resolved with respect to each behavioural sheet or the
directory supplied via `--stim-root`.  When a single directory is given on the
command line the same path is used as the default stimulus root.

```console
$ bidscomatic-cli events --help | grep keep-raw-stim
  --keep-raw-stim     Preserve original stimulus paths in 'stim_file'.
$ bidscomatic-cli events --help | grep create-stimuli-directory
  --create-stimuli-directory  Copy stimulus files into <BIDS_ROOT>/stimuli/
```

Use ``--create-events-json`` to write a minimal ``*_events.json`` side‑car for
each ``events.tsv`` file.  The following flags override individual metadata
fields:

* ``--json-spec`` – merge an external JSON snippet into every side‑car.
* ``--field-description`` – set column descriptions with ``col=text`` pairs.
* ``--field-units`` – define measurement units with ``col=unit`` pairs.
* ``--field-levels`` – describe categorical values with ``col=val:desc`` pairs.

Example:

```bash
bidscomatic-cli events sourcedata/behavioural_task \
  --img-col image_file --accuracy-col is_correct \
  --onset-cols onset_Run1 --rt-cols rt_Run1 \
  --duration 3 --trialtype-patterns 'img=img' \
  --task demo --sub sub-001 \
  --create-events-json \
  --field-description response_time="RT in seconds" \
  --field-units response_time=s \
  --field-levels trial_type=img:face
```

Resulting ``sub-001_task-demo_run-01_events.json`` (abridged):

```json
{
  "response_time": {"Description": "RT in seconds", "Units": "s"},
  "trial_type": {"Levels": {"img": "face"}},
  "GeneratedBy": {
    "Name": "bidscomatic",
    "Version": "0.1.1",
    "CodeURL": "https://github.com/<org>/bidscomatic"
  }
}
```

To reproduce this JSON via a file, write additional column metadata to
``events_meta.json``:

```json
{
  "response_time": {"Description": "RT in seconds", "Units": "s"},
  "trial_type": {
    "Description": "Stimulus category",
    "Levels": {"img": "", "unknown": ""}
  }
}
```

And call the CLI with ``--json-spec`` to merge the snippet:

```bash
bidscomatic-cli events sourcedata/behavioural_task \
  --img-col image_file --accuracy-col is_correct \
  --onset-cols onset_Run1 --rt-cols rt_Run1 \
  --duration 3 --trialtype-patterns 'img=img' \
  --task demo --sub sub-001 \
  --create-events-json \
  --json-spec events_meta.json
```

Resulting JSON (abridged):

```json
{
  "response_time": {"Description": "RT in seconds", "Units": "s"},
  "trial_type": {
    "Description": "Stimulus category",
    "Levels": {"img": "", "unknown": ""}
  },
  "GeneratedBy": {
    "Name": "bidscomatic",
    "Version": "0.1.1",
    "CodeURL": "https://github.com/<org>/bidscomatic"
  }
}
```

By default only the ``onset`` and ``duration`` columns are kept.  Use
``--keep-cols`` to preserve additional columns such as
``trial_type``, ``stim_file``, ``response_time`` or ``response``.

### Phenotype JSON metadata overrides

The `phenotype-json` command supports inline overrides for measurement tool
metadata and individual fields:

```bash
bidscomatic-cli phenotype-json phenotype/mmq_abl_ses-01.tsv \
  --tool-description "MMQ" \
  --tool-term-url https://example.com \
  --field-description mmq_ability="Ability score" \
  --field-units mmq_ability=score
[INFO] Wrote phenotype/mmq_abl_ses-01.json
```

### Unzipping DICOM archives

```console
$ bidscomatic-cli unzip sourcedata/dicom
=== Unzip archives ===
[INFO] Unzipping: sourcedata/dicom/sub-001/ses-01
  • sub-001/ses-01
[INFO] Found 2 archive(s) under /home/user/MyBidsProject/sourcedata/dicom/sub-001/ses-01
[INFO] Unpacking TAR: .../sub-001_ses-01.tar → .../sub-001/ses-01
[INFO] Unzipping: sourcedata/dicom/sub-002/ses-02
  • sub-002/ses-02
[INFO] Found 2 archive(s) under /home/user/MyBidsProject/sourcedata/dicom/sub-002/ses-02
[INFO] Unpacking TAR: .../sub-002_ses-02.tar → .../sub-002/ses-02
✓ 4 archive(s) unpacked

$ bidscomatic-cli unzip sourcedata/dicom --filter-sub 001
[INFO] Unzipping: sourcedata/dicom/sub-001/ses-01
  • sub-001/ses-01
✓ 2 archive(s) unpacked

$ bidscomatic-cli unzip sourcedata/dicom --filter-ses 02
[INFO] Unzipping: sourcedata/dicom/sub-002/ses-02
  • sub-002/ses-02
✓ 2 archive(s) unpacked
```

### Filtering subjects & sessions

Most commands (`unzip`, `convert`, `bids`, `events`, `participants`, etc.)
accept `--filter-sub` and `--filter-ses` to restrict which IDs are processed.
Provide IDs without the `sub-`/`ses-` prefix. Multiple values may be given by
repeating the option or separating values with commas.

```bash
bidscomatic-cli convert sourcedata/dicom --filter-sub 001,002 --filter-ses 02
```

### Converting DICOM to NIfTI

```console
$ bidscomatic-cli convert sourcedata/dicom
=== Convert DICOM ===
[INFO] Converting DICOM tree: sourcedata/dicom/sub-001/ses-01
  • sub-001/ses-01
[INFO] Scanning /home/user/MyBidsProject/sourcedata/dicom/sub-001/ses-01 for DICOM series …
[INFO] Found 27 image series
[INFO] Subject = sub-001    Session hint = ses-01
[INFO] ✓ 27 series → 650 file(s) written under /home/user/MyBidsProject/sourcedata/nifti
[INFO] Converting DICOM tree: sourcedata/dicom/sub-002/ses-02
  • sub-002/ses-02
[INFO] Scanning /home/user/MyBidsProject/sourcedata/dicom/sub-002/ses-02 for DICOM series …
[INFO] Found 29 image series
[INFO] Subject = sub-002    Session hint = ses-02
[INFO] ✓ 29 series → 694 file(s) written under /home/user/MyBidsProject/sourcedata/nifti
✓ 56 series across 2 subject folders → 1344 file(s) total
```

### Organising into BIDS

```console
$ bidscomatic-cli bids sourcedata/nifti --anat t1w --func task=memory,rest --epi
=== Organise BIDS ===
  • sub-001/ses-01
  • sub-002/ses-02

  — Anatomical —
[INFO] Picked T1w.nii.gz (rank=(11, 0)) for sub-001 ses-01
[INFO] sourcedata/nifti/sub-001/ses-01/2024_01_01/0011/T1w.nii.gz ↳ sub-001/ses-01/anat/sub-001_ses-01_T1w.nii.gz
✓ Anatomical organisation complete.

  — Functional —
[INFO] [sub-001 ses-01] memory dir=AP → 3 run(s) to move, 0 already present
[INFO] sourcedata/nifti/sub-001/ses-01/0016/rfMRI_TASK_AP_16.nii.gz ↳ sub-001/ses-01/func/sub-001_ses-01_task-memory_dir-AP_run-01_bold.nii.gz
[INFO] [sub-001 ses-01] rest dir=AP → 1 run(s) to move, 0 already present
[INFO] sourcedata/nifti/sub-001/ses-01/0025/rfMRI_REST_AP_25.nii.gz ↳ sub-001/ses-01/func/sub-001_ses-01_task-rest_dir-AP_bold.nii.gz
✓ Functional organisation complete.

  — EPI field-maps —
[INFO] sourcedata/nifti/sub-001/ses-01/0029/rfMRI_PA_29.nii.gz ↳ sub-001/ses-01/fmap/sub-001_ses-01_dir-PA_epi.nii.gz
✓ EPI field-map organisation complete.
```

### Generating events.tsv

```console
$ bidscomatic-cli events sourcedata/behavioural_task \
  --pattern '*MemoryTask*.csv' \
  --img-col image_file --task memory
=== events.tsv ===
[INFO] [events] discovered 2 sheet(s) under /home/user/MyBidsProject/sourcedata/behavioural_task
  • sub-001/ses-01
[INFO] [events] 001_MemoryTask.csv → 3 run(s) × 100 row(s)
[INFO] [events] wrote sub-001/ses-01/func/sub-001_ses-01_task-memory_run-01_events.tsv
  • sub-002/ses-02
[INFO] [events] 002_MemoryTask.csv → 3 run(s) × 100 row(s)
[INFO] [events] wrote sub-002/ses-02/func/sub-002_ses-02_task-memory_run-01_events.tsv
✓ 6 events.tsv file(s) written.
```

### Updating participants.tsv

```console
$ bidscomatic-cli participants \ 
    sourcedata/phenotype_raw/questionnaire.csv \
    --keep-cols Age,Sex,Group \
    --rename-cols Age=age,Sex=sex,Group=group \
    --map-values sex=0:M,1:F
=== participants.tsv ===
[INFO] [participants] discovered 3 subject folder(s)
  • sub-001
  • sub-002
  • sub-003
[INFO] [participants] loaded 10 row(s) from questionnaire.csv
[INFO] [participants] wrote participants.tsv (3 row(s))
✓ participants.tsv updated.
```

### Creating phenotype TSVs

```console
$ bidscomatic-cli questionnaires sourcedata/phenotype_raw/questionnaire.csv --session-mode single
=== questionnaires ===
[INFO] [questionnaires] questionnaire.csv → 3 row(s) × 100 column(s) after filtering
[INFO] [questionnaires] wrote phenotype/general_ses-01.tsv
[INFO] [phenotype-json] wrote phenotype/general_ses-01.json
✓ 12 TSV file(s) written in /home/user/MyBidsProject/phenotype
```

### Updating phenotype JSON

```console
$ bidscomatic-cli phenotype-json phenotype/mmq_abl_ses-01.tsv \
  --tool-description "Metamemory in Adulthood Questionnaire" \
  --tool-term-url https://example.com/mmq \
  --field-description mmq_abl_b="Ability sub-scale score (0–80)" \
  --field-units mmq_abl_b=score
[INFO] Wrote phenotype/mmq_abl_ses-01.json
```

### Running the BIDS validator

```console
$ bidscomatic-cli validate
=== Validate dataset ===
[INFO] Running bids-validator on: /home/user/MyBidsProject
bids-validator@1.15.0
✓ BIDS validation passed.
```

---

## 🛠️ Configuration – `series.yaml` & `files.yaml`

The toolkit ships robust defaults for *HCP‑style* naming, but every study can customise behaviour:

1. **Project‑local overrides** live in  `code/config/` at the dataset root.
2. Specify **only** the keys you need to change – everything else falls back to the packaged templates.
3. Both YAMLs are rigorously validated at launch via Pydantic models (`bidscomatic.config.schema`).

```yaml
# Minimal example (code/config/series.yaml)
version: "1.0"
modalities:
  anatomical:
    T1w:
      sequence_id: "T1w_MPR"
      bids:
        datatype: anat
        suffix: T1w
```

See [`resources/default_series.yaml`](./bidscomatic/resources/default_series.yaml) for the full schema with extensive inline docs.

## Environment variables

`BIDSCOMATIC_LOG_DIR` – optional path for JSON log files. When set, log
messages are written to this directory instead of `<BIDS_ROOT>/code/logs`.
If neither this variable nor a dataset root is supplied, JSON logs are
written to the package's own `logs/` directory.

---

##  Development workflow

```bash
ruff check .   # lint
black .        # formatter
pytest -c ../pytest.ini -q      # unit tests
mypy bidscomatic   # type‑checking
pytest -c ../pytest.ini --cov   # coverage report
```

CI runs exactly the same steps – please ensure the test suite passes before opening a PR.

---

##  Repository layout (abridged)

```
bidscomatic/
├── cli/            # Click entry‑points  (bidscomatic-cli …)
├── pipelines/      # Pure helpers for unzip/convert/bidsify flows
├── config/         # YAML loader + Pydantic schemas
├── resources/      # Packaged default YAML templates
└── utils/          # Re‑usable helpers (events, filters, slug, …)
```

---

##  License

`bidscomatic` is released under the **MIT License** – see the top‑level `LICENSE` file for details.

---

##  Acknowledgements & citation

If you use this software in your research, please cite the corresponding paper (pending) **or** acknowledge the toolkit in your methods section:

> *Data were converted and organised using bidscomatic (v0.1.1).*

Questions, feature requests, or bug reports? Please open an issue or start a discussion.
