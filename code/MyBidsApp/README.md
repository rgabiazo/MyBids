# MyBidsApp 📦 — unified BIDS toolkit

> **One repo · One virtual‑env · Three power‑tools**

`MyBidsApp` glues together everything you typically need when working with
**Brain‑Imaging Data Structure (BIDS)** datasets:

| Sub‑package 📁              | Console script    | What it does                                                                                         | Typical use‑case                                                                  |
| --------------------------- | ----------------- | ---------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| **`bidscomatic/`**          | `bidscomatic-cli` | *DICOM ➜ BIDS* conversion, folder re‑organisation, side‑car JSON cleaning                            | You just got a pile of `.dcm` series from the scanner and want a valid BIDS tree. |
| **`dicomatic/`**            | `dicomatic-cli`   | Query, download and manifest helpers for PACS / XNAT style DICOM archives                            | You need to pull raw DICOMs (or metadata) straight from the source.               |
| **`cbrain_bids_pipeline/`** | `cbrain-cli` | Launch & monitor **CBRAIN** tools *on* your BIDS dataset (currently `hippunfold`; more tools coming) | You want to run heavy‑duty pipelines on HPC while keeping output BIDS‑compliant.  |
| **`bids_cli_hub/`**         | `bids`            | Tiny wrapper that re‑exports the three commands above as sub‑commands for muscle‑memory convenience  | You like `git …`, `conda …` style umbrellas and one autocompletion entry.         |

```console
$ bids --help            # umbrella command, shows available sub‑commands
$ bids bidscomatic --help
$ bids dicomatic --help
$ bids cbrain --help
```

---

## 🚀 Quick‑start (local *editable* install)

```bash
python -m venv .venv && source .venv/bin/activate
./code/MyBidsApp/dev_install.sh        # installs *all four* packages in‑place
bids --version                         # sanity‑check: umbrella CLI available
```

Need only one tool? `pip install -e code/bidscomatic` (or the relevant folder) works just as well, but the hub gives nice tab‑completion.

### 📋 Prerequisites

> Actively tested on **macOS 12+** (Homebrew) and **Ubuntu 22.04**.
> Windows users: run everything inside **WSL 2** – follow the Linux steps there.

