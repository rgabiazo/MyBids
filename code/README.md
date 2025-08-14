# Overview

This folder contains all executables and configuration files that accompany the demonstration
BIDS dataset.  There are two main components:

1. **MyBidsApp** – a collection of Python packages providing command line tools
   for BIDS data (``bidscomatic-cli``, ``dicomatic-cli``, ``cbrain-cli``,
   and the ``bids`` umbrella).  These packages live in
   ``MyBidsApp/``.  See the
   [detailed MyBidsApp README](MyBidsApp/README.md) for installation
   and usage instructions for each tool.
2. **Shell scripts** – helper scripts for preprocessing and analysing neuroimaging
   data with FSL and related utilities.  Scripts reside in ``scripts/``
   and work with the BIDS dataset stored at the repository root.

# Shell Scripts

The ``scripts/`` directory offers a set of Bash helpers to streamline common
fMRI workflows.  Each script prints usage information when run without
arguments.  They are intended to be composable so you can run individual
steps or entire pipelines.

# Included Scripts

1. ``build_images.sh`` – build the Docker image used to run ICA‑AROMA.
2. ``fmri_preprocessing.sh`` – orchestrate preprocessing steps such as skull stripping, fieldmap correction and event file conversion.
3. ``run_bet_extraction.sh`` – apply FSL BET to T1w images.
4. ``run_synthstrip_extraction.sh`` – skull strip T1w images using FreeSurfer’s SynthStrip.
5. ``run_fieldmap_correction.sh`` – apply TOPUP‑based distortion correction.
6. ``extract_slice_timing.sh`` – extract slice timing arrays from BOLD JSON sidecars.
7. ``create_event_files.sh`` – convert BIDS ``events.tsv`` files to the simple three‑column text format expected by FSL FEAT.
8. ``feat_first_level_analysis.sh`` – set up and run FSL FEAT first‑level analyses with optional ICA‑AROMA, nuisance regression and slice timing correction.
9. ``run_feat_analysis.sh`` – convenience wrapper combining preprocessing, ICA‑AROMA and FEAT.
10. ``second_level_analysis.sh`` – run fixed‑effects analyses across runs or sessions.
11. ``generate_fixed_effects_design_fsf.sh`` – create a second‑level FEAT design file programmatically.
12. ``third_level_analysis.sh`` – perform mixed‑effects group analyses in FSL.
13. ``select_group_roi.sh`` – helper for group‑level ROI selection that calls ``generate_cluster_tables.sh`` and ``create_spherical_rois.sh``.
14. ``generate_cluster_tables.sh`` – parse group‑level FEAT results, perform atlas lookups and guide ROI selection.
16. ``create_spherical_rois.sh`` – generate spherical ROI masks from coordinates using FSL ``fslmaths``.
18. ``featquery_input.sh`` – interactively choose FEAT directories and ROI masks, then delegate to ``run_featquery.sh``.
19. ``run_featquery.sh`` – run FSL ``featquery`` on FEAT output and collect CSV tables.

# Requirements

Running the shell scripts requires a Unix environment with the following
software installed:

| Dependency | Purpose |
|------------|---------|
| **FSL** | Provides ``feat``, ``fslmaths`` and ``topup`` |
| **FreeSurfer** | Supplies SynthStrip for ``run_synthstrip_extraction.sh`` |
| **Docker** | Build and optionally run the ICA‑AROMA container |
| **Python 2.7** or ``ICA_AROMA_CONTAINER`` | Execute the legacy ICA‑AROMA scripts |
| ``yq`` and ``jq`` | Parse configuration and JSON metadata |

Some helpers rely on the configuration files under ``config/`` for default
paths and dataset metadata. Logs are written to ``code/logs`` inside the
project directory.

# Environment Variables

The `run_feat_analysis.sh` helper understands the following variables:

| Variable | Purpose |
|----------|---------|
| `ICA_AROMA_CONTAINER` | Docker image used to run ICA‑AROMA when no system `python2.7` is available |
| `ICA_AROMA_SKIP_PLOTS` | Pass `--noplots` to ICA‑AROMA to save memory and skip component plots |
| `ICA_AROMA_SHOW_PLOT_WARNINGS` | Display seaborn/matplotlib warnings during plot generation |

