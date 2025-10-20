# **bidscomatic**

*A CLI toolkit for end-to-end DICOM study orchestration – extraction, conversion, curation, preprocessing, QC and validation – into a BIDS‑compliant layout*

---

## 📚 Table of Contents

- [5‑minute Quickstart](#5-minute-quickstart)
- [Cheat‑sheet (command reference)](#cheat-sheet-command-reference)
- [Key features](#key-features)
- [Installation](#installation)
  - [Prerequisites](#prerequisites)
  - [Install dcm2niix](#installing-dcm2niix)
  - [Install Node.js & bids-validator](#installing-nodejs)
  - [Python install options](#python-install-options)
  - [OS support](#os-support)
  - [Environment & logging](#environment--logging)
- [Example dataset structure](#example-dataset-structure)
- [Common CLI options](#common-cli-options)
- [Guides](#guides)
  - [Example workflow (overview)](#example-workflow-overview)
  - [Unzipping DICOM archives](#unzipping-dicom-archives)
  - [Converting DICOM to NIfTI](#converting-dicom-to-nifti)
  - [BIDS Conversion](#bids-conversion)
  - [Generating events.tsv](#generating-eventstsv)
  - [Using configuration files](#using-configuration-files)
  - [Updating participants.tsv](#updating-participantstsv)
  - [Creating phenotype TSVs](#creating-phenotype-tsvs)
  - [Updating phenotype JSON metadata](#updating-phenotype-json-metadata)
  - [Running the BIDS validator](#running-the-bids-validator)
  - [Preprocessing](#preprocessing-bidscomatic-cli-preprocess)
    - [Deriving PEPOLAR fieldmaps](#deriving-pepolar-fieldmaps)
    - [Denoising with fMRIPost‑AROMA](#denoising-with-fmripost-aroma)
    - [Running fMRIPrep](#running-fmriprep)
    - [Generating EPI masks](#generating-epi-masks)
    - [Motion correction with FSL MCFLIRT](#motion-correction-with-fsl-mcflirt)
  - [QC](#qc-bidscomatic-cli-qc)
- [Configuration – `series.yaml` & `files.yaml`](#configuration--seriesyaml--filesyaml)
- [Contributing](#contributing)
- [Repository layout](#repository-layout-abridged)
- [License](#license)
- [Acknowledgements & citation](#acknowledgements--citation)

---

## 🚀 5‑minute Quickstart

A minimal **raw DICOMs → validated BIDS** flow. (See also the [cheat‑sheet](#cheat-sheet-command-reference) and [common options](#common-cli-options).)

```bash
# 1) Extract nested TAR/ZIP deliveries into structured DICOM folders
bidscomatic-cli unzip ~/Downloads/MRI_archives --rm-archives

# 2) Convert every DICOM series → NIfTI under sourcedata/nifti
bidscomatic-cli convert sourcedata/dicom --merge-by-name -j 8

# 3) Organise NIfTIs into BIDS folders
bidscomatic-cli bids sourcedata/nifti \
  --anat t1w,t2w \
  --func task=nback,rest \
  --dwi --epi --overwrite

# 4) Validate the BIDS structure
bidscomatic-cli validate
```

Show top‑level help (one command as a compass):

```bash
bidscomatic-cli --help
```

---

## 🔧 Cheat‑sheet (command reference)

| Sub‑command            | What it does                                                                 |
| ---------------------- | ---------------------------------------------------------------------------- |
| `init`                 | Create an empty BIDS dataset (writes `dataset_description.json`; renames folder unless `--no-rename-root`). |
| `unzip`                | Extract archives & optionally delete them or their DICOM folders.            |
| `convert`              | Parallel DICOM → NIfTI conversion powered by *dcm2niix*.                     |
| `bids`                 | Move NIfTIs into `anat/`, `func/`, `dwi/`, `fmap/` folders.                  |
| `dataset-description`  | Create or update `dataset_description.json`.                                 |
| `participants`         | Merge metadata & update `participants.tsv` (values can be recoded).          |
| `events`               | Turn behavioural sheets into `*_events.tsv`.                                 |
| `questionnaires`       | Split questionnaire CSV → tidy TSV(s) in `phenotype/`.                       |
| `phenotype-json`       | Create or update JSON side‑cars for questionnaire TSVs.                      |
| `validate`             | Run the Node bids-validator on the dataset.                                  |
| `qc`                   | Compute DVARS, FD and tSNR for BOLD runs.                                    |
| `preprocess`           | Wrap common preprocessing pipelines (PEPOLAR fieldmaps, fMRIPrep, ICA‑AROMA, EPI masks). |
| `fsl mcflirt`          | Run FSL MCFLIRT and generate FEAT‑style motion plots.                        |

Each command exposes `--help` with exhaustive options and live examples.

---

## ✨ Key features

| Capability                         | Why it matters                                                                                                          |
|------------------------------------|-------------------------------------------------------------------------------------------------------------------------|
| **One‑line DICOM → BIDS pipeline** | `bidscomatic-cli convert` wraps *dcm2niix* in parallel and writes deterministic folder trees.                           |
| **YAML‑driven mapping**            | Opinionated defaults ship in `resources/default_*.yaml`, yet every study can override series‑to‑BIDS rules per dataset. |
| **Idempotent & safe**              | Existing files are **never** overwritten unless `--overwrite` is supplied.                                              |
| **Rich sub‑commands**              | Unzip archives, curate participants & events, build questionnaires – all from one CLI.                                  |
| **Pure‑Python, MIT‑licensed**      | No compiled extensions; runs on Linux & macOS with Python ≥ 3.9.                                                        |
| **Robust preprocessing**           | `bidscomatic-cli preprocess` wraps PEPOLAR fieldmaps, fMRIPrep, fMRIPost‑AROMA and EPI mask generation.                 |
| **Quick QC metrics**               | `bidscomatic-cli qc` computes DVARS, FD and tSNR for BOLD runs.                                                         |

---

## Installation

### Prerequisites

- **Python ≥ 3.9**
- [`dcm2niix`](https://github.com/rordenlab/dcm2niix) available on your `$PATH`
- **Node.js & npm** (install via your OS package manager)
- **`bids-validator`** (`npm install -g bids-validator`) – required by `validate`

### Installing `dcm2niix`

`bidscomatic` expects the `dcm2niix` binary to be discoverable on your `PATH`.

```bash
# Ubuntu/Debian
sudo apt install dcm2niix

# macOS (Homebrew)
brew install dcm2niix
```

Alternatively grab a pre-built release from the upstream repo and place it on your `PATH`.

### Installing Node.js

Node.js is required for the BIDS Validator used by the `validate` sub-command.

```bash
# macOS (Homebrew)
brew install node

# Ubuntu/Debian
sudo apt install nodejs npm

# Then install validator
npm install -g bids-validator
```

### Python install options

**a) Editable install inside a larger repo**

```bash
# From your repository root (monorepo style)
pip install -e path/to/bidscomatic
```

**b) Stand‑alone development clone**

```bash
git clone https://github.com/<your‑org>/bidscomatic.git
cd bidscomatic
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"   # core + testing/lint extras
```

### OS support

Runs on **Linux** and **macOS**. On Windows, use **WSL2** or a Linux/macOS host for full support.

### Environment & logging

- `BIDSCOMATIC_LOG_DIR` – optional path for JSON log files. When set, logs are written there instead of `<BIDS_ROOT>/code/logs`.  
  If neither this variable nor a dataset root is supplied, JSON logs live under the package `logs/` directory.
- Verbosity: pass `--verbose` or `--debug` on any command for more detail.

---

## 📂 Example dataset structure

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
    │   │   └── ...
    │   ├── run1_taskB/
    │   └── ...
    ├── cfmm2tar/
    │   ├── metadata.json
    │   └── sub-001/
    │       └── ExampleStudy/
    │           ├── study_20240101.attached.tar
    │           ├── study_20240101.tar
    │           └── study_20240101.uid
    ├── dicom/
    │   ├── metadata.json
    │   └── sub-001/
    │       └── ses-01/
    │           └── ExampleStudy/
    │               ├── study_20240101.attached.tar
    │               ├── study_20240101.tar
    │               └── study_20240101.uid
    └── phenotype_raw/
        └── questionnaire.csv
```

---

## Common CLI options

These options are accepted by most commands (`unzip`, `convert`, `bids`, `events`, `participants`, etc.).

- `--filter-sub <ID[,ID…]>` – process only these **subject** IDs (without the `sub-` prefix).  
- `--filter-ses <ID[,ID…]>` – process only these **session** IDs (without the `ses-` prefix).  
  You can repeat the option or pass comma-separated values.
- `--overwrite` – allow regeneration of existing outputs.
- `--verbose` / `--debug` – increase log verbosity.

Example:

```bash
bidscomatic-cli convert sourcedata/dicom --filter-sub 001,002 --filter-ses 02
```

---

## Guides

### Example workflow (overview)

1. `unzip` archives → DICOM folders  
2. `convert` DICOM → NIfTI under `sourcedata/nifti`  
3. `bids` promote into `anat/`, `func/`, `dwi/`, `fmap/`  
4. `events` build `*_events.tsv` from behavioural logs (optional)  
5. `participants` / `questionnaires` curate phenotype files (optional)  
6. `validate` the dataset  
7. `preprocess` (PEPOLAR / fMRIPrep / AROMA / EPI masks)  
8. `qc` metrics for BOLD data  

See [Common CLI options](#common-cli-options) for filters/verbosity used across commands.

### Unzipping DICOM archives

Use `bidscomatic-cli unzip` to expand nested TAR/ZIP deliveries into structured DICOM folders.

| Flag | Description |
| --- | --- |
| `--rm-archives` | Delete original TAR/ZIP files after successful extraction. |

Example:

```bash
bidscomatic-cli unzip sourcedata/dicom
```

Example output (abridged):

```text
=== Unzip archives ===
[INFO] Unzipping: sourcedata/dicom/sub-001/ses-01
[INFO] Found 2 archive(s)
[INFO] Unpacking TAR: .../sub-001_ses-01.tar → .../sub-001/ses-01
✓ 2 archive(s) unpacked
```

### Converting DICOM to NIfTI

Wrap `dcm2niix` with subject/session discovery, parallel execution and deterministic output naming.

| Flag | Description |
| --- | --- |
| `--merge-by-name` | Combine DICOM series that share the same sequence name before conversion. |

```bash
bidscomatic-cli convert sourcedata/dicom
```

Example output (abridged):

```text
=== Convert DICOM ===
[INFO] Found 27 image series for sub-001 ses-01
[INFO] ✓ 27 series → 650 file(s) written under sourcedata/nifti
```

### BIDS Conversion

Promote NIfTIs into the canonical `anat/`, `func/`, `dwi/` and `fmap/` hierarchy with on‑the‑fly entity detection.

| Flag | Description |
| --- | --- |
| `--anat <series[,series…]>` | Declare anatomical series (e.g., `t1w,t2w`) to promote into `anat/`. |
| `--func <task=labels[,task=labels…]>` | Map functional runs to task labels (e.g., `task=nback,rest`). |
| `--dwi` | Include diffusion-weighted series during BIDS promotion. |
| `--epi` | Include EPI fieldmaps during BIDS promotion. |
| `--overwrite` | Replace existing BIDS outputs when regenerating files. |

```bash
bidscomatic-cli bids sourcedata/nifti --anat t1w --func task=memory,rest --epi
```

Example output (abridged):

```text
=== Organise BIDS ===
[INFO] Picked T1w.nii.gz → sub-001/ses-01/anat/sub-001_ses-01_T1w.nii.gz
[INFO] rfMRI_TASK_AP_16.nii.gz → sub-001/ses-01/func/sub-001_ses-01_task-memory_dir-AP_run-01_bold.nii.gz
[INFO] rfMRI_REST_AP_25.nii.gz → sub-001/ses-01/func/sub-001_ses-01_task-rest_dir-AP_bold.nii.gz
[INFO] rfMRI_PA_29.nii.gz → sub-001/ses-01/fmap/sub-001_ses-01_dir-PA_epi.nii.gz
✓ BIDS organisation complete.
```

### Generating `events.tsv`

Transform behavioural spreadsheets into BIDS‑compatible `*_events.tsv` files.

| Flag | Description |
| --- | --- |
| `--pattern <glob>` | Select behavioural files to ingest using glob patterns. |
| `--img-col <name>` | Column for stimulus file references. |
| `--response-cols <cols>` | Coalesce multiple response columns into a single `response`. |
| `--onset-cols <cols>` | Provide onset column(s); supports per-group default durations (`duration=...`). |
| `--rt-cols <cols>` | Reaction-time columns aligned with onset groups. |
| `--task <label>` | Set the BIDS `task-` entity. |
| `--duration <seconds>` / `--duration-col <name>` | Fixed or per-row trial durations. |
| `--trialtype-col <name>` | Reuse an existing column as `trial_type`. |
| `--trialtype-patterns <map>` | Remap raw trial labels. |
| `--regex-map ...` / `--map-values ...` | Derive or recode columns via declarative mappings. |
| `--synth-rows ...` | Insert synthetic instruction rows. |
| `--set ...`, `--drop ...` | Adjust or prune rows/columns. |
| `--keep-raw-stim` | Preserve original stimulus paths in `stim_file`. |
| `--create-stimuli-directory` | Copy referenced stimulus assets into `<BIDS_ROOT>/stimuli`. |
| `--create-events-json` | Emit companion `*_events.json` files. |
| `--field-description`, `--field-units`, `--field-levels` | Document columns in sidecars. |
| `--json-spec <path>` | Merge a JSON template into each side‑car. |

Minimal example:

```bash
bidscomatic-cli events sourcedata/behavioural_task \
  --pattern '*MemoryTask*.csv' \
  --onset-cols 'encodeTrialRun1_Image.started,recogTrialRun1_Image.started duration=3.000' \
  --task assocmemory
```

Example output (abridged):

```text
=== events.tsv ===
[INFO] wrote sub-002/ses-01/func/sub-002_ses-01_task-assocmemory_run-01_events.tsv
[INFO] wrote sub-002/ses-01/func/sub-002_ses-01_task-assocmemory_run-02_events.tsv
[INFO] wrote sub-002/ses-01/func/sub-002_ses-01_task-assocmemory_run-03_events.tsv
```

#### File naming and derived columns (highlights)

- **Phase encoding suffixes** – When a matching `*_bold.json` includes `PhaseEncodingDirection`, a `dir-<phase>` entity (e.g., `dir-AP`) is added to events filenames; falls back to classic naming otherwise.
- **Transforming columns** – Flags like `--regex-map`, `--map-values`, `--join-value`, `--set`, `--drop`, `--synth-rows` can derive/recode columns and insert instruction rows.

#### Reusing existing columns

- **Durations** – Point `--duration-col` at a timing column. Non‑numeric rows fall back to the group’s `duration=` or global `--duration` default.
- **Trial labels** – Keep `--trialtype-col <column>` and optionally remap with `--trialtype-patterns`.

Another example with richer operators (abridged for readability):

```bash
bidscomatic-cli events sourcedata/behavioural_task \
  --pattern '*MemoryTask*.csv' \
  --img-col image_file \
  --response-cols 'response_old_new,response_pair_fit,response_gender,response_water' \
  --onset-cols 'encodeTrialRun1_Image.started,recogTrialRun1_Image.started,encodeTrialRun2_Image.started,recogTrialRun2_Image.started,encodeTrialRun3_Image.started,recogTrialRun3_Image.started duration=3.000' \
  --rt-cols 'encodeTrialTestKeyRespRun1.rt,recogTrialTestKeyRespRun1.rt,encodeTrialTestKeyRespRun2.rt,recogTrialTestKeyRespRun2.rt,encodeTrialTestKeyRespRun3.rt,recogTrialTestKeyRespRun3.rt' \
  --task assocmemory \
  --keep-cols 'trial_type,stim_file,response_time,response' \
  --trialtype-patterns 'Pair_Encoding=encoding_pair;Face_Encoding=encoding_face;Place_Encoding=encoding_place;Pair_Recog=recog_pair;Face_Recog=recog_face;Place_Recog=recog_place' \
  --regex-map 'newcol=phase from=trial_type map=encoding:^(?:enc|encoding)_;recognition:^(?:rec|ret|recogn)[a-z]*_;instruction:^instruction' \
  --regex-extract 'newcol=condition from=trial_type pattern=_(\w+)$ group=0 apply-to=phase!="instruction"' \
  --id-from 'newcol=stim_id from=stim_file func=basename' \
  --synth-rows 'when=block-start groupby=phase,condition onset=first.onset-10 duration=10 clamp-zero=true set=trial_type=fmt("instruction_{condition}_{phase}");is_instruction=1' \
  --join-membership 'newcol=probe_type keys=condition,stim_id exists-in=phase=="encoding" apply-to=phase=="recognition" true-value=target false-value=lure' \
  --regex-map 'newcol=choice from=response casefold=true map=old:^\s*old\s*$;new:^\s*new\s*$;no_response:^\s*$' \
  --set 'when=(phase=="recognition") & (choice=="old") & (probe_type=="target") set=acc_label=hit' \
  --set 'when=(phase=="recognition") & (choice=="old") & (probe_type=="lure")   set=acc_label=false_alarm' \
  --set 'when=(phase=="recognition") & (choice=="new") & (probe_type=="lure")   set=acc_label=correct_rejection' \
  --set 'when=(phase=="recognition") & (choice=="new") & (probe_type=="target") set=acc_label=miss' \
  --set 'when=(phase=="recognition") & (choice=="no_response")                  set=acc_label=no_response' \
  --set 'when=acc_label=="" set=acc_label=n/a' \
  --join-value 'newcol=enc_later_outcome value-from=acc_label keys=condition,stim_id from-rows=phase=="recognition" to-rows=phase=="encoding" default=not_tested' \
  --exists-to-flag 'newcol=enc_is_tested keys=condition,stim_id from-rows=phase=="recognition" to-rows=phase=="encoding" true=1 false=0' \
  --flag 'newcol=is_error expr=((phase=="recognition") & ((acc_label=="miss") | (acc_label=="false_alarm") | (acc_label=="no_response"))) | ((phase=="encoding") & (enc_later_outcome=="miss")) true=1 false=0' \
  --index 'newcol=trial_n groupby=phase,condition orderby=onset start=1' \
  --set 'when=phase=="instruction" set=trial_n=n/a' \
  --map-values 'newcol=block_n from=phase map=encoding=1;recognition=2;instruction=n/a' \
  --flag 'newcol=analysis_include expr=(phase=="recognition") & ((acc_label=="hit") | (acc_label=="correct_rejection")) true=1 false=0' \
  --keep-cols-if-exist 'onset,duration,trial_type,stim_file,response_time,response,phase,condition,stim_id,acc_label,probe_type,enc_is_tested,enc_later_outcome,is_instruction,is_error,block_n,trial_n,analysis_include' \
  --create-stimuli-directory \
  --create-events-json \
  --field-description response="Raw participant response (phase-specific; e.g., old/new for recognition; pair_fit/gender/water during encoding)." \
  --field-description acc_label="Signal detection outcome for recognition trials (hit/miss/correct_rejection/false_alarm/no_response)." \
  --field-description onset="Start time of the event measured from the beginning of the run." \
  --field-description duration="Duration of the event." \
  --field-description trial_type="Experimental condition label for each trial." \
  --field-description stim_file="Relative path (from the dataset root) to the bitmap shown on that trial. Paths should begin with 'stimuli/'." \
  --field-description response_time="Latency between stimulus onset and the participant’s button press." \
  --field-description phase="Stage parsed from trial_type (encoding/recognition/instruction)." \
  --field-description condition="Condition parsed from trial_type (e.g., face/place/pair)." \
  --field-description stim_id="Basename of stim_file; used as join key across phases." \
  --field-description probe_type="For recognition, target if a matching encoding instance exists in the run; else lure." \
  --field-description enc_is_tested="For encoding trials, whether a recognition probe occurred for this item in the run (0/1)." \
  --field-description enc_later_outcome="For encoding trials, the recognition outcome for the same item, or not_tested." \
  --field-description is_instruction="Instruction row placed at each (phase,condition) block start (10 s before first trial)." \
  --field-description is_error="Incorrect/missed recognition or encoding item later missed (0/1)." \
  --field-description block_n="Within-run block index: encoding=1, recognition=2, instruction=n/a." \
  --field-description trial_n="Within (phase,condition), 1-based trial index ordered by onset; blank on instruction." \
  --field-description analysis_include="Mask flag for correct trials (hit/correct_rejection) (0/1)." \
  --field-units response_time=seconds \
  --field-levels probe_type="target:Old (studied) item;lure:New (unstudied) item"
```

Key operators used above (and how to adapt them to **your** study)

#### Ingest & basic columns
* `--pattern` – which files to read (glob). Point it at your task logs (CSV/TSV/XLSX).
* `--img-col` and `--response-cols` – the listed response columns are **coalesced** left‑to‑right into a single `response` column (first non‑empty per row wins). This removes the need for `--accuracy-col`.
* `--onset-cols` – one or more onset columns; you can list multiple per run and assign a default `duration=...` (overridden later for instructions). **Tip:** columns that include `Run1`, `Run2`, … are auto‑matched to RT columns with the same run number.
* `--rt-cols` – reaction‑time columns; the matching run’s RT column is used (non‑numeric are coerced to NA).
* `--task` – the task entity injected into output filenames (e.g., `task-assocmemory`).
* `--keep-cols` – preserve additional raw columns alongside the mandatory `onset`/`duration`.

#### Parse trial structure
* `--trialtype-patterns` – maps raw strings (often in `stim_file` or an existing trial label) to concise labels (e.g., `Face_Recog` → `recog_face`). Update these to match your naming.
* `--trialtype-col` – reuse an existing column as `trial_type`. Combine with `--trialtype-patterns` to remap values when needed.
* `--regex-map newcol=phase` – derives a `phase` column by regex‑matching `trial_type` to `encoding`/`recognition`/`instruction`.
* `--regex-extract newcol=condition` – pulls the condition (e.g., `face`, `place`, `pair`) from the tail of `trial_type`.
* `--id-from newcol=stim_id` – derives an item ID from the `stim_file` basename for cross‑phase joining (e.g., link recognition probes back to encoding items).

#### Insert synthetic rows (block instructions)
* `--synth-rows` – inserts an instruction row at the start of each `(phase,condition)` block (`onset=first.onset-10`, `duration=10s`), optionally clamping negative onsets to zero. Sets sensible defaults (e.g., `is_instruction=1`, `is_error=0`). Adjust onset/duration to your paradigm.

#### Normalise responses → accuracy labels
* `--regex-map 'newcol=choice from=response …'` – normalises free‑text into canonical **choices**: `old`, `new`, or `no_response` (edit the regexes to your labels).
* `--join-membership newcol=probe_type` – marks recognition trials as `target` if a matching `(condition, stim_id)` exists in encoding; otherwise `lure` (within‑run membership).
* `--set … set=acc_label=…` – derives **signal‑detection outcomes** from `choice × probe_type` (on recognition only):
  * `old` + `target` → `hit`
  * `old` + `lure` → `false_alarm`
  * `new` + `lure` → `correct_rejection`
  * `new` + `target` → `miss`
  * `no_response` → `no_response`
* `--set 'when=acc_label=="" set=acc_label=n/a'` – makes blank outcomes explicit.

#### Cross‑phase relationships
* `--join-value newcol=enc_later_outcome` – writes each encoding item’s later recognition outcome (`hit/miss/…` or `not_tested`).
* `--exists-to-flag newcol=enc_is_tested` – flags encoding items that were later probed (`0/1`).

#### Define analytic flags & indices
* `--flag newcol=is_error …` – `1` for incorrect/missed recognition (`miss`, `false_alarm`, `no_response`) and for encoding items later missed; else `0`.
* `--index newcol=trial_n` – numbers trials within `(phase,condition)` ordered by `onset`, starting at 1.
* `--set 'when=phase=="instruction"'` – blanks `trial_n` on instruction rows.
* `--map-values newcol=block_n` – encodes block order (`encoding=1`, `recognition=2`).
* `--flag newcol=analysis_include` – mask for correct recognition only (`hit/correct_rejection`).

#### Select columns & write metadata
* `--keep-cols-if-exist` – keeps only analysis‑ready columns if present.
* `--create-stimuli-directory` – copies any referenced image files into `<BIDS_ROOT>/stimuli` (paths in `stim_file` become dataset‑relative).
* `--create-events-json + --field-*` – emits per‑run `*_events.json` side‑cars with human‑readable descriptions, units and categorical level docs.

**Adapting to your study – quick checklist**  
1) Replace `--pattern` to match your filenames.  
2) Point `--img-col`, `--response-cols`, `--onset-cols`, and `--rt-cols` at the columns in your sheets.  
3) Update the regexes in `--trialtype-patterns`, `--regex-map newcol=phase`, and `--regex-map newcol=choice`.  
4) If durations vary per trial, add `--duration-col <col>`.  
5) Align `--rt-cols` with runs if they don’t include `Run1/Run2/...`.  
6) For extra outcomes (e.g., confidence), derive a separate label column.  
7) Validate a single subject first and inspect the resulting `*_events.tsv`.

### Using configuration files

Keep the command line concise by moving settings into a config file:

```yaml
version: 1
command: events
task: assocmemory
# (abridged) – see the bundled example below for the full schema
```

The full example is bundled at
[`bidscomatic/resources/examples/events_assocmemory.yaml`](./bidscomatic/resources/examples/events_assocmemory.yaml).  
A minimal skeleton template lives at
[`bidscomatic/resources/events_template.yaml`](./bidscomatic/resources/events_template.yaml).

### Updating `participants.tsv`

Curate a `participants.tsv` with renaming, recoding and column filtering controls.

| Flag | Description |
| --- | --- |
| `--keep-cols <cols>` | Retain only the listed columns from the input spreadsheets. |
| `--rename-cols <map>` | Rename incoming columns using `source=target` pairs. |
| `--map-values <map>` | Recode categorical values (e.g., `group=0:control,1:intervention`). |

```bash
bidscomatic-cli participants \
  sourcedata/phenotype_raw/questionnaire.csv \
  --keep-cols Age,Sex,Group \
  --rename-cols Age=age,Sex=sex,Group=group \
  --map-values group=0:control,1:intervention \
  --map-values sex=0:M,1:F
```

Example output (abridged):

```text
=== participants.tsv ===
[INFO] discovered 3 subject folder(s)
[INFO] wrote participants.tsv (3 row(s))
✓ participants.tsv updated.
```

### Creating phenotype TSVs

Turn raw survey spreadsheets into tidy `phenotype/*.tsv` outputs with sidecar metadata and consistent participant/session keys.

| Flag | Description |
| --- | --- |
| `--session-mode {single,split,...}` | Control how questionnaire rows map onto sessions. |
| `--all-subjects` | Include subjects even when no responses are present. |
| `--tool-description <text>` | Describe the assessment tool in generated JSON side-cars. |
| `--tool-term-url <URL>` | Link to the questionnaire or ontology entry. |
| `--field-description <col=text>` | Document questionnaire columns in the side-car. |
| `--field-units <col=unit>` | Provide measurement units for numeric responses. |

```bash
bidscomatic-cli questionnaires sourcedata/phenotype_raw/questionnaire.csv --session-mode single
```

Example output (abridged):

```text
=== questionnaires ===
[INFO] wrote phenotype/general_ses-01.tsv
[INFO] wrote phenotype/general_ses-01.json
✓ 12 TSV file(s) written.
```

### Updating phenotype JSON metadata

```bash
bidscomatic-cli phenotype-json phenotype/mmq_abl_ses-01.tsv \
  --tool-description "Metamemory in Adulthood Questionnaire" \
  --tool-term-url https://example.com/mmq \
  --field-description mmq_abl_b="Ability sub-scale score (0–80)" \
  --field-units mmq_abl_b=score
```

Example output:

```text
[INFO] wrote phenotype/mmq_abl_ses-01.json
```

### Running the BIDS validator

Shell out to the official Node.js `bids-validator` and sanity‑check your dataset before sharing.

```bash
bidscomatic-cli validate
```

Example output:

```text
=== Validate dataset ===
bids-validator@1.15.0
✓ BIDS validation passed.
```

### Preprocessing (`bidscomatic-cli preprocess`)

#### Deriving PEPOLAR fieldmaps

Compute *topup*-ready spin‑echo pairs that correct susceptibility distortions across BOLD runs, automatically pairing opposing phase-encoding directions and writing BIDS-compliant fieldmap derivatives.

```bash
# Derive using all BOLD runs for subject 002 session 01
bidscomatic-cli preprocess pepolar --filter-sub 002 --filter-ses 01

# Limit to a task only
bidscomatic-cli preprocess pepolar --filter-sub 002 --filter-ses 01 --task assocmemory

# Preview outputs without touching disk
bidscomatic-cli preprocess pepolar --filter-sub 002 --filter-ses 01 --dry-run

# Emit IntendedFor entries as BIDS URIs
bidscomatic-cli preprocess pepolar --filter-sub 002 --filter-ses 01 --use-bids-uri 1
```

Example output (abridged):

```text
=========================
   PEPOLAR — Subject: sub-005
=========================
Created session-level opposite-PE EPI: sub-005/ses-01/fmap/sub-005_ses-01_dir-PA_epi.nii.gz
```

#### Denoising with fMRIPost‑AROMA

Run the fMRIPost‑AROMA container on preprocessed BOLD data, classifying ICA components as signal or noise and generating non‑aggressive denoised outputs alongside provenance logs.

```bash
bidscomatic-cli preprocess aroma --subjects 005 \
  --bids-filter-file derivatives/work/fmripost_aroma/bids_filters_assocmemory.json
```

Generate a filter file on‑the‑fly:

```bash
bidscomatic-cli preprocess aroma --subjects 005 \
  --create-filter task=memory \
  --task memory
```

#### Running fMRIPrep

Orchestrate the full fMRIPrep anatomical and functional pipelines with automatic resource tuning, FreeSurfer surface reconstruction support and BIDS‑Derivatives‑compliant layout.

```bash
bidscomatic-cli preprocess fmriprep --fs-license /path/to/license.txt
```

#### Generating EPI masks

Create robust brain masks for each `_desc-preproc_bold` image, natively via Nilearn or using containerised fMRIPrep.

```bash
bidscomatic-cli preprocess epi-mask --prep-dir derivatives/fmriprep
```

#### Motion correction with FSL MCFLIRT

Fast rigid-body alignment of BOLD runs along with FEAT‑style plots.

```bash
bidscomatic-cli fsl mcflirt sub-001_ses-01_task-rest_bold.nii.gz
# or
bidscomatic-cli fsl mcflirt --i derivatives/fmriprep/sub-001/ses-01/func
```

### QC (`bidscomatic-cli qc`)

Summarise BOLD data quality by computing DVARS, framewise displacement and tSNR. Results are written to CSV in the current directory; per-run TSV series can be saved with `--save-series`.

```bash
bidscomatic-cli qc \
  -i derivatives/sub-01/func \
  --space MNI152NLin6Asym_res-2 \
  --calc-dvars --calc-tsnr \
  --fd-from confounds --save-series
```

---

## 🛠️ Configuration – `series.yaml` & `files.yaml`

The toolkit ships robust defaults for *HCP‑style* naming, but every study can customise behaviour:

1. **Project‑local overrides** live in `code/config/` at the dataset root.
2. Specify **only** the keys you need to change – everything else falls back to the packaged templates.
3. Both YAMLs are validated at launch via Pydantic models (`bidscomatic.config.schema`).

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

See the full defaults at [`resources/default_series.yaml`](./bidscomatic/resources/default_series.yaml).

---

## Contributing

We welcome issues, discussions and pull requests. Before opening a PR, please ensure the test suite passes locally.

```bash
ruff check .       # lint
black .            # format
mypy bidscomatic   # type‑check
pytest -c ../pytest.ini -q           # unit tests
pytest -c ../pytest.ini --cov        # coverage report
```

- Start a discussion or report a bug in the repo’s **Issues/Discussions** tabs.
- CI runs the same steps shown above.

---

## Repository layout (abridged)

```text
bidscomatic/
├── cli/            # Click entry‑points  (bidscomatic-cli …)
├── pipelines/      # Helpers for unzip/convert/bidsify flows
├── config/         # YAML loader + Pydantic schemas
├── resources/      # Packaged default YAML templates
└── utils/          # Re‑usable helpers (events, filters, slug, …)
```

---

## License

`bidscomatic` is released under the **MIT License** – see the top‑level `LICENSE` file for details.

---

## Acknowledgements & citation

If you use this software in your research, please cite the corresponding paper (pending) **or** acknowledge the toolkit in your methods section:

> *Data were converted and organised using bidscomatic (v0.1.1).*

Questions, feature requests, or bug reports? Please open an issue or start a discussion.
