> **dicomatic – Terminal-native DICOM ⇄ BIDS data wrangler.**
>
> *Query PACS, download archives, and curate BIDS trees with one coherent CLI (and an optional TUI).*

---

## Contents

- [Overview](#overview)
- [Quick-start cheat sheet](#quick-start-cheat-sheet)
  - [From zero to first BIDS download (5 steps)](#from-zero-to-first-bids-download-5-steps)
- [Highlights](#highlights)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
  - [Install inside MyBidsApp](#install-inside-mybidsapp)
  - [Standalone clone](#standalone-clone)
- [Configuration](#configuration)
  - [Config search order](#config-search-order)
  - [Sample YAML](#sample-yaml)
- [Command reference (cheat-sheet)](#command-reference-cheat-sheet)
- [Repository layout](#repository-layout)
- [CLI usage](#cli-usage)
  - [Credentials](#credentials)
  - [TUI walkthrough](#tui-walkthrough)
  - [Listing studies](#listing-studies)
  - [Downloading](#downloading)
  - [Additional download options](#additional-download-options)
- [Contributing / Development](#contributing--development)
- [License](#license)

---

## Overview

`dicomatic` is a Click-based CLI plus lightweight helper library that translates DICOM PACS queries into BIDS-friendly downloads. It wraps dcm4che’s `findscu` utilities and the [`cfmm2tar`](https://github.com/uwo-cfmm/cfmm2tar) container, so the same commands work on Linux, macOS, and Windows (via WSL).

---

## Quick-start cheat sheet

### From zero to first BIDS download (5 steps)

1. **Configure access** – export credentials or create a secret file:

   ```bash
   export DICOM_USERNAME="myuser"
   export DICOM_PASSWORD="mys3cret"
   ```

2. **List studies** matching a StudyDescription:

   ```bash
   dicomatic-cli bids \
     -d 'ACMELAB^BRAIN_HEALTH' \
     --list-studies \
     --demographics
   ```

3. **Filter** the sessions/subjects you care about (optional):

   ```bash
   dicomatic-cli bids \
     -d 'ACMELAB^BRAIN_HEALTH' \
     --reassign-session 071:01=072 \
     --filter-session 072:01 \
     --no-numeric-sessions
   ```

4. **Download** archives & metadata into `sourcedata/dicom/`:

   ```bash
   dicomatic-cli bids \
     -d 'ACMELAB^BRAIN_HEALTH' \
     --reassign-session 071:01=072 \
     --filter-session 072:01 \
     --no-numeric-sessions \
     --download \
     --demographics \
     --create-metadata
   ```

5. **Inspect output** – verify `.tar` archives and the merged `metadata.json` were created under `sourcedata/dicom/sub-*/ses-*`.

---

## Highlights

| Capability | Why it matters |
| --- | --- |
| **One CLI, many workflows** | Scriptable `query`, `download`, `bids`, `metadata`, and `patients` sub-commands, plus a guided TUI. |
| **Docker-powered cfmm2tar** | Guarantees consistent downloads on any OS with Docker. |
| **Automatic BIDS mapping** | `PatientName` + acquisition date drive sub-/ses- naming; overrides for custom nomenclature. |
| **YAML-first configuration** | Drop a single file to set PACS endpoints, Docker image, and naming rules; secrets via env vars. |
| **Idempotent downloads** | Existing archives are reused; manifests merge on StudyInstanceUID. |
| **Pure Python ≥ 3.8** | No database, no compiled extensions – easy to hack on and ship. |

---

## Prerequisites

- Python ≥ 3.8
- Docker Engine (desktop or server)
- Network access to the target PACS (AET, host, port, TLS mode)
- `cfmm2tar` Docker image available locally (`docker pull uwoce/cfmm2tar:<tag>`)

> **Apple Silicon heads-up:** when pulling the container, add `--platform linux/amd64` if the registry lacks native arm64 images.

---

## Installation

### Install inside MyBidsApp

```bash
# from the repository root
pip install -e code/MyBidsApp/dicomatic
```

### Standalone clone

```bash
git clone https://github.com/<your-org>/dicomatic.git
cd dicomatic
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"    # core + lint/test extras
```

---

## Configuration

### Config search order

`dicomatic` looks for configuration in the following order:

1. `--config /path/to/file.yaml` (explicit flag)
2. `~/.config/dicomatic.yaml`
3. Repository override at `code/MyBidsApp/dicomatic/config/config.yaml`
4. Built-in defaults bundled with the package

Environment variables (`DICOM_USERNAME`, `DICOM_PASSWORD`, etc.) always win over values defined in YAML.

### Sample YAML

```yaml
# ~/.config/dicomatic.yaml

dicom:
  container: "uwoce/cfmm2tar:latest"
  server: "MYAET@pacs.example.org"
  port: 11112
  tls: "none"              # aes | ssl | none
  username: "${DICOM_USERNAME}"
  password: "${DICOM_PASSWORD}"

dicom_query_tags:
  - PatientName
  - StudyDescription
  - StudyDate
  - StudyInstanceUID

session_map:
  baseline: "01"
  followup: "02"

bids:
  root: "/data/bids_dataset"
  sourcedata: "sourcedata/dicom"
```

Place the file anywhere you like and point to it with `--config`. Dropping a copy into the repository’s `config/config.yaml` lets teammates share defaults.

---

## Command reference (cheat-sheet)

| Command | Purpose |
| --- | --- |
| `dicomatic-cli query` | Free-form StudyDescription search with optional interactive download prompt. |
| `dicomatic-cli patients` | Enumerate distinct PatientName values and trigger targeted downloads. |
| `dicomatic-cli download` | Pull archives directly by StudyInstanceUID and/or StudyDescription. |
| `dicomatic-cli bids` | End-to-end BIDS workflow: list, filter, download, and build metadata. |
| `dicomatic-cli metadata` | Generate or merge `metadata.json` manifests without re-downloading. |

Append `--help` to any command for the exhaustive flag list.

---

## Repository layout

```
dicomatic/
├── cli.py                 # Root Click entry point
├── commands/              # query, bids, download, metadata, patients
├── config/                # default YAML + loaders
├── query/                 # findscu builder/runner/parsers
├── utils/                 # auth, display, planning, naming helpers
└── models.py              # DownloadPlan and dataclasses
```

---

## CLI usage

### Credentials

`dicomatic` reads PACS credentials from environment variables, CLI flags, or a `.mysecrets` file. Choose whichever fits your workflow:

- **Environment variables** (preferred for scripting):

  ```bash
  export DICOM_USERNAME="operator"
  export DICOM_PASSWORD="supersecret"
  export DICOM_PROJECT="DemoBrainHealth"
  ```

- **Command-line flags** (`--username`, `--password`) – useful in CI when secrets are injected per run.

- **Secret file** stored at the BIDS root – create it with a short Bash snippet:

  ```bash
  BIDS_ROOT=/data/bids_dataset
  mkdir -p "$BIDS_ROOT"
  cat <<'EOF' > "$BIDS_ROOT/.mysecrets"
  {
    "username": "operator",
    "password": "supersecret"
  }
  EOF
  ```

  This writes a JSON secrets file that you can later reuse with
  `dicomatic-cli bids --mysecrets "$BIDS_ROOT/.mysecrets"`. Adjust the
  `BIDS_ROOT`, `username`, and `password` values to match your environment, and
  protect the file with restrictive permissions (`chmod 600`).

### TUI walkthrough

Launch the interactive text UI and explore subjects/sessions visually:

```bash
dicomatic-cli bids -d 'ACMELAB^BRAIN_HEALTH'
```

You can reuse the existing example session log (below) to orient new users:

```text
[==== DICOMATIC - DICOM Query & Download ====]

1) List & download studies (cfmm2tar)
2) BIDS workflow: group / filter / download
3) Search by PatientName & custom download

Choose an option (1, 2, 3)
> 2

=== Subject: sub-101 ===

-- Session: ses-01 --
+----------+---------------------------+------+-----+--------------------------------------------+
| Date     | Patient                   | Age  | Sex | UID                                        |
+----------+---------------------------+------+-----+--------------------------------------------+
| 20240105 | 2024_01_05_101_visit1     | 050Y | F   | 1.2.840.999999.1.1.1011                    |
+----------+---------------------------+------+-----+--------------------------------------------+

…
```

Answer the prompts to download specific subjects/sessions and optionally regenerate `metadata.json`.

### Listing studies

Preview the available studies for a given StudyDescription, optionally including demographic details stored in DICOM headers:

```bash
dicomatic-cli bids \
  -d 'ACMELAB^BRAIN_HEALTH' \
  --list-studies \
  --demographics
```

### Downloading

Download everything for a description, while remapping sessions and forcing human-friendly labels:

```bash
dicomatic-cli bids \
  -d 'ACMELAB^BRAIN_HEALTH' \
  --reassign-session 071:01=072 \
  --filter-session 072:01 \
  --no-numeric-sessions \
  --demographics \
  --download \
  --create-metadata
```

Filter multiple sessions (or subjects) in one go, exclude specific UIDs, and avoid numeric session labels:

```bash
dicomatic-cli bids \
  -d 'ACMELAB^BRAIN_HEALTH' \
  --filter-session 064:01 \
  --filter-session 066:01 \
  --exclude-uid 9.9.999999.1.2.20230801125107586 \
  --no-numeric-sessions \
  --download \
  --create-metadata
```

Target an alternate project, skip a subject, and keep sessions textual:

```bash
dicomatic-cli bids \
  -d 'NAGAMATSU^SELFEFFICACY' \
  --filter-session ses-01 \
  --exclude-subject 001 \
  --no-numeric-sessions \
  --demographics \
  --download \
  --create-metadata
```

### Additional download options

- `--create-metadata` merges new entries into `metadata.json` alongside demographic tags.
- `--demographics` includes Age, Sex, and other header fields in both CLI output and metadata.
- `--reassign-session` allows multiple remaps (e.g., `--reassign-session 071:01=072 --reassign-session 073:01=074`).
- Use `--exclude-subject` and `--exclude-uid` together to prune noisy scans while keeping the rest of a cohort.
- Combine filters with `--download-only` to skip metadata or `--metadata-only` to refresh manifests without touching archives.

---

## Contributing / Development

```bash
pip install -e .[dev]
ruff check .
pytest -c ../pytest.ini -vv
```

Pre-commit hooks (`pre-commit install`) keep formatting consistent. Issues and PRs are welcome—please include reproduction steps or sample command lines when reporting bugs.

---

## License

`dicomatic` is distributed under the [MIT License](../../../LICENSE).