# Running ICA-AROMA via Docker

The `code/ICA-AROMA-master` folder includes a Dockerfile that builds from
`vnmd/fsl_6.0.7.14`. The container installs Python 2.7 along with the
packages listed in `requirements.txt` so ICA‑AROMA can run out of the box.
Build the image with Docker:

```bash
docker build -t ica_aroma:dev code/ICA-AROMA-master
```

The container automatically detects the FSL installation at runtime and
adds `$FSLDIR/bin` to the `PATH`.  You can override the detection with
`-e FSLDIR=/path/to/fsl` when running the container.

The helper scripts look for an image tagged `ica_aroma` (implicitly
`latest`). Tag the container accordingly:

```bash
docker tag ica_aroma:dev ica_aroma
```

Alternatively set `ICA_AROMA_CONTAINER=ica_aroma:dev` before running
`run_feat_analysis.sh`.

You can also run `code/scripts/build_images.sh` to produce and push a
tagged release.

When an image tagged `ica_aroma` is present and `ICA_AROMA_CONTAINER` is unset,
`run_feat_analysis.sh` uses this Docker image automatically. If no container is
found the script falls back to a system `python2.7` install.


# Example Workflow

The following helpers illustrate a typical preprocessing and analysis
sequence. Run each script directly from the command line and follow the
interactive prompts.

```bash
./code/scripts/fmri_preprocessing.sh
./code/scripts/feat_first_level_analysis.sh
./code/scripts/second_level_analysis.sh
./code/scripts/third_level_analysis.sh
```

### `fmri_preprocessing.sh`

Orchestrates skull stripping, field map correction, event file conversion and
slice timing extraction. Run the helper directly from the command line:

```bash
./code/scripts/fmri_preprocessing.sh
```

#### Example output

Running the preprocessing helper prints a sequence of interactive prompts:

```text
$ ./code/scripts/fmri_preprocessing.sh
=== fMRI Preprocessing Pipeline ===

Please enter the base directory for the project or hit Enter/Return to use the default [/path/to/project]:
>
Using base directory: /path/to/project

Is the preprocessing for task-based fMRI or resting-state fMRI?
1. Task-based
2. Resting-state
Enter the number corresponding to your choice: 1

Apply skull stripping? (y/n): y
Please select a skull stripping tool:
1. BET (FSL)
2. SynthStrip (FreeSurfer)
Enter your choice: 2

Apply fslreorient2std to all T1w images? (y/n): y
Apply fieldmap correction using topup? (y/n): y
Create .txt event files from .tsv? (y/n): y
Enter number of runs: 3
Enter trial types (e.g., encoding_pair recog_pair):
encoding_pair recog_pair encoding_place recog_place encoding_face recog_face
Extract slice timing from BOLD JSON? (y/n): n

Enter subject IDs (e.g., sub-01 sub-02) or press Enter/Return for all:
>
Enter session IDs (e.g., ses-01 ses-02) or press Enter/Return for all:
> ses-01

=== Running SynthStrip skull stripping ===
Found 28 subject directories.
=== Processing Subject: sub-002 ===
--- Session: ses-01 ---
...
```

### `feat_first_level_analysis.sh`

Run preprocessing and first-level FEAT analyses with optional ICA‑AROMA,
nuisance regression and slice timing correction. Statistics require event text
files in `derivatives/custom_events` with names matching the EV labels in the
design file. The repository ships with a generic preprocessing design file
`desc-ICAAROMApreproc_design.fsf`; provide a task-specific stats design such as
`task-myexperiment_desc-ICAAROMAstats_design.fsf` when running your study.

```bash
./code/scripts/feat_first_level_analysis.sh
```

#### Example output

