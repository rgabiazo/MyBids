# **dicomatic**

*A CLI‑first toolkit to **query, download & organise DICOM studies** into a tidy, BIDS‑compatible tree – all without leaving your terminal.*

---

## Key features

| Capability                        | Why it matters                                                                                                                               |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| **PACS ↔︎ DICOM over Docker**     | `dicomatic-cli` wraps dcm4che’s **findscu** & the *cfmm2tar* container so the exact same commands run on Linux, macOS & Windows‑WSL.         |
| **Interactive or fully scripted** | Use prompts when you feel exploratory *or* supply flags/env‑vars for headless CI runs.                                                       |
| **Smart BIDS mapping**            | Subject/session folders are inferred from `PatientName` & acquisition dates; session tags like `baseline` ↔︎ `ses-01` are YAML‑configurable. |
| **Rich sub‑commands**             | Query studies, filter by patient, download raw archives, build/update `metadata.json`, even orchestrate one‑line BIDS downloads.             |
| **YAML configuration**            | Package ships sane defaults in `dicomatic/config/config.yaml` – override as little or as much as you need.                                   |
| **Idempotent & safe**             | Existing `.tar` archives aren’t re‑pulled and manifest entries merge by UID.                                                                 |
| **Pure‑Python ≥ 3.8**             | No compiled extensions & no local database; just Python + Docker.                                                                            |

---

## 🚀 Installation

