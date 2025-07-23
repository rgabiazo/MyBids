# MyBids

This repository bundles a BIDS dataset and utilities for working with
neuroimaging files. The Python packages in `code/MyBidsApp/` allow you to
convert and organise data, query PACS servers and submit jobs to CBRAIN.
Shell helpers under `code/scripts/` wrap FSL, Freesurfer, ICA-AROMA, and 
related tools so you can run preprocessing and FEAT-based analyses with minimal setup. 
Everything installs into a single virtual environment and a `dataset_description.json` 
template ensures new projects start with valid metadata.

## Included tools

- **`bidscomatic-cli`** – convert DICOM series into a compliant BIDS layout
- **`dicomatic-cli`** – query and download DICOM studies
- **`cbrain-cli`** – launch CBRAIN pipelines on your dataset
- **`bids`** – umbrella command re-exporting the three scripts above

For complete usage instructions, configuration examples and workflow
walk‑throughs, see the detailed
[MyBidsApp README](code/MyBidsApp/README.md).

## Code directory overview

All code lives under the `code/` folder. Key subdirectories include:

- `MyBidsApp/` – Python packages providing the command line tools.
- `ICA-AROMA-master/` – ICA‑AROMA sources and Dockerfile.
- `scripts/` – shell helpers for preprocessing and analysis.
- `design_files/` – template FEAT design files.
- `config/` – YAML configuration defaults.

See [code/README.md](code/README.md) for a full list of helper scripts and
their external requirements (FSL, FreeSurfer, Docker, `yq`, `jq`).

## Analysis scripts

The `code/scripts` directory bundles shell helpers that let you run
preprocessing and FSL FEAT analyses locally. Key scripts include:

- `fmri_preprocessing.sh` – orchestrate skull stripping, fieldmap correction
  and event file conversion.
- `feat_first_level_analysis.sh` – configure and execute first-level FEAT models.
- `run_feat_analysis.sh` – convenience wrapper combining preprocessing with FEAT.
- `second_level_analysis.sh` – run fixed-effects analyses across runs or sessions.
- `third_level_analysis.sh` – perform mixed-effects group analyses.
- `run_featquery.sh` – extract ROI statistics from FEAT results.

Helpers such as `select_group_roi.sh` and `featquery_input.sh` assist with ROI
selection and interactive featquery runs. See
[code/README.md](code/README.md) for full usage details.

## Installation

Create a virtual environment and run the helper script to install all
packages in editable mode:

```bash
python -m venv .venv && source .venv/bin/activate
./code/MyBidsApp/dev_install.sh
bids --help
```

All CLI commands accept `--version` to display the installed release.

Some workflows depend on FSL's FEAT toolkit. Ensure the `feat` command is
available in your `PATH` before running analysis scripts.

### Initialise a new dataset

The `init_bids_project.sh` helper automates common setup steps.  It renames
the dataset folder to match the provided study name, creates a virtual
environment and generates a minimal `dataset_description.json` using the
template bundled with this repository.  Once the setup finishes it spawns a
new shell with the virtual environment activated inside the renamed dataset
directory.  The prompt shows the usual
virtual‑environment prefix so you know the tools are ready:

```bash
./code/MyBidsApp/init_bids_project.sh --name "MyBidsProject" --author "Alice" \
    --license "CC-BY-4.0"
```

Pass `--author` multiple times to list several authors and `--dataset-type`
to create a derivative dataset instead of the default raw layout.  The helper
also accepts additional options to fill out the dataset metadata, including
`--license`, `--acknowledgements`, `--how-to-acknowledge`, `--funding`,
`--ethics-approval`, `--reference`, and `--dataset-doi`.  When you are done
working in the project subshell simply type `exit` (or press `Ctrl-D`) to
return to your original shell session.

Each tool can also be installed on its own with `pip install -e` from the
corresponding subdirectory.

For script usage details, including environment variables and Docker
instructions, see [code/README.md](code/README.md).

## 📚 Acknowledgements & citations

If you use **MyBidsApp** or any local scripts from this repository, **please cite the authors of those tools and acknowledge this repository**.

## 📚 Citations & acknowledgements

- **BIDS Validator** – Gorgolewski K.J., et al. *Sci Data* 2016;3:160044. doi:10.1038/sdata.2016.44  
- **Boutiques** – Glatard T., et al. *GigaScience* 2018;7:giy016. doi:10.1093/gigascience/giy016  
- **CBRAIN** – Sherif T., et al. *Front Neuroinform* 2014;8:54. doi:10.3389/fninf.2014.00054  
- **dcm2niix** – Li X., et al. *Front Neuroinform* 2016;10:30. doi:10.3389/fninf.2016.00030  
- **FreeSurfer** – Fischl B. *NeuroImage* 2012;62:774‑781. doi:10.1016/j.neuroimage.2012.01.021  
- **FSL** – Jenkinson M., et al. *NeuroImage* 2012;62:782‑790. doi:10.1016/j.neuroimage.2011.09.015  
- **hippunfold** – de Kraker L., et al. *eLife* 2023;12:e69982. doi:10.7554/eLife.69982  
- **ICA‑AROMA** – Pruim R.H.R., et al. *NeuroImage* 2015;112:267‑277. doi:10.1016/j.neuroimage.2015.02.064  
- **SynthStrip** – Hoopes A., et al. *NeuroImage* 2022;260:119474. doi:10.1016/j.neuroimage.2022.119474   

Special thanks to my supervisor Dr. Lindsay Nagamatsu and the Exercise, Mobility, and Brain Health lab at Western University for their invaluable support, insightful feedback, and access to computing resources that made this project possible.

## License

This project is distributed under the terms of the [MIT License](LICENSE).