```text
$ ./code/scripts/feat_first_level_analysis.sh
=== First-Level Analysis: Preprocessing & Statistics ===

Please enter the base directory or press Enter/Return to use the default [/path/to/project]:
>
Using base directory: /path/to/project

Log file: /path/to/project/code/logs/feat_first_level_analysis_YYYY-MM-DD_HH-MM-SS.log
Do you want to apply ICA-AROMA? (y/n): y
Do you want to apply non-linear registration? (y/n): y
Do you want to apply slice timing correction? (y/n): n
Skipping slice timing correction.
Do you want to use Boundary-Based Registration (BBR)? (y/n): y
BBR will be used.
Do you want to apply nuisance regression after ICA-AROMA? (y/n): y
Nuisance regression after ICA-AROMA will be applied.
Do you want to apply statistics (main FEAT analysis) after ICA-AROMA? (y/n): y
Statistics will be run after ICA-AROMA.

Please enter the path for the ICA-AROMA main analysis design.fsf or press Enter/Return for [/path/to/project/code/design_files]:
>
Multiple design files found:
1) task-assocmemory_desc-ICAAROMAstats_design.fsf
2) task-faceplace_desc-ICAAROMAstats_design.fsf
Select the design file (enter a number): 2
Using ICA-AROMA main analysis design file: /path/to/project/code/design_files/task-faceplace_desc-ICAAROMAstats_design.fsf

Please enter the path for the ICA-AROMA preprocessing design.fsf or press Enter/Return for [/path/to/project/code/design_files]:
>
Using ICA-AROMA preprocessing design file: /path/to/project/code/design_files/desc-ICAAROMApreproc_design.fsf
Select the skull-stripped T1 images directory or press Enter/Return for [BET]:
1. BET skull-stripped T1 images
2. SynthStrip skull-stripped T1 images
> 2
Using SynthStrip skull-stripped T1 images.
Do you want to use field map corrected runs? (y/n): y
Using field map corrected runs.
Do you want to apply high-pass filtering during the main FEAT analysis? (y/n): y
Enter the high-pass filter cutoff value in seconds, or press Enter/Return to use the default cutoff of 100:
>
High-pass filtering will be applied with a cutoff of 100 seconds.
Enter the number of EVs: 6
Enter the condition names for the EVs in order.
Condition name for EV1: encoding_face
Condition name for EV2: encoding_place
Condition name for EV3: encoding_pair
Condition name for EV4: recog_face
Condition name for EV5: recog_place
Condition name for EV6: recog_pair

Enter template path or press Enter/Return for [/path/to/project/derivatives/templates/MNI152_T1_2mm_brain.nii.gz]:
>

Enter subject IDs (e.g., sub-01 sub-02), or press Enter/Return for all in /path/to/project:
> sub-002

Enter session IDs (e.g., ses-01 ses-02), or press Enter/Return for all sessions:
> ses-01

--- FEAT Preprocessing + Main Analysis (ICA-AROMA) ---
./code/scripts/run_feat_analysis.sh --preproc-design-file <preproc_design.fsf> \
    --analysis-output-dir <analysis_dir> --design-file <stats_design.fsf> \
    --ica-aroma --nonlinear-reg --subject sub-002 --session ses-01 --run run-01 \
    --ev1 <ev1.txt> --ev2 <ev2.txt> ...

[INFO] Running: docker run --rm --entrypoint "" -v /path/to/project:/path/to/project \
        -w $(pwd) ica_aroma python /ICA-AROMA/ica-aroma-via-docker.py \
        -in <filtered_func_data.nii.gz> -out <ICA_AROMA_dir> -mc <mc.par> \
        -m <brain_mask.nii.gz> -affmat <example_func2highres.mat> \
        -warp <highres2standard_warp.nii.gz>
Running: python /ICA-AROMA/ICA_AROMA.py -in <filtered_func_data.nii.gz> \
        -out <ICA_AROMA_dir> -mc <mc.par> -m <brain_mask.nii.gz> \
        -affmat <example_func2highres.mat> -warp <highres2standard_warp.nii.gz>
[Output from ICA-AROMA]
------------------------------- RUNNING ICA-AROMA ---------------------------
--------------- 'ICA-based Automatic Removal Of Motion Artifacts' ---------------

Step 1) MELODIC
Step 2) Automatic classification of the components
  - registering the spatial maps to MNI
  - extracting the CSF & Edge fraction features
  - extracting the Maximum RP correlation feature
  - extracting the High-frequency content feature
  - classification
Step 3) Data denoising

----------------------------------- Finished -----------------------------------
[INFO] ICA-AROMA processed successfully.

# Without Docker the script falls back to the system Python 2.7 interpreter
[INFO] Running: /usr/bin/python2.7 /path/to/project/code/ICA-AROMA-master/ICA_AROMA.py \
        -in <filtered_func_data.nii.gz> -out <ICA_AROMA_dir> -mc <mc.par> \
        -m <brain_mask.nii.gz> -affmat <example_func2highres.mat> \
        -warp <highres2standard_warp.nii.gz>
[INFO] ICA-AROMA processed successfully.
```

