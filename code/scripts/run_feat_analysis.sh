#!/bin/bash
###############################################################################
# run_feat_analysis.sh
#
# Purpose:
#   Wrapper to run FEAT first-level analysis with optional ICA-AROMA,
#   nuisance regression and slice timing correction.
#
# Usage:
#   run_feat_analysis.sh [options]
#
# Usage Examples:
#   run_feat_analysis.sh --design-file design.fsf --t1-image sub-001_T1w.nii.gz
#
# Options:
#   --preproc-design-file FILE  .fsf for ICA-AROMA preprocessing
#   --design-file FILE         .fsf for main stats
#   --t1-image FILE            Skull stripped T1 image
#   --func-image FILE          Functional data
#   --template FILE            MNI template
#   --output-dir DIR           FEAT output directory
#   --preproc-output-dir DIR   ICA-AROMA output directory
#   --analysis-output-dir DIR  Post-ICA analysis directory
#   --ev1 FILE ...             Event files
#   --ica-aroma                Enable ICA-AROMA
#   --nonlinear-reg            Use non-linear registration
#   --subject ID               Subject label
#   --session ID               Session label
#   --task NAME                Task name
#   --run LABEL                Run label
#   --slice-timing-file FILE   Slice timing file
#   --highpass-cutoff VALUE    High-pass filter cutoff
#   --use-bbr                  Use BBR registration
#   --apply-nuisance-reg       Apply nuisance regression
#   --help, -h                 Show help
#
# Requirements:
#   FSL and yq; ICA-AROMA requires Python 2.7 or container.
#
# Notes:
#   Updates dataset_description.json via create_dataset_description.sh.
#   Config usage:
#       - This script reads a config.yaml (by default at code/config/config.yaml) for:
#         * BIDS version
#         * dataset_descriptions fields (Name, DatasetType, Description)
#         * 'generatedby' arrays specifying FSL, ICA-AROMA version, etc.
#       - By doing so, it automatically populates the dataset_description.json
###############################################################################

usage() {
  cat <<EOF
Usage: run_feat_analysis.sh [options]

Runs FEAT first-level analysis in FSL, optionally with ICA-AROMA.

Options:
  --preproc-design-file <file> : Path to the .fsf design for ICA-AROMA preprocessing
  --design-file <file>         : Path to the main .fsf design (for stats)
  --t1-image <file>            : Path to the skull-stripped T1
  --func-image <file>          : Path to the functional data (BOLD)
  --template <file>            : Path to the MNI template
  --output-dir <path>          : Where to put the output for standard FEAT
  --preproc-output-dir <path>  : Where to put the output for ICA-AROMA preprocessing
  --analysis-output-dir <path> : Where to put the post-ICA analysis results
  --ev1 <file>, --ev2 <file>   : Event files (text) for each EV
  --ica-aroma                  : Boolean flag to enable ICA-AROMA
  --nonlinear-reg              : Use non-linear registration
  --subject <string>           : Subject ID (e.g. sub-001)
  --session <string>           : Session ID (e.g. ses-01)
  --task <string>              : Task name (e.g. memtask)
  --run <string>               : Run label (e.g. run-01)
  --slice-timing-file <file>   : Slice timing file (if slice timing correction is used)
  --highpass-cutoff <value>    : High-pass filter cutoff in seconds
  --use-bbr                    : Use BBR registration
  --apply-nuisance-reg         : Apply nuisance regression after ICA-AROMA
  --design-only                : Only generate design files, skip running FEAT
  --keep-full-paths            : When used with --design-only, keep full paths in design files
  --help, -h                   : Display this help text

Environment variables:
  ICA_AROMA_CONTAINER          : Docker image for ICA-AROMA
                                  (expects Python 2.7 inside and overrides the
                                  system interpreter)
  ICA_AROMA_SKIP_PLOTS         : If set, pass --noplots to ICA-AROMA

EOF
  exit 1
}

# Determine base directory for logs and supporting files
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
BASE_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Initialize logging immediately so usage/help output is captured
LOG_DIR="${BASE_DIR}/code/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/run_feat_analysis_$(date +%Y-%m-%d_%H-%M-%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1
echo "Log file: $LOG_FILE"

ICA_AROMA_SCRIPT="$BASE_DIR/code/ICA-AROMA-master/ICA_AROMA.py"

if [ $# -eq 0 ]; then
  usage
fi

# Acquire FSL
FSL_VERSION="Unknown"
if [ -n "$FSLDIR" ] && [ -f "$FSLDIR/etc/fslversion" ]; then
  FSL_VERSION=$(cat "$FSLDIR/etc/fslversion" | cut -d'%' -f1)
fi

# Load config.yaml
CONFIG_FILE="${BASE_DIR}/code/config/config.yaml"

# Parse the top-level BIDS version from config
BIDS_VERSION="$(yq e '.bids_version' "$CONFIG_FILE")"

# Extract the "ICA-AROMA" version from the aroma block in config
ICA_AROMA_VERSION="$(
  yq e '.dataset_descriptions.level-1.aroma.generatedby[] 
        | select(.name == "ICA-AROMA") 
        | .version' "$CONFIG_FILE"
)"

# Check if yq is installed
if ! command -v yq &> /dev/null; then
  echo -e "\nERROR: 'yq' (YAML processor) not found in your PATH. Please install yq.\n"
  exit 1
fi

###############################################################################
# PARSE dataset_description FIELDS FOR PREPROC, AROMA, ANALYSIS_POSTICA,
# AND FEAT_ANALYSIS
###############################################################################
# 1) For 'preprocessing_preICA'
PREPROC_DS_NAME="$(yq e '.dataset_descriptions.level-1.preprocessing_preICA.name' "$CONFIG_FILE")"
PREPROC_DS_TYPE="$(yq e '.dataset_descriptions.level-1.preprocessing_preICA.dataset_type' "$CONFIG_FILE")"
PREPROC_DS_DESC="$(yq e '.dataset_descriptions.level-1.preprocessing_preICA.description' "$CONFIG_FILE")"