| Dependency                | Why it’s needed                                  | Install hint                                                      |
| ------------------------- | ------------------------------------------------ | ----------------------------------------------------------------- |
| Python ≥ 3.9 (CPython)    | All three tools are pure‑Python; PyPy not tested | `brew install python` / `apt install python3.10`                  |
| `dcm2niix`                | Converts DICOM → NIfTI during `bidscomatic` runs | `brew install dcm2niix` / `apt install dcm2niix`                  |
| Node.js & npm             | Required by the **BIDS Validator** CLI           | `brew install node` / `apt install nodejs npm`                    |
| `bids-validator`          | Ensures datasets stay spec‑compliant             | `npm install -g bids-validator`                                   |
| CBRAIN account (optional) | Needed only for `cbrain-cli` (alias `bids-cbrain-cli`)                | [Get API & SFTP credentials](https://github.com/aces/cbrain/wiki) |

> **TIP:** The dev script checks for these binaries and prints guidance if any are missing.

---

## 🏗️  Repository layout

```
MyBidsApp/
├─ bidscomatic/              # packaging + source code
├─ dicomatic/
├─ cbrain_bids_pipeline/
├─ bids_cli_hub/
├─ dev_install.sh            # helper that installs everything in one hit
└─ dataset_description.json  # demo dataset for smoke‑tests (optional)
```

Each sub‑package ships its own detailed README with examples and advanced usage. The short summaries below should help you decide which path to explore first.

| Tool            | One‑liner                              | Highlights                                                             |
| --------------- | -------------------------------------- | ---------------------------------------------------------------------- |
| **bidscomatic** | Opinionated *DICOM ➜ BIDS* organiser   | Parallel unpacking, naming heuristics, automatic side‑car fixes        |
| **dicomatic**   | Lightweight DICOM query & download CLI | Works against PACS & XNAT, CSV manifests, retry logic                  |
| **bids‑cbrain** | Fire‑and‑forget CBRAIN launcher        | Token auto‑renewal, SFTP uploads/downloads, flatten derivative folders |

---

## 🔧 Configuration cheatsheet

The CBRAIN pipeline relies on three YAML files (all live in `cbrain_bids_pipeline/bids_cbrain_runner/config/`). 98 % of users only tweak `servers.yaml` once.

```text
File              Purpose                                        Minimal example
----------------- ---------------------------------------------- ----------------
servers.yaml      SFTP endpoints & Data‑Provider IDs             (see below)
tools.yaml        Tool‑ID ↔ bourreau mapping, versions, dirs     hippunfold only for now
defaults.yaml     Where derivatives land inside the BIDS tree    hippunfold_output_dir + filetype rules
```

### Example config snippets

```yaml
# servers.yaml
cbrain_base_url: "https://portal.cbrain.mcgill.ca"
data_providers:
  sftp_1:
    host: ace-cbrain-1.cbrain.mcgill.ca
    port: 7500
    cbrain_id: 51
  sftp_2:
    host: user@ace-cbrain-2.cbrain.mcgill.ca
    port: 7500
    cbrain_id: 32
```

```yaml
# tools.yaml
tools:
  hippunfold:
    version: "1.3.2"
    default_cluster: beluga
    clusters:
      beluga:
        tool_config_id: 5035
        bourreau_id: 56
      rorqual:
        tool_config_id: 8954
        bourreau_id: 104
    keep_dirs: [config, logs, work]
  fmriprep:
    version: "23.0.2"
    default_cluster: beluga
    clusters:
      beluga:
        tool_config_id: 4538
        bourreau_id: 56
    keep_dirs: [config, logs, work]
```

```yaml
# defaults.yaml
cbrain:
  hippunfold:
    hippunfold_output_dir: derivatives/hippunfold
  fmriprep:
    fmriprep_output_dir: derivatives/fmriprep
filetype_inference:
  fallback: BidsSubject
  patterns:
    "*.json": JsonFile
    "*.txt": TextFile
    "dataset_description.json": JsonFile
    "sub-*": BidsSubject
```

When ``--upload-bids-and-sftp-files`` registers new folders and no explicit
``--upload-filetypes`` are given, the tool matches basenames against these
patterns to pick a CBRAIN filetype.  The ``fallback`` value is used when no
pattern matches.

Environment variables **override YAML** – perfect for CI/CD secrets:

```bash
export CBRAIN_USERNAME=alice@example.com
export CBRAIN_PASSWORD=********
export CBRAIN_PERSIST=1   # re‑write new tokens back to cbrain.yaml when refreshed
```

---

## 👩‍🔬 Typical workflows

### 1️⃣ Create a BIDS dataset from raw DICOMs

```console
bids bidscomatic /path/to/dicom_zip_or_folder /dest/bids_dataset
```

### 2️⃣ Query & pull missing series from PACS

```console
bids dicomatic fetch --patient-id 12345 --series "T1*" ./scratch/dicom
```

### 3️⃣ Run *hippunfold* on CBRAIN (single subject)

```console
bids cbrain --launch-tool hippunfold --group-id 98765 \
            --extra modality=T1w --subject_dir sub-001/ses-01/anat
```

### 4️⃣ Download derivatives back into your dataset

```console
bids cbrain --download-tool hippunfold --group-id 98765 --flatten
```

---

## 📝 Acknowledgements & citations

* **HippUnfold** — de Kraker L., et al. *eLife* **11**, e77945 (2022). doi:10.7554/eLife.77945
* **BIDS Validator** — Gorgolewski K.J., et al. *Sci Data* **3**, 160044 (2016). doi:10.1038/sdata.2016.44
* **dcm2niix** — Li X., et al. *Front. Neuroinform.* **10**, 30 (2016). doi:10.3389/fninf.2016.00030
* **CBRAIN** — Sherif T., et al. *Front. Neuroinform.* **8**, 54 (2014). doi:10.3389/fninf.2014.00054 

If you use `MyBidsApp` in your research, please cite the relevant upstream tools as well as this repository.

---

## 🤝 Contributing

1. Fork → feature branch → pull request.
2. Run `pre-commit` and ensure unit‑tests (where present) pass.
3. New CLI flags must include docstrings and `--help` examples.

Bug reports & feature requests are welcome via GitHub Issues.

---

## License

[MIT](../../LICENSE) – free to use, modify and distribute with attribution.