### `second_level_analysis.sh`

Run fixed-effects analyses across runs or sessions after completing the
first-level processing. The helper combines the specified runs for each subject
into a single FEAT directory.

```bash
./code/scripts/second_level_analysis.sh
```

#### Example output

```text
$ ./code/scripts/second_level_analysis.sh
=== Second-Level FEAT Analysis ===

Please enter the base directory or press Enter/Return to use the default [/path/to/project]:
>
Using base directory: /path/to/project

Available first-level analyses:
1) analysis
2) analysis_postICA
Select the analysis directory (enter a number): 1
You have selected the analysis directory: /path/to/project/derivatives/fsl/level-1/analysis

Enter subject IDs (e.g., sub-01 sub-02):
> sub-002
Enter session IDs (e.g., ses-01 ses-02) or press Enter/Return for all:
>
Log file: /path/to/project/code/logs/second_level_analysis_YYYY-MM-DD_HH-MM-SS.log
...
```

### `third_level_analysis.sh`

Run mixed-effects group analyses using higher-level FEAT outputs.

```bash
./code/scripts/third_level_analysis.sh
```

#### Example output

```text
$ ./code/scripts/third_level_analysis.sh
=== Third-Level Analysis ===

---- Higher level FEAT directories ----
Select analysis directory containing 3D cope images

1) derivatives/fsl/level-2/analysis_postICA

Please enter your choice: 1

You have selected the following analysis directory:
/path/to/project/derivatives/fsl/level-2/analysis_postICA

--- Select session ---
Higher level FEAT directories

Select available sessions:

1) ses-01

Please enter your choice: 1

=== Confirm Your Selections for Mixed Effects Analysis ===
Session: ses-01

Subject: sub-001 | Session: ses-01
----------------------------------------
Higher-level Feat Directory:
  - derivatives/fsl/level-2/analysis_postICA/sub-001/ses-01/sub-001_ses-01_task-<name>_desc-fixed-effects.gfeat

Subject: sub-002 | Session: ses-01
----------------------------------------
Higher-level Feat Directory:
  - derivatives/fsl/level-2/analysis_postICA/sub-002/ses-01/sub-002_ses-01_task-<name>_desc-fixed-effects.gfeat

============================================

Options:
  • To exclude subjects, type '-' followed by subject IDs separated by spaces (e.g., '- sub-01 sub-02').
  • To edit directories for a specific subject, type 'edit'.
  • Press Enter/Return to proceed with third-level mixed-effects analysis if everything looks correct.
```

### `select_group_roi.sh`

Helper script to choose group-level regions of interest based on FEAT results.
It invokes `generate_cluster_tables.sh` to produce cluster summaries and
`create_spherical_rois.sh` to build spherical masks from the selected clusters.

```bash
./code/scripts/select_group_roi.sh
```

#### Example output