PREPROC_GENERATEDBY=()
n_preproc_gb=$(yq e '.dataset_descriptions.level-1.preprocessing_preICA.generatedby | length' "$CONFIG_FILE")
for ((idx=0; idx<n_preproc_gb; idx++)); do
  gb_name=$(yq e ".dataset_descriptions.level-1.preprocessing_preICA.generatedby[$idx].name" "$CONFIG_FILE")
  gb_version=$(yq e ".dataset_descriptions.level-1.preprocessing_preICA.generatedby[$idx].version" "$CONFIG_FILE")
  gb_desc=$(yq e ".dataset_descriptions.level-1.preprocessing_preICA.generatedby[$idx].description" "$CONFIG_FILE")
  
  # If the YAML version is "null" but gb_name is "FSL", try to fill from $FSL_VERSION
  if [ "$gb_name" = "FSL" ] && [ "$gb_version" = "null" ]; then
    gb_version="$FSL_VERSION"
  fi

  gb_string="Name=${gb_name}"
  [ "$gb_version" != "null" ] && gb_string+=",Version=${gb_version}"
  [ "$gb_desc"   != "null" ] && gb_string+=",Description=${gb_desc}"

  PREPROC_GENERATEDBY+=("$gb_string")
done

# 2) For 'aroma'
AROMA_DS_NAME="$(yq e '.dataset_descriptions.level-1.aroma.name' "$CONFIG_FILE")"
AROMA_DS_TYPE="$(yq e '.dataset_descriptions.level-1.aroma.dataset_type' "$CONFIG_FILE")"
AROMA_DS_DESC="$(yq e '.dataset_descriptions.level-1.aroma.description' "$CONFIG_FILE")"

AROMA_GENERATEDBY=()
n_aroma_gb=$(yq e '.dataset_descriptions.level-1.aroma.generatedby | length' "$CONFIG_FILE")
for ((idx=0; idx<n_aroma_gb; idx++)); do
  gb_name=$(yq e ".dataset_descriptions.level-1.aroma.generatedby[$idx].name" "$CONFIG_FILE")
  gb_version=$(yq e ".dataset_descriptions.level-1.aroma.generatedby[$idx].version" "$CONFIG_FILE")
  gb_desc=$(yq e ".dataset_descriptions.level-1.aroma.generatedby[$idx].description" "$CONFIG_FILE")
  
  # If the YAML version is "null" but gb_name is "FSL", try to fill from $FSL_VERSION
  if [ "$gb_name" = "FSL" ] && [ "$gb_version" = "null" ]; then
    gb_version="$FSL_VERSION"
  fi

  gb_string="Name=${gb_name}"
  [ "$gb_version" != "null" ] && gb_string+=",Version=${gb_version}"
  [ "$gb_desc"   != "null" ] && gb_string+=",Description=${gb_desc}"

  AROMA_GENERATEDBY+=("$gb_string")
done

# 3) For 'analysis_postICA'
POSTICA_DS_NAME="$(yq e '.dataset_descriptions.level-1.analysis_postICA.name' "$CONFIG_FILE")"
POSTICA_DS_TYPE="$(yq e '.dataset_descriptions.level-1.analysis_postICA.dataset_type' "$CONFIG_FILE")"
POSTICA_DS_DESC="$(yq e '.dataset_descriptions.level-1.analysis_postICA.description' "$CONFIG_FILE")"

POSTICA_GENERATEDBY=()
n_postica_gb=$(yq e '.dataset_descriptions.level-1.analysis_postICA.generatedby | length' "$CONFIG_FILE")
for ((idx=0; idx<n_postica_gb; idx++)); do
  gb_name=$(yq e ".dataset_descriptions.level-1.analysis_postICA.generatedby[$idx].name" "$CONFIG_FILE")
  gb_version=$(yq e ".dataset_descriptions.level-1.analysis_postICA.generatedby[$idx].version" "$CONFIG_FILE")
  gb_desc=$(yq e ".dataset_descriptions.level-1.analysis_postICA.generatedby[$idx].description" "$CONFIG_FILE")
  
  # If the YAML version is "null" but gb_name is "FSL", try to fill from $FSL_VERSION
  if [ "$gb_name" = "FSL" ] && [ "$gb_version" = "null" ]; then
    gb_version="$FSL_VERSION"
  fi

  gb_string="Name=${gb_name}"
  [ "$gb_version" != "null" ] && gb_string+=",Version=${gb_version}"
  [ "$gb_desc"   != "null" ] && gb_string+=",Description=${gb_desc}"

  POSTICA_GENERATEDBY+=("$gb_string")
done

# 4) For 'analysis'
FEAT_DS_NAME="$(yq e '.dataset_descriptions.level-1.feat_analysis.name' "$CONFIG_FILE")"
FEAT_DS_TYPE="$(yq e '.dataset_descriptions.level-1.feat_analysis.dataset_type' "$CONFIG_FILE")"
FEAT_DS_DESC="$(yq e '.dataset_descriptions.level-1.feat_analysis.description' "$CONFIG_FILE")"