> **Prerequisites**
>
> * Python ≥ 3.8
> * [Docker](https://docs.docker.com/get-docker/)
> * Access to a DICOM server (AET, port, TLS mode, credentials)
> * [`cfmm2tar`](https://github.com/uwo‑cfmm/cfmm2tar) image pulled locally (`docker pull uwoce/cfmm2tar:X.Y`)

### a) As part of **MyBidsApp**

```bash
# from the repository root
pip install -e code/MyBidsApp/dicomatic
```

### b) Stand‑alone development clone

```bash
git clone https://github.com/<org>/dicomatic.git  # replace with your fork
cd dicomatic
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"            # core + test/typing/lint extras
```

> **Heads‑up:** On Apple Silicon you may need `--platform linux/amd64` when pulling `cfmm2tar`.

---

## ⚡ 2‑minute quick‑start

```bash
# 0 Set credentials once per shell (or use --username/--password flags)
export DICOM_USERNAME=myuser
export DICOM_PASSWORD=secret

# 1 List studies whose StudyDescription contains "MyStudy"
dicomatic-cli query -d "MyStudy"

# 2 Download a specific StudyInstanceUID → ~/Downloads
UID=1.2.840.113619.2.55.3.604688222.1122.1598364181.467

dicomatic-cli download --uid "$UID" -o ~/Downloads --dry-run   # preview paths

dicomatic-cli download --uid "$UID" -o ~/Downloads --create-metadata  # real run

# 3 One‑liner BIDS workflow (query → filter → download → manifest)
dicomatic-cli bids -d "MyStudy" \
    --exclude-patient Phantom \
    --numeric-sessions \
    --download --create-metadata
```

Use `--filter-session` to keep only specific sessions. Numbers with more than
two digits are interpreted as subject labels, so `--filter-session 064 01` pairs
"064" with the following session token and behaves the same as
`--filter-session 064:01`.

Result: archives land in `sourcedata/dicom/sub-XXX/ses-YY/` and a `metadata.json` is (re)generated.

### Example interactive session

```text
[==== DICOMATIC - DICOM Query & Download ====]

1) List & download studies (cfmm2tar)
2) BIDS workflow: group / filter / download
3) Search by PatientName & custom download

Choose an option (1, 2, 3)
> 2

=== Subject: sub-101 ===

-- Session: ses-01 --
+----------+--------------------------+------+-----+--------------------------------------------+
| Date     | Patient                  | Age  | Sex | UID                                        |
+----------+--------------------------+------+-----+--------------------------------------------+
| 20240105 | 2024_01_05_101_visit1    | 050Y | F   | 1.2.840.999999.1.1.1011                    |
+----------+--------------------------+------+-----+--------------------------------------------+

=== Subject: sub-102 ===

-- Session: ses-01 --
+----------+--------------------------+------+-----+--------------------------------------------+
| Date     | Patient                  | Age  | Sex | UID                                        |
+----------+--------------------------+------+-----+--------------------------------------------+
| 20240210 | 2024_02_10_102_visit1    | 052Y | M   | 1.2.840.999999.1.1.1022                    |
+----------+--------------------------+------+-----+--------------------------------------------+

=== Subject: sub-103 ===

-- Session: ses-01 --
+----------+--------------------------+------+-----+--------------------------------------------+
| Date     | Patient                  | Age  | Sex | UID                                        |
+----------+--------------------------+------+-----+--------------------------------------------+
| 20240315 | 2024_03_15_103_visit1    | 048Y | F   | 1.2.840.999999.1.1.1033                    |
+----------+--------------------------+------+-----+--------------------------------------------+

-- Session: ses-02 --
+----------+--------------------------+------+-----+--------------------------------------------+
| Date     | Patient                  | Age  | Sex | UID                                        |
+----------+--------------------------+------+-----+--------------------------------------------+
| 20240630 | 2024_06_30_103_visit2    | 048Y | F   | 1.2.840.999999.1.1.1034                    |
+----------+--------------------------+------+-----+--------------------------------------------+

Would you like to download any studies (y, n)
> y

Would you like to download all subjects (y, n)
> y

Would you like to download all sessions (y, n)
> n

Please enter sessions to download (space-separated)
> 01

Would you like to update/create metadata (y, n)
> y

=== Downloading 3 studies ===
╭──────────────────────────────┬──────────────────────────────┬──────────────────────────────╮
│                      Subject │                      Session │                          UID │
├──────────────────────────────┼──────────────────────────────┼──────────────────────────────┤
│                      sub-101 │                       ses-01 │ 1.2.840.999999.1.1.1011       │
│                      sub-102 │                       ses-01 │ 1.2.840.999999.1.1.1022       │
│                      sub-103 │                       ses-01 │ 1.2.840.999999.1.1.1033       │
╰──────────────────────────────┴──────────────────────────────┴──────────────────────────────╯

-- [1/3] sub-101 | ses-01
> Running: docker run --rm -v /tmp/tmp_creds:/tmp/creds:ro -v /path/to/sourcedata/dicom/sub-101/ses-01:/data -w /data cfmm2tar -c /tmp/creds -u 1.2.840.999999.1.1.1011 /data
> output directory → /path/to/sourcedata/dicom/sub-101/ses-01
[ Download Complete ] → /path/to/sourcedata/dicom/sub-101/ses-01
```

---

## 🛠️ Configuration (`config.yaml`)

```yaml
# ~/.config/dicomatic.yaml  (or pass with --config)

dicom:
  container: "cfmm2tar"      # Docker image tag
  server: "AET@dicom.host"   # Remote PACS hostname
  port: "11112"
  tls: "aes"                # aes | ssl | none
  username: "YOUR_USERNAME"  # can be overridden by $DICOM_USERNAME
  password: "YOUR_PASSWORD"  #     "         "  $DICOM_PASSWORD

# Which DICOM attributes to request via findscu
# and how to map them to dict keys used internally
# (see shipped default for full schema)
dicom_query_tags: [ PatientName, StudyDate, StudyInstanceUID ]
dicom_tag_map:
  PatientName:     { group_elem: "(0010,0010)", vr: PN, field: patient_name }
  StudyInstanceUID:{ group_elem: "(0020,000D)", vr: UI, field: study_uid }

# Optional hard‑coded PatientName → ses‑## mapping
session_map:
  baseline: "01"
  endpoint: "02"

bids:
  root: "/path/to/bids_dataset"  # Leave empty to auto‑detect via dataset_description.json
```

*Place the file anywhere and point to it with `--config /path/to/your.yaml` or drop it into* `$(git rev-parse --show-toplevel)/code/MyBidsApp/dicomatic/config/config.yaml` *to override package defaults.*

---

## Command reference (cheat‑sheet)

| Sub‑command | Synopsis                                                                                         |
| ----------- | ------------------------------------------------------------------------------------------------ |
| `query`     | List studies that match *StudyDescription* and optionally launch an interactive download prompt. |
| `patients`  | List unique `PatientName` values, then guide you through a download of one of them.              |
| `download`  | Direct cfmm2tar pull by UID and/or StudyDescription.                                             |
| `bids`      | End‑to‑end: group studies → filter subjects/sessions → download archives into BIDS tree.         |
| `metadata`  | Create or merge a `metadata.json` manifest **without** touching existing archives.               |

Run `dicomatic-cli <sub‑command> --help` for exhaustive options & examples.

---

## Repository layout (abridged)

```
dicomatic/
├── cli.py            # Root Click entry‑point
├── commands/         # query, bids, download, … wrappers
├── query/            # findscu builder / runner / parser
├── utils/            # planning, display, auth, naming, …
├── config/           # default YAML + loader
└── models.py         # DownloadPlan dataclass
```

---

## Contributing

* Fork → create feature branch → run `ruff`, `black`,
  `pytest -c code/MyBidsApp/pytest.ini -q` & `mypy` → PR.
* CI mirrors the steps above; please keep coverage ✅.
* Ideas & bug reports welcome under *Issues*.

---

## License

`dicomatic` is released under the **MIT License** – see [LICENSE](../../../LICENSE).

---

## Acknowledgements & citation

If `dicomatic` aids your research, please cite the corresponding paper (in prep) or acknowledge the toolkit:

> *DICOM archives were retrieved and curated using dicomatic (v0.1.0).*