```text
$ ./code/scripts/select_group_roi.sh

=== Spherical ROI Group Analysis Directory Selection ===
Available Group Analysis Directories:

1) task-example_desc-group-FLAME1

Please select the group analysis directory for spherical ROI creation by entering the number:
> 1

=== .gfeat Selection ===
Directory: task-example_desc-group-FLAME1

Available .gfeat directories:

 1)  cope1.gfeat
 2)  cope2.gfeat
 ...
Please select a .gfeat directory by entering the number:
> 2

---------------------------------------------------------------
 ROI ID | ( x,   y,   z )         | Voxel Location | Cortical ROI (Highest Probability %)
---------------------------------------------------------------
 1.     | (  6.00, -52.00, 10.00) | (48, 24, 32)   | Precuneus Cortex (37%)
 2.     | (-46.00,   6.00, 30.00) | (29, 74, 39)   | Inferior Frontal Gyrus, pars opercularis (31%)
---------------------------------------------------------------

Enter ROI ID(s) to use for spherical ROI (e.g. 1 2 3), or press ENTER for all:
> 1 2

Enter Radius, or press ENTER to use default 5mm:
> 5

Generating Spherical ROI: <region name>
...
Would you like to select another group & cope for spherical ROI creation? (y/n)
>
```

### `featquery_input.sh`

Interactive helper that walks through selecting lower‑ or higher‑level FEAT
directories along with ROI masks before delegating to `run_featquery.sh`. The
script lists available analyses and sessions, lets you confirm or edit the
subject selection, choose ROI directories and masks, then calls
`run_featquery.sh` with the final choices.

```bash
./code/scripts/featquery_input.sh
```

#### Example output

```text
$ ./code/scripts/featquery_input.sh

=== FEATQUERY INPUT SELECTION ===
Please select analysis level for input directories:

1) Inputs are lower-level FEAT directories
2) Inputs are higher-level .gfeat directories
3) Cancel
Please enter your choice [1/2/3]: 1

Available analysis directories in level-1:

1) derivatives/fsl/level-1/analysis
2) derivatives/fsl/level-1/analysis_postICA
Please select an analysis directory by number: 1

Available sessions:

1) ses-01
Please select a session by number: 1

=== Confirm Your Selections for FEATQUERY ===
Subject: sub-001 | Session: ses-01
Selected Feat Directory:
  derivatives/fsl/level-1/analysis/sub-001/ses-01/<...>.feat
Subject: sub-002 | Session: ses-01
Selected Feat Directory:
  derivatives/fsl/level-1/analysis/sub-002/ses-01/<...>.feat
============================================

Options:
  • To exclude subjects, type '-' followed by subject IDs.
  • To edit directories for a specific subject, type 'edit'.
  • Press Enter/Return to continue when everything looks correct.
>

=== FINAL DIRECTORIES SELECTED ===
Total final directories: 2
  /path/to/project/derivatives/fsl/level-1/analysis/sub-001/ses-01/<...>.feat
  /path/to/project/derivatives/fsl/level-1/analysis/sub-002/ses-01/<...>.feat

Select from the available ROI directories below.
-------------------------------------------------
1) /path/to/project/derivatives/fsl/level-3/task-example_desc-group/roi/cope1
> 1

Select from the available ROI masks below.
-------------------------------------------------
1) ROI-mask_binarized.nii.gz
> 1

=== FINAL ROI MASKS SELECTED ===
  /path/to/project/derivatives/fsl/level-3/task-example_desc-group/roi/cope1/ROI-mask_binarized.nii.gz

```

## Non-interactive command line scripts

The following helpers can be invoked directly on the command line without any
interactive prompts.

### `run_synthstrip_extraction.sh`

Skull strip T1w images using FreeSurfer SynthStrip.

```bash
./code/scripts/run_synthstrip_extraction.sh --base-dir /path/to/BIDS sub-01 sub-02
```

```bash
./code/scripts/run_synthstrip_extraction.sh --base-dir /path/to/BIDS --reorient
```

```bash
./code/scripts/run_synthstrip_extraction.sh --base-dir /path/to/BIDS --session ses-01
```

### `run_fieldmap_correction.sh`

Apply TOPUP-based distortion correction to BOLD data.

```bash
./code/scripts/run_fieldmap_correction.sh --base-dir /path/to/BIDS --preproc-type task
```

