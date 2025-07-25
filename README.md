# MyBids

MyBids is a comprehensive toolkit and example repository for working with neuroimaging data in the **Brain Imaging Data Structure (BIDS)** format. It bundles a demonstration BIDS dataset together with command‑line utilities and pipeline scripts so you can convert raw DICOM files, organize data, and run end‑to‑end analyses — all from a single, unified environment. There are two main components:

1. **MyBidsApp** – a collection of Python packages providing command line tools
   for BIDS data (``bidscomatic-cli``, ``dicomatic-cli``, ``cbrain-cli``,
   and the ``bids`` umbrella).  These packages live in
   ``MyBidsApp/``.  See the
   [detailed MyBidsApp README](MyBidsApp/README.md) for installation
   and usage instructions for each tool.
2. **Shell scripts** – helper scripts for preprocessing and analysing neuroimaging
   data with FSL, FreeSurfer and related utilities. Scripts reside in ``scripts/``
   and work with the BIDS dataset stored at the repository root. See the
   [Shell Scripts README](code/README.md#shell-scripts) for usage details.

## Key Features

| Category | Description |
|----------|-------------|
| **DICOM → BIDS Conversion** | `bidscomatic-cli` automates naming, folder structure, and JSON side‑car creation so scanner output becomes a valid BIDS dataset in one step. |
| **DICOM Archive Querying** | `dicomatic-cli` connects to **PACS**/**XNAT** archives, letting you search and download series by patient, study, or accession number. |
| **CBRAIN Pipeline Launcher** | `cbrain-cli` submits and monitors jobs on the **CBRAIN** HPC platform (e.g. HippUnfold), handles upload/download, and writes outputs back into `derivatives/` following BIDS. |
| **Unified Command Hub** | A single `bids` umbrella command re‑exports the three tools above, providing `bids bidscomatic …`, `bids dicomatic …`, and `bids cbrain …` for shell‑completion convenience. |
| **fMRI Processing Scripts** | Bash helpers under `code/scripts/` run local preprocessing (skull‑stripping, TOPUP, ICA‑AROMA) and FSL **FEAT** first‑, second‑, and third‑level stats. |
| **Project Initialisation** | `init_bids_project.sh` spins up a clean project folder, virtual environment, and `dataset_description.json` skeleton in one command. |
| **Templates & Configs** | Ready‑made FEAT design files (`design_files/`) and YAML configs (`config/`) offer sensible defaults you can tweak. |

Uploads from the `derivatives/` tree behave like regular BIDS uploads—the leading
`derivatives/` component is stripped so files appear alongside the rest of the
dataset on the remote SFTP server.

## Technology Stack

* **Python ≥ 3.9** — CLI tools (packaged in *MyBidsApp*)
* **Bash** — helper scripts (macOS 12+, Ubuntu 22.04, or WSL 2)
* **BIDS** Validator (Node.js) — compliance checking
* **dcm2niix** — DICOM ➜ NIfTI conversion
* **FSL** (BET, TOPUP, FEAT, fslmaths, etc.)
* **FreeSurfer** (*SynthStrip* optional skull‑strip)
* **ICA‑AROMA** — motion artefact removal (Docker image supplied)
* **Docker** — optional containerised pipelines
* **CBRAIN** — external HPC processing
* **PACS / XNAT** — remote DICOM archives

### 1 — Clone the repository

```bash
git clone https://github.com/rgabiazo/MyBids.git
cd MyBids
```

### 2 — Create & activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3 — Install the tools

```bash
./code/MyBidsApp/dev_install.sh    # installs umbrella `bids` command
```

Verify:

```bash
bids --version
bids --help
```

*Need only one sub‑tool?* Install it in editable mode, e.g.:

```bash
pip install -e code/bidscomatic
```

*Note*: FSL, Node.js (for the validator), and other externals must already be on your `$PATH`.

## Usage Overview

The **`bids`** umbrella command exposes three sub‑commands, all of which accept `--help`:

| Command | Purpose |
|---------|---------|
| `bids bidscomatic <dicom_src> <bids_dst>` | Convert raw DICOMs to BIDS. |
| `bids dicomatic fetch --patient-id <ID> --series "<pattern>" <outdir>` | Query & download from PACS/XNAT. |
| `bids cbrain --launch-tool hippunfold …` | Submit CBRAIN jobs and retrieve outputs. |

### Example end‑to‑end workflow

```bash
# 1 Pull DICOM series by Study UID
bids dicomatic fetch --study-uid <UID> ./scratch/dicoms

# 2 Convert to BIDS format
bids bidscomatic ./scratch/dicoms /data/MyStudy

# 3 Launch HippUnfold on CBRAIN for subject sub-001
bids cbrain-cli \
--launch-tool hippunfold \
--tool-param modality=T1w \
--launch-tool-batch-group MyStudy \
--launch-tool-batch-type BidsSubject \
--launch-tool-bourreau-id 56 \
--launch-tool-results-dp-id 51 

# 4 Download the derivatives
bids cbrain --download-tool hippunfold --group-id MyStudy --flatten
```

### Local analysis scripts

```bash
# Preprocess fMRI
./code/scripts/fmri_preprocessing.sh

# First‑level stats
./code/scripts/feat_first_level_analysis.sh

# Second‑ & third‑level group stats
./code/scripts/second_level_analysis.sh
./code/scripts/third_level_analysis.sh
```

All scripts display a usage prompt when run without arguments.

## Contributing

Pull requests are welcome! Please file an issue first for major changes. Ensure any new dependencies are documented and that pipelines still produce BIDS‑valid output.

## License

This project is released under the MIT License. See [LICENSE](LICENSE) for details.

## Acknowledgements & Citations

If you use *MyBids* or the bundled scripts, please cite the original tool authors. Key references include:

* Gorgolewski KJ et al. *BIDS Validator*, *Sci Data* 3, 160044 (2016)  
* Glatard T et al. *Boutiques*, *GigaScience* 7(5), giy016 (2018)  
* Sherif T et al. *CBRAIN*, *Front. Neuroinform.* 8, 54 (2014)  
* Li X et al. *dcm2niix*, *Front. Neuroinform.* 10, 30 (2016)  
* Fischl B. *FreeSurfer*, *NeuroImage* 62(2), 774–781 (2012)  
* Jenkinson M et al. *FSL*, *NeuroImage* 62(2), 782–790 (2012)  
* de Kraker L et al. *HippUnfold*, *eLife* 11, e77945 (2022)  
* Pruim RHR et al. *ICA‑AROMA*, *NeuroImage* 112, 267–277 (2015)  
* Hoopes A et al. *SynthStrip*, *NeuroImage* 260, 119474 (2022)

*Special thanks* to Dr. Lindsay Nagamatsu and the Exercise, Mobility, and Brain Health Lab at Western University for their feedback and computing resources.