FEAT_GENERATEDBY=()
n_feat_gb=$(yq e '.dataset_descriptions.level-1.feat_analysis.generatedby | length' "$CONFIG_FILE")
for ((idx=0; idx<n_feat_gb; idx++)); do
  gb_name=$(yq e ".dataset_descriptions.level-1.feat_analysis.generatedby[$idx].name" "$CONFIG_FILE")
  gb_version=$(yq e ".dataset_descriptions.level-1.feat_analysis.generatedby[$idx].version" "$CONFIG_FILE")
  gb_desc=$(yq e ".dataset_descriptions.level-1.feat_analysis.generatedby[$idx].description" "$CONFIG_FILE")
  
  # If the YAML version is "null" but gb_name is "FSL", try to fill from $FSL_VERSION
  if [ "$gb_name" = "FSL" ] && [ "$gb_version" = "null" ]; then
    gb_version="$FSL_VERSION"
  fi

  gb_string="Name=${gb_name}"
  [ "$gb_version" != "null" ] && gb_string+=",Version=${gb_version}"
  [ "$gb_desc"   != "null" ] && gb_string+=",Description=${gb_desc}"

  FEAT_GENERATEDBY+=("$gb_string")
done

###############################################################################
# Remaining Variables
###############################################################################
EV_FILES=()
ICA_AROMA=false
NONLINEAR_REG=false
OUTPUT_DIR=""
PREPROC_OUTPUT_DIR=""
ANALYSIS_OUTPUT_DIR=""
SUBJECT=""
SESSION=""
TASK=""
RUN=""
PREPROC_DESIGN_FILE=""
DESIGN_FILE=""
SLICE_TIMING_FILE=""
USE_SLICE_TIMING=false
HIGHPASS_CUTOFF=""
APPLY_HIGHPASS_FILTERING=false
USE_BBR=false
APPLY_NUISANCE_REG=false
DESIGN_ONLY=false
KEEP_FULL_PATHS=false
T1_IMAGE=""
FUNC_IMAGE=""
TEMPLATE=""

###############################################################################
# Parse command-line arguments
###############################################################################
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    --help|-h)
      usage
      ;;
    --preproc-design-file)
      PREPROC_DESIGN_FILE="$2"
      shift; shift
      ;;
    --design-file)
      DESIGN_FILE="$2"
      shift; shift
      ;;
    --t1-image)
      T1_IMAGE="$2"
      shift; shift
      ;;
    --func-image)
      FUNC_IMAGE="$2"
      shift; shift
      ;;
    --template)
      TEMPLATE="$2"
      shift; shift
      ;;
    --output-dir)
      OUTPUT_DIR="$2"
      shift; shift
      ;;
    --preproc-output-dir)
      PREPROC_OUTPUT_DIR="$2"
      shift; shift
      ;;
    --analysis-output-dir)
      ANALYSIS_OUTPUT_DIR="$2"
      shift; shift
      ;;
    --ev*)
      EV_FILES+=("$2")
      shift; shift
      ;;
    --ica-aroma)
      ICA_AROMA=true
      shift
      ;;
    --nonlinear-reg)
      NONLINEAR_REG=true
      shift
      ;;
    --subject)
      SUBJECT="$2"
      shift; shift
      ;;
    --session)
      SESSION="$2"
      shift; shift
      ;;
    --task)
      TASK="$2"
      shift; shift
      ;;
    --run)
      RUN="$2"
      shift; shift
      ;;
    --slice-timing-file)
      SLICE_TIMING_FILE="$2"
      USE_SLICE_TIMING=true
      shift; shift
      ;;
    --highpass-cutoff)
      HIGHPASS_CUTOFF="$2"
      APPLY_HIGHPASS_FILTERING=true
      shift; shift
      ;;
    --use-bbr)
      USE_BBR=true
      shift
      ;;
    --apply-nuisance-reg)
      APPLY_NUISANCE_REG=true
      shift
      ;;
    --design-only)
      DESIGN_ONLY=true
      shift
      ;;
    --keep-full-paths)
      KEEP_FULL_PATHS=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      usage
      ;;
  esac
done

# Remove any stray quotes
PREPROC_DESIGN_FILE=$(echo "$PREPROC_DESIGN_FILE" | tr -d "'\"")
DESIGN_FILE=$(echo "$DESIGN_FILE" | tr -d "'\"")
T1_IMAGE=$(echo "$T1_IMAGE" | tr -d "'\"")
FUNC_IMAGE=$(echo "$FUNC_IMAGE" | tr -d "'\"")
TEMPLATE=$(echo "$TEMPLATE" | tr -d "'\"")
OUTPUT_DIR=$(echo "$OUTPUT_DIR" | tr -d "'\"")
PREPROC_OUTPUT_DIR=$(echo "$PREPROC_OUTPUT_DIR" | tr -d "'\"")
ANALYSIS_OUTPUT_DIR=$(echo "$ANALYSIS_OUTPUT_DIR" | tr -d "'\"")
DESIGN_ONLY=$(echo "$DESIGN_ONLY" | tr -d "'\"")
KEEP_FULL_PATHS=$(echo "$KEEP_FULL_PATHS" | tr -d "'\"")

# Determine optional session segments for paths and filenames
session_path=""
session_label=""
[ -n "$SESSION" ] && { session_path="/$SESSION"; session_label="_${SESSION}"; }