```bash
./code/scripts/run_fieldmap_correction.sh --base-dir /path/to/BIDS --preproc-type rest --session ses-01 sub-01 sub-02
```

### `run_feat_analysis.sh`

Run first-level FEAT analyses with optional ICA‑AROMA and nuisance regression.

```bash
./code/scripts/run_feat_analysis.sh --design-file design.fsf \
    --t1-image sub-001_desc-brain_T1w.nii.gz \
    --func-image sub-001_task-example_bold.nii.gz \
    --output-dir derivatives/fsl/level-1/analysis/sub-001/task-example_run-1.feat \
    --ev1 ev1.txt
```

### `generate_fixed_effects_design_fsf.sh`

Create a second-level fixed-effects design file.

```bash
./code/scripts/generate_fixed_effects_design_fsf.sh \
    derivatives/fsl/level-2/sub-01 4 2.3 0.05 \
    run1.feat run2.feat run3.feat run4.feat
```

### `third_level_analysis.sh`

Perform mixed-effects group analyses in FSL.

```bash
./code/scripts/third_level_analysis.sh \
    --analysis-dir derivatives/fsl/level-2/analysis_postICA \
    --session ses-01 --subjects "sub-001 sub-002" \
    --mixed-effects FLAME1 --z-thresh 2.3 --cluster-p-thresh 0.05
```

### `run_featquery.sh`

Wrapper around FSL `featquery` that extracts mean ROI values from one or more
FEAT directories. Pass all FEAT directories first, followed by `::`, then the
ROI mask paths. Output TSV files are written under
`derivatives/fsl/featquery/data/<GROUP_NAME>/`.

```bash
./code/scripts/run_featquery.sh derivatives/... :: mask.nii.gz
```

#### Example output

```text
$ ./code/scripts/run_featquery.sh \
    derivatives/fsl/level-2/analysis/sub-01/cope1.feat \
    derivatives/fsl/level-2/analysis/sub-02/cope1.feat \
    :: \
    derivatives/fsl/level-3/task-example_desc-group/roi/cope1/ROI-mask_binarized.nii.gz

=== Featquery input directories and ROI mask(s) ===
FEAT directories (2):
  /path/to/project/derivatives/fsl/level-2/analysis/sub-01/cope1.feat
  /path/to/project/derivatives/fsl/level-2/analysis/sub-02/cope1.feat

ROI masks (1):
  /path/to/project/derivatives/fsl/level-3/task-example_desc-group/roi/cope1/ROI-mask_binarized.nii.gz
----------------------------------------------------
>>> featquery 2 /path/to/project/.../sub-01/... /path/to/project/.../sub-02/... 1 stats/pe1 cope1_ROI-mask_featquery -p -s -b /path/to/project/derivatives/.../ROI-mask_binarized.nii.gz
TSV created at: /path/to/project/derivatives/fsl/featquery/data/group/cope-1_roi-mask.tsv

Featquery Complete.
========================================
=== Finished run_featquery.sh ===
```

### `create_dataset_description.sh`

Create or update a `dataset_description.json` in a derivative directory.

```bash
./code/scripts/create_dataset_description.sh --analysis-dir derivatives/fsl/level-1 \
    --ds-name "My Derivative" --dataset-type derivative
```

## Citations & acknowledgements

* **SynthStrip** — Hoopes A., et al. *NeuroImage* **260**, 119474 (2022). doi:10.1016/j.neuroimage.2022.119474
* **ICA-AROMA** — Pruim R.H.R., et al. *NeuroImage* **112**, 267–277 (2015). doi:10.1016/j.neuroimage.2015.02.064
* **FreeSurfer** — Fischl B. *NeuroImage* **62**(2), 774–781 (2012). doi:10.1016/j.neuroimage.2012.01.021
* **FSL** — Jenkinson M., et al. *NeuroImage* **62**(2), 782–790 (2012). doi:10.1016/j.neuroimage.2011.09.015

# License

This project is licensed under the [MIT License](../LICENSE).