###############################################################################
# Quick validations
###############################################################################
if [ "$ICA_AROMA" = false ]; then
  if [ -n "$DESIGN_FILE" ] && [ ${#EV_FILES[@]} -eq 0 ]; then
    echo "Error: No EV files provided for main analysis."
    exit 1
  fi
else
  if [ -n "$DESIGN_FILE" ] && [ ${#EV_FILES[@]} -eq 0 ] && [ -n "$ANALYSIS_OUTPUT_DIR" ]; then
    echo "Error: No EV files for post-ICA-AROMA stats."
    exit 1
  fi
fi

if [ -z "$T1_IMAGE" ] || [ -z "$FUNC_IMAGE" ] || [ -z "$TEMPLATE" ]; then
  echo "Error: Missing --t1-image, --func-image, or --template."
  exit 1
fi

###############################################################################
# Helper functions
###############################################################################
apply_sed_replacement() {
  local file="$1"
  local find_expr="$2"
  local replace_expr="$3"
  local tmpfile
  tmpfile=$(mktemp)
  sed "s|${find_expr}|${replace_expr}|g" "$file" > "$tmpfile"
  mv "$tmpfile" "$file"
}

adjust_slice_timing_settings() {
  local infile="$1"
  local outfile="$2"
  local slice_timing_file="$3"

  if [ "$USE_SLICE_TIMING" = true ] && [ -n "$slice_timing_file" ]; then
    # If slice timing is applied, use mode 4
    sed -e "s|@SLICE_TIMING@|4|g" \
        -e "s|@SLICE_TIMING_FILE@|$slice_timing_file|g" \
        "$infile" > "$outfile"
  else
    # If no slice timing, set to 0 and remove the reference
    sed -e "s|@SLICE_TIMING@|0|g" \
        -e "s|@SLICE_TIMING_FILE@||g" \
        "$infile" > "$outfile"
  fi
}

adjust_highpass_filter_settings() {
  local infile="$1"
  local outfile="$2"
  local highpass_cutoff="$3"
  if [ "$APPLY_HIGHPASS_FILTERING" = true ] && [ -n "$highpass_cutoff" ]; then
    sed "s|@HIGHPASS_CUTOFF@|$highpass_cutoff|g" "$infile" > "$outfile"
  else
    sed "s|@HIGHPASS_CUTOFF@|0|g" "$infile" > "$outfile"
  fi
}

strip_paths_if_needed() {
  local file="$1"
  if [ "$KEEP_FULL_PATHS" = false ]; then
    apply_sed_replacement "$file" "$FUNC_IMAGE" "$(basename \"$FUNC_IMAGE\")"
    apply_sed_replacement "$file" "$T1_IMAGE" "$(basename \"$T1_IMAGE\")"
    apply_sed_replacement "$file" "$TEMPLATE" "$(basename \"$TEMPLATE\")"
    [ -n "$OUTPUT_DIR" ] && apply_sed_replacement "$file" "$OUTPUT_DIR" "$(basename \"$OUTPUT_DIR\")"
    [ -n "$PREPROC_OUTPUT_DIR" ] && apply_sed_replacement "$file" "$PREPROC_OUTPUT_DIR" "$(basename \"$PREPROC_OUTPUT_DIR\")"
    [ -n "$ANALYSIS_OUTPUT_DIR" ] && apply_sed_replacement "$file" "$ANALYSIS_OUTPUT_DIR" "$(basename \"$ANALYSIS_OUTPUT_DIR\")"
    sed -i 's/""/"/g' "$file"
    apply_sed_replacement "$file" "set fmri(relative_yn) .*" "set fmri(relative_yn) 0"
  else
    apply_sed_replacement "$file" "set fmri(relative_yn) .*" "set fmri(relative_yn) 1"
  fi
}

###############################################################################
# Main logic
###############################################################################
npts=$(fslval "$FUNC_IMAGE" dim4 | xargs)
tr=$(fslval "$FUNC_IMAGE" pixdim4 | xargs)
tr=$(LC_NUMERIC=C printf "%.6f" "$tr")

##########################################################################
# Function to get the top-level "analysis" or "analysis_postICA" directory
# (or similarly structured directories) from a deeper .feat path.
# just do 4x `dirname`.
##########################################################################
get_top_level_analysis_dir() {
  local feat_path="$1"
  local dir
  dir="$(dirname "$feat_path")"       # .../sub-01[/ses-01]/func
  dir="$(dirname "$dir")"            # .../sub-01[/ses-01]
  if [[ "$dir" == */ses-* ]]; then
    dir="$(dirname "$dir")"           # .../sub-01
  fi
  dir="$(dirname "$dir")"             # .../analysis_postICA or analysis
  echo "$dir"
}

# ---------------------------------------------------------------------------
# Run ICA-AROMA using either python2.7 or a Docker container specified in
# $ICA_AROMA_CONTAINER. The container must provide Python 2.7. Prints
# [INFO] / [ERROR] messages and returns the command status.
# ---------------------------------------------------------------------------
run_ica_aroma() {
  local in_file="$1"
  local out_dir="$2"
  local mc_par="$3"
  local mask_file="$4"
  local affmat="$5"
  local warp_file="$6"
  local cmd

  # Automatically use a Docker image called "ica_aroma" if available and
  # ICA_AROMA_CONTAINER was not explicitly provided.
  if [ -z "$ICA_AROMA_CONTAINER" ] && command -v docker >/dev/null 2>&1; then
    if [ -n "$(docker images -q ica_aroma 2>/dev/null)" ]; then
      ICA_AROMA_CONTAINER="ica_aroma"
    fi
  fi

  if [ -n "$ICA_AROMA_CONTAINER" ]; then
    if ! command -v docker >/dev/null 2>&1; then
      echo "[ERROR] ICA_AROMA_CONTAINER is set but docker is unavailable" >&2
      return 1
    fi
    cmd=(docker run --rm --entrypoint "" \
         -v "${BASE_DIR}:${BASE_DIR}" -w "$(pwd)" \
         "$ICA_AROMA_CONTAINER" \
         python /ICA-AROMA/ica-aroma-via-docker.py \
         -in "$in_file" -out "$out_dir" -mc "$mc_par" -m "$mask_file" \
         -affmat "$affmat")
    [ -n "$ICA_AROMA_SKIP_PLOTS" ] && cmd+=( -np )
    [ -n "$warp_file" ] && cmd+=( -warp "$warp_file" )
  else
    local PYTHON2
    PYTHON2=$(command -v python2.7)
    if [ -z "$PYTHON2" ]; then
      echo "[ERROR] python2.7 not found in PATH (required for ICA-AROMA)" >&2
      return 1
    fi
    cmd=("$PYTHON2" "$ICA_AROMA_SCRIPT" -in "$in_file" -out "$out_dir" \
         -mc "$mc_par" -m "$mask_file" -affmat "$affmat")
    [ -n "$ICA_AROMA_SKIP_PLOTS" ] && cmd+=( -np )
    [ -n "$warp_file" ] && cmd+=( -warp "$warp_file" )
  fi

  echo "[INFO] Running: ${cmd[*]}"
  "${cmd[@]}"
  local status=$?
  if [ $status -eq 0 ]; then
    echo "[INFO] ICA-AROMA processed successfully."
  else
    echo "[ERROR] ICA-AROMA failed with exit code $status." >&2
  fi
  return $status
}

if [ "$ICA_AROMA" = true ]; then
  # --------------------------------------------------------------
  # 1. ICA-AROMA route
  # --------------------------------------------------------------
  if [ -z "$PREPROC_DESIGN_FILE" ] || [ -z "$PREPROC_OUTPUT_DIR" ]; then
    echo "Error: Missing --preproc-design-file or --preproc-output-dir for ICA-AROMA."
    exit 1
  fi

  # 1A. FEAT Preprocessing
  PREPROC_DESIGN_OUT="$(dirname "$PREPROC_OUTPUT_DIR")/${SUBJECT}${session_label}_${RUN}_$(basename "$PREPROC_DESIGN_FILE")"
  mkdir -p "$(dirname "$PREPROC_DESIGN_OUT")"

  sed -e "s|@OUTPUT_DIR@|$PREPROC_OUTPUT_DIR|g" \
      -e "s|@FUNC_IMAGE@|$FUNC_IMAGE|g" \
      -e "s|@T1_IMAGE@|$T1_IMAGE|g" \
      -e "s|@TEMPLATE@|$TEMPLATE|g" \
      -e "s|@NPTS@|$npts|g" \
      -e "s|@TR@|$tr|g" \
      "$PREPROC_DESIGN_FILE" > "$PREPROC_DESIGN_OUT.tmp"

  adjust_slice_timing_settings \
    "$PREPROC_DESIGN_OUT.tmp" \
    "$PREPROC_DESIGN_OUT" \
    "$SLICE_TIMING_FILE"

  rm "$PREPROC_DESIGN_OUT.tmp"

  if [ "$NONLINEAR_REG" = true ]; then
    apply_sed_replacement "$PREPROC_DESIGN_OUT" \
      "set fmri(regstandard_nonlinear_yn) .*" \
      "set fmri(regstandard_nonlinear_yn) 1"
  else
    apply_sed_replacement "$PREPROC_DESIGN_OUT" \
      "set fmri(regstandard_nonlinear_yn) .*" \
      "set fmri(regstandard_nonlinear_yn) 0"
  fi

  if [ "$USE_BBR" = true ]; then
    apply_sed_replacement "$PREPROC_DESIGN_OUT" \
      "set fmri(reghighres_dof) .*" \
      "set fmri(reghighres_dof) BBR"
  else
    apply_sed_replacement "$PREPROC_DESIGN_OUT" \
      "set fmri(reghighres_dof) .*" \
      "set fmri(reghighres_dof) 12"
  fi

  strip_paths_if_needed "$PREPROC_DESIGN_OUT"

  echo ""
  echo "[FEAT PREPROCESSING]"
  if [ "$DESIGN_ONLY" = true ]; then
    echo "Only creating design.fsf files. Skipping."
  else
    if [ ! -d "$PREPROC_OUTPUT_DIR" ]; then
      feat "$PREPROC_DESIGN_OUT" || { echo "FEAT preprocessing failed."; exit 1; }
      echo "- FEAT preprocessing completed at $PREPROC_OUTPUT_DIR"

      preproc_generatedby_args=()
      for gb_item in "${PREPROC_GENERATEDBY[@]}"; do
        preproc_generatedby_args+=(--generatedby "$gb_item")
      done

      PREPROC_TOP_DIR="$(get_top_level_analysis_dir "$PREPROC_OUTPUT_DIR")"
      "$SCRIPT_DIR/create_dataset_description.sh" \
        --analysis-dir "$PREPROC_TOP_DIR" \
        --ds-name "$PREPROC_DS_NAME" \
        --dataset-type "$PREPROC_DS_TYPE" \
        --description "$PREPROC_DS_DESC" \
        --bids-version "$BIDS_VERSION" \
        "${preproc_generatedby_args[@]}"

      output_dir_name=$(basename "$PREPROC_OUTPUT_DIR" .feat)
      mask_output="${PREPROC_OUTPUT_DIR}/${output_dir_name}_example_func_mask.nii.gz"
      example_func="${PREPROC_OUTPUT_DIR}/example_func.nii.gz"

      echo ""
      echo "[MASK CREATION]"
      bet "$example_func" "$mask_output" -f 0.3 || { echo "Mask creation failed."; exit 1; }
      echo "- Mask created at $mask_output"
    else
      echo "FEAT preprocessing already completed at $PREPROC_OUTPUT_DIR"
    fi
  fi



  # 1B. ICA-AROMA
  echo -e "\n[ICA-AROMA PROCESSING]"
  ICA_AROMA_OUTPUT_DIR="${BASE_DIR}/derivatives/fsl/level-1/aroma/${SUBJECT}${session_path}/func"
  if [ -n "$TASK" ]; then
    ICA_AROMA_OUTPUT_DIR="${ICA_AROMA_OUTPUT_DIR}/${SUBJECT}${session_label}_task-${TASK}_${RUN}.feat"
  else
    ICA_AROMA_OUTPUT_DIR="${ICA_AROMA_OUTPUT_DIR}/${SUBJECT}${session_label}_${RUN}.feat"
  fi

  if [ "$DESIGN_ONLY" = true ]; then
    echo "Only creating design.fsf files. Skipping."
  else
  
  denoised_func="${ICA_AROMA_OUTPUT_DIR}/denoised_func_data_nonaggr.nii.gz"
  if [ ! -f "$denoised_func" ]; then
    filtered_func_data="${PREPROC_OUTPUT_DIR}/filtered_func_data.nii.gz"
    mc_par="${PREPROC_OUTPUT_DIR}/mc/prefiltered_func_data_mcf.par"
    affmat="${PREPROC_OUTPUT_DIR}/reg/example_func2highres.mat"
    warp_file="${PREPROC_OUTPUT_DIR}/reg/highres2standard_warp.nii.gz"
    mask_file="$mask_output"

    warp_arg=""
    [ "$NONLINEAR_REG" = true ] && warp_arg="$warp_file"

    run_ica_aroma "$filtered_func_data" "$ICA_AROMA_OUTPUT_DIR" "$mc_par" \
      "$mask_file" "$affmat" "$warp_arg"
    rc=$?
    if [ $rc -ne 0 ]; then
      echo "ICA-AROMA failed with exit code $rc. Skipping this run."
      exit $rc
    fi
    if [ ! -f "$denoised_func" ]; then
      echo "Error: denoised_func_data_nonaggr.nii.gz not created at $denoised_func." >&2
      echo "       Inspect ICA-AROMA container logs for more details." >&2
      exit 1
    fi
    echo "- Denoised data at $denoised_func"
    
    # Build an array for the --generatedby flags
    aroma_generatedby_args=()
    for gb_item in "${AROMA_GENERATEDBY[@]}"; do
      aroma_generatedby_args+=(--generatedby "$gb_item")
    done

    # Create dataset_description.json in aroma top-level
    AROMA_TOP_DIR="$(get_top_level_analysis_dir "$ICA_AROMA_OUTPUT_DIR")"
    "$SCRIPT_DIR/create_dataset_description.sh" \
      --analysis-dir "$AROMA_TOP_DIR" \
      --ds-name "$AROMA_DS_NAME" \
      --dataset-type "$AROMA_DS_TYPE" \
      --description "$AROMA_DS_DESC" \
      --bids-version "$BIDS_VERSION" \
      "${aroma_generatedby_args[@]}"

  else
    echo "ICA-AROMA already processed at $denoised_func"
  fi

  fi


  # 1C. Optional nuisance regression
  echo ""
  echo "[NUISANCE REGRESSION AFTER ICA-AROMA]"
  if [ "$DESIGN_ONLY" = true ]; then
    echo "Only creating design.fsf files. Skipping."
  elif [ "$APPLY_NUISANCE_REG" = true ]; then
    nuisance_regressed_func="${ICA_AROMA_OUTPUT_DIR}/denoised_func_data_nonaggr_nuis.nii.gz"
    if [ -f "$nuisance_regressed_func" ]; then
      echo "Nuisance regression already performed at $nuisance_regressed_func"
      denoised_func="$nuisance_regressed_func"
    else
      if [ ! -f "$denoised_func" ]; then
        echo "Denoised data missing before nuisance regression. Skipping."
        exit 0
      fi

      SEG_DIR="${ICA_AROMA_OUTPUT_DIR}/segmentation"
      mkdir -p "$SEG_DIR"

      echo -e "Segmenting structural image (FAST)..."
      fast -t 1 -n 3 -H 0.1 -I 4 -l 20.0 -o ${SEG_DIR}/T1w_brain "$T1_IMAGE"
      echo "  - Segmentation completed at:"
      echo "    ${SEG_DIR}/T1w_brain_pve_2.nii.gz"
      echo "    ${SEG_DIR}/T1w_brain_pve_1.nii.gz"
      echo "    ${SEG_DIR}/T1w_brain_pve_0.nii.gz"
      
      fslmaths ${SEG_DIR}/T1w_brain_pve_2.nii.gz -thr 0.8 -bin ${SEG_DIR}/WM_mask.nii.gz
      fslmaths ${SEG_DIR}/T1w_brain_pve_0.nii.gz -thr 0.8 -bin ${SEG_DIR}/CSF_mask.nii.gz
      echo "  - WM and CSF masks created at:"
      echo "    WM Mask: ${SEG_DIR}/WM_mask.nii.gz"
      echo "    CSF Mask: ${SEG_DIR}/CSF_mask.nii.gz"

      echo -e "\nTransforming masks to functional space..."
      convert_xfm -inverse -omat ${PREPROC_OUTPUT_DIR}/reg/highres2example_func.mat \
        ${PREPROC_OUTPUT_DIR}/reg/example_func2highres.mat

      flirt -in ${SEG_DIR}/WM_mask.nii.gz \
        -ref ${PREPROC_OUTPUT_DIR}/example_func.nii.gz \
        -applyxfm -init ${PREPROC_OUTPUT_DIR}/reg/highres2example_func.mat \
        -out ${SEG_DIR}/WM_mask_func.nii.gz -interp nearestneighbour

      flirt -in ${SEG_DIR}/CSF_mask.nii.gz \
        -ref ${PREPROC_OUTPUT_DIR}/example_func.nii.gz \
        -applyxfm -init ${PREPROC_OUTPUT_DIR}/reg/highres2example_func.mat \
        -out ${SEG_DIR}/CSF_mask_func.nii.gz -interp nearestneighbour
      
      echo "  - Masks transformed to functional space:"
      echo "    ${SEG_DIR}/WM_mask_func.nii.gz"
      echo "    ${SEG_DIR}/CSF_mask_func.nii.gz"

      echo -e "\nExtracting WM and CSF time series..."
      fslmeants -i "$denoised_func" -o ${SEG_DIR}/WM_timeseries.txt -m ${SEG_DIR}/WM_mask_func.nii.gz
      fslmeants -i "$denoised_func" -o ${SEG_DIR}/CSF_timeseries.txt -m ${SEG_DIR}/CSF_mask_func.nii.gz
      echo "  - WM timeseries: ${SEG_DIR}/WM_timeseries.txt"
      echo "  - CSF timeseries: ${SEG_DIR}/CSF_timeseries.txt"

      echo -e "\nCreating linear trend regressor..."
      npts=$(fslval "$denoised_func" dim4)
      seq 0 $((npts - 1)) > ${SEG_DIR}/linear_trend.txt
      echo "  - Linear trend regressor created at ${SEG_DIR}/linear_trend.txt"


      echo -e "\nCombining regressors..."
      paste ${SEG_DIR}/WM_timeseries.txt \
            ${SEG_DIR}/CSF_timeseries.txt \
            ${SEG_DIR}/linear_trend.txt > ${SEG_DIR}/nuisance_regressors.txt
      echo "  - Combined regressors at ${SEG_DIR}/nuisance_regressors.txt"

      echo -e "\nPerforming nuisance regression..."
      fsl_regfilt -i "$denoised_func" \
                  -d ${SEG_DIR}/nuisance_regressors.txt \
                  -f "1,2,3" \
                  -o "$nuisance_regressed_func"
      echo "  - Nuisance regression completed at ${nuisance_regressed_func}"

      denoised_func="$nuisance_regressed_func"
    fi
  else
    echo "Skipping nuisance regression."
  fi

  # 1D. Main Analysis (stats) after ICA-AROMA if requested
  if [ -n "$ANALYSIS_OUTPUT_DIR" ] && [ -n "$DESIGN_FILE" ]; then
    echo ""
    echo "[FEAT MAIN ANALYSIS (POST-ICA)]"

    ANALYSIS_DESIGN_OUT_DIR="$(dirname "$ANALYSIS_OUTPUT_DIR")"
    design_prefix="${SUBJECT}${session_label}"
    [ -n "$TASK" ] && design_prefix+="_task-${TASK}"
    design_prefix+="_${RUN}"
    ANALYSIS_DESIGN_FILE="${ANALYSIS_DESIGN_OUT_DIR}/${design_prefix}_$(basename "$DESIGN_FILE")"
    mkdir -p "$ANALYSIS_DESIGN_OUT_DIR"

    if [ "$DESIGN_ONLY" = true ]; then
      npts=$(fslval "$FUNC_IMAGE" dim4 | xargs)
      tr=$(fslval "$FUNC_IMAGE" pixdim4 | xargs)
    else
      if [ ! -f "$denoised_func" ]; then
        echo "Denoised data not found before main stats. Skipping."
        exit 0
      fi
      npts=$(fslval "$denoised_func" dim4 | xargs)
      tr=$(fslval "$denoised_func" pixdim4 | xargs)
    fi
    tr=$(LC_NUMERIC=C printf "%.6f" "$tr")

    sed -e "s|@OUTPUT_DIR@|$ANALYSIS_OUTPUT_DIR|g" \
        -e "s|@FUNC_IMAGE@|$denoised_func|g" \
        -e "s|@T1_IMAGE@|$T1_IMAGE|g" \
        -e "s|@TEMPLATE@|$TEMPLATE|g" \
        -e "s|@NPTS@|$npts|g" \
        -e "s|@TR@|$tr|g" \
        "$DESIGN_FILE" > "$ANALYSIS_DESIGN_FILE.tmp"

    USE_SLICE_TIMING=false
    SLICE_TIMING_FILE=""
    adjust_slice_timing_settings "$ANALYSIS_DESIGN_FILE.tmp" "$ANALYSIS_DESIGN_FILE.hp" "$SLICE_TIMING_FILE"
    adjust_highpass_filter_settings "$ANALYSIS_DESIGN_FILE.hp" "$ANALYSIS_DESIGN_FILE" "$HIGHPASS_CUTOFF"
    rm "$ANALYSIS_DESIGN_FILE.tmp" "$ANALYSIS_DESIGN_FILE.hp"

    if [ "$NONLINEAR_REG" = true ]; then
      apply_sed_replacement "$ANALYSIS_DESIGN_FILE" "set fmri(regstandard_nonlinear_yn) .*" "set fmri(regstandard_nonlinear_yn) 1"
    else
      apply_sed_replacement "$ANALYSIS_DESIGN_FILE" "set fmri(regstandard_nonlinear_yn) .*" "set fmri(regstandard_nonlinear_yn) 0"
    fi

    if [ "$USE_BBR" = true ]; then
      apply_sed_replacement "$ANALYSIS_DESIGN_FILE" "set fmri(reghighres_dof) .*" "set fmri(reghighres_dof) BBR"
    else
      apply_sed_replacement "$ANALYSIS_DESIGN_FILE" "set fmri(reghighres_dof) .*" "set fmri(reghighres_dof) 12"
    fi

    for ((i=0; i<${#EV_FILES[@]}; i++)); do
      ev_num=$((i+1))
      apply_sed_replacement "$ANALYSIS_DESIGN_FILE" "@EV${ev_num}@" "${EV_FILES[i]}"
    done

    strip_paths_if_needed "$ANALYSIS_DESIGN_FILE"

    if [ "$DESIGN_ONLY" = true ]; then
      echo "Only creating design.fsf files. Skipping."
    else
      feat "$ANALYSIS_DESIGN_FILE" || { echo "FEAT main analysis failed."; exit 1; }
      echo "- FEAT main analysis (post-ICA) completed at $ANALYSIS_OUTPUT_DIR"

      postica_generatedby_args=()
      for gb_item in "${POSTICA_GENERATEDBY[@]}"; do
        postica_generatedby_args+=(--generatedby "$gb_item")
      done

      TOP_ANALYSIS_DIR="$(get_top_level_analysis_dir "$ANALYSIS_OUTPUT_DIR")"
      "$SCRIPT_DIR/create_dataset_description.sh" \
        --analysis-dir "$TOP_ANALYSIS_DIR" \
        --ds-name "$POSTICA_DS_NAME" \
        --dataset-type "$POSTICA_DS_TYPE" \
        --description "$POSTICA_DS_DESC" \
        --bids-version "$BIDS_VERSION" \
        "${postica_generatedby_args[@]}"
    fi
  else
    echo ""
    echo "Preprocessing and ICA-AROMA completed (no main stats)."
  fi

else
  # --------------------------------------------------------------
  # 2. Non-ICA-AROMA route
  # --------------------------------------------------------------
  if [ -z "$DESIGN_FILE" ] || [ -z "$OUTPUT_DIR" ]; then
    echo "Error: Missing --design-file or --output-dir."
    exit 1
  fi

  if [ -d "$OUTPUT_DIR" ]; then
    echo ""
    echo "FEAT analysis already exists at $OUTPUT_DIR"
  else
    DESIGN_OUT_DIR="$(dirname "$OUTPUT_DIR")"
    design_prefix="${SUBJECT}${session_label}_${RUN}"
    DESIGN_OUT_FILE="${DESIGN_OUT_DIR}/${design_prefix}_$(basename "$DESIGN_FILE")"
    mkdir -p "$DESIGN_OUT_DIR"

    sed -e "s|@OUTPUT_DIR@|$OUTPUT_DIR|g" \
        -e "s|@FUNC_IMAGE@|$FUNC_IMAGE|g" \
        -e "s|@T1_IMAGE@|$T1_IMAGE|g" \
        -e "s|@TEMPLATE@|$TEMPLATE|g" \
        -e "s|@NPTS@|$npts|g" \
        -e "s|@TR@|$tr|g" \
        "$DESIGN_FILE" > "$DESIGN_OUT_FILE.tmp"

    adjust_slice_timing_settings \
      "$DESIGN_OUT_FILE.tmp" \
      "$DESIGN_OUT_FILE.hp" \
      "$SLICE_TIMING_FILE"

    adjust_highpass_filter_settings \
      "$DESIGN_OUT_FILE.hp" \
      "$DESIGN_OUT_FILE" \
      "$HIGHPASS_CUTOFF"

    rm "$DESIGN_OUT_FILE.tmp" "$DESIGN_OUT_FILE.hp"

    # Non-linear registration
    if [ "$NONLINEAR_REG" = true ]; then
      apply_sed_replacement "$DESIGN_OUT_FILE" \
        "set fmri(regstandard_nonlinear_yn) .*" \
        "set fmri(regstandard_nonlinear_yn) 1"
    else
      apply_sed_replacement "$DESIGN_OUT_FILE" \
        "set fmri(regstandard_nonlinear_yn) .*" \
        "set fmri(regstandard_nonlinear_yn) 0"
    fi

    # BBR or 12 DOF
    if [ "$USE_BBR" = true ]; then
      apply_sed_replacement "$DESIGN_OUT_FILE" \
        "set fmri(reghighres_dof) .*" \
        "set fmri(reghighres_dof) BBR"
    else
      apply_sed_replacement "$DESIGN_OUT_FILE" \
        "set fmri(reghighres_dof) .*" \
        "set fmri(reghighres_dof) 12"
    fi

    # Insert EV files
    for ((i=0; i<${#EV_FILES[@]}; i++)); do
      ev_num=$((i+1))
      apply_sed_replacement "$DESIGN_OUT_FILE" \
        "@EV${ev_num}@" \
        "${EV_FILES[i]}"
    done

    strip_paths_if_needed "$DESIGN_OUT_FILE"

    echo ""
    echo "[FEAT MAIN ANALYSIS]"
    if [ "$DESIGN_ONLY" = true ]; then
      echo "Only creating design.fsf files. Skipping."
    else
      feat "$DESIGN_OUT_FILE" || { echo "FEAT failed."; exit 1; }
      echo "- FEAT main analysis completed at $OUTPUT_DIR"
    fi
  fi

  
  
    # Build an array for the --generatedby flags
    if [ "$DESIGN_ONLY" != true ]; then
      feat_generatedby_args=()
      for gb_item in "${FEAT_GENERATEDBY[@]}"; do
        feat_generatedby_args+=(--generatedby "$gb_item")
      done

      TOP_ANALYSIS_DIR="$(get_top_level_analysis_dir "$OUTPUT_DIR")"
      "$SCRIPT_DIR/create_dataset_description.sh" \
        --analysis-dir "$TOP_ANALYSIS_DIR" \
        --ds-name "$FEAT_DS_NAME" \
        --dataset-type "$FEAT_DS_TYPE" \
        --description "$FEAT_DS_DESC" \
        --bids-version "$BIDS_VERSION" \
        "${feat_generatedby_args[@]}"
    fi
fi

# Cleanup extraneous files
find "$(dirname "$SCRIPT_DIR")" -type f -name "*''" -exec rm -f {} \; 2>/dev/null
