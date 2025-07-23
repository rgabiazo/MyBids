#!/bin/bash
###############################################################################
# feat_first_level_analysis.sh
#
# Purpose:
#   Configure and execute FSL FEAT first-level analyses for a BIDS dataset.
#   Optional steps include ICA-AROMA, slice timing correction, nuisance
#   regression and high-pass filtering.
#
# Usage:
#   feat_first_level_analysis.sh
#
# Usage Examples:
#   ./feat_first_level_analysis.sh
#
# Options:
#   Interactive prompts for base directory, ICA-AROMA, slice timing,
#   BBR registration, nuisance regression, high-pass filtering and subject
#   selection.
#
# Requirements:
#   FSL, yq and optionally Python 2.7 for ICA-AROMA.
#
# Notes:
#   Reads configuration from <BIDS_BASE>/code/config/config.yaml for output
#   directories and dataset_description fields.
#
###############################################################################

# Check if yq is installed
if ! command -v yq &> /dev/null
then
  echo -e "\nERROR: 'yq' (YAML processor) not found in your PATH. Please install yq.\n"
  exit 1
fi

# Load Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR_DEFAULT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Prompt for the BIDS base directory
echo -e "\n=== First-Level Analysis: Preprocessing & Statistics ===\n"
echo -ne "Please enter the base directory or press Enter/Return to use the default [${BASE_DIR_DEFAULT}]: \n> "
read base_dir_input
if [ -n "$base_dir_input" ]; then
  BASE_DIR="$base_dir_input"
else
  BASE_DIR="$BASE_DIR_DEFAULT"
fi
echo -e "Using base directory: $BASE_DIR\n"

# Initialize logging now that BASE_DIR is known
LOG_DIR="${BASE_DIR}/code/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/feat_first_level_analysis_$(date +%Y-%m-%d_%H-%M-%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1
echo "Log file: $LOG_FILE"

# Load config.yaml
CONFIG_FILE="${BASE_DIR}/code/config/config.yaml"

### Read from the config.yaml
PREPROC_PARENT_DIR="$(yq e '.fsl.level-1.preprocess_output_dir' "$CONFIG_FILE")"
AROMA_PARENT_DIR="$(yq e '.fsl.level-1.aroma_output_dir' "$CONFIG_FILE")"
ANALYSIS_PARENT_DIR="$(yq e '.fsl.level-1.analysis_output_dir' "$CONFIG_FILE")"
ANALYSIS_POSTICA_PARENT_DIR="$(yq e '.fsl.level-1.analysis_postICA_output_dir' "$CONFIG_FILE")"

BIDS_VERSION="$(yq e '.bids_version' "$CONFIG_FILE")"

# Read from config.yaml
# ============== PREPROCESSING PRE ICA-AROMA PARSING ==============
PREPROC_DS_NAME="$(yq e '.dataset_descriptions.level-1.preprocessing_preICA.name' "$CONFIG_FILE")"
PREPROC_DS_TYPE="$(yq e '.dataset_descriptions.level-1.preprocessing_preICA.dataset_type' "$CONFIG_FILE")"
PREPROC_DS_DESC="$(yq e '.dataset_descriptions.level-1.preprocessing_preICA.description' "$CONFIG_FILE")"

# ============== ICA-AROMA BLOCK ==============
AROMA_DS_NAME="$(yq e '.dataset_descriptions.level-1.aroma.name' "$CONFIG_FILE")"
AROMA_DS_TYPE="$(yq e '.dataset_descriptions.level-1.aroma.dataset_type' "$CONFIG_FILE")"
AROMA_DS_DESC="$(yq e '.dataset_descriptions.level-1.aroma.description' "$CONFIG_FILE")"

# ============== FEAT ANALYSIS (or 'analysis') BLOCK ==============
FEAT_DS_NAME="$(yq e '.dataset_descriptions.level-1.feat_analysis.name' "$CONFIG_FILE")"
FEAT_DS_TYPE="$(yq e '.dataset_descriptions.level-1.feat_analysis.dataset_type' "$CONFIG_FILE")"
FEAT_DS_DESC="$(yq e '.dataset_descriptions.level-1.feat_analysis.description' "$CONFIG_FILE")"

DESIGN_FILES_DIR="${BASE_DIR}/code/design_files"

###############################################################################
# Prompt for analysis choices
###############################################################################
# 1) ICA-AROMA
while true; do
  echo -ne "Do you want to apply ICA-AROMA? (y/n): "
  read apply_ica_aroma
  case "$apply_ica_aroma" in
    [Yy]* )
      ica_aroma=true
      while true; do
        echo -ne "Do you want to apply non-linear registration? (y/n): "
        read apply_nonlinear_reg
        case "$apply_nonlinear_reg" in
          [Yy]* )
            nonlinear_reg=true
            echo -e "Non-linear registration will be applied with ICA-AROMA.\n"
            break
            ;;
          [Nn]* )
            nonlinear_reg=false
            echo -e "Non-linear registration will not be applied with ICA-AROMA.\n"
            break
            ;;
          * ) echo "Invalid input, please enter y or n." ;;
        esac
      done
      break
      ;;
    [Nn]* )
      ica_aroma=false
      nonlinear_reg=false
      echo "Skipping ICA-AROMA application."
      break
      ;;
    * ) echo "Invalid input, please enter y or n." ;;
  esac
done

# 2) Slice timing correction
while true; do
  echo -ne "Do you want to apply slice timing correction? (y/n): "
  read apply_slice_timing
  case "$apply_slice_timing" in
    [Yy]* )
      slice_timing_correction=true
      echo -e "Slice timing correction will be applied.\n"
      break
      ;;
    [Nn]* )
      slice_timing_correction=false
      echo -e "Skipping slice timing correction.\n"
      break
      ;;
    * ) echo "Invalid input, please enter y or n." ;;
  esac
done

# 3) BBR
while true; do
  echo -ne "Do you want to use Boundary-Based Registration (BBR)? (y/n): "
  read use_bbr_input
  case "$use_bbr_input" in
    [Yy]* )
      use_bbr=true
      echo -e "BBR will be used.\n"
      break
      ;;
    [Nn]* )
      use_bbr=false
      echo -e "Using default 12 DOF affine registration.\n"
      break
      ;;
    * ) echo "Invalid input, please enter y or n." ;;
  esac
done

# 4) If ICA-AROMA, prompt nuisance regression & stats
apply_nuisance_regression=false
apply_aroma_stats=false
if [ "$ica_aroma" = true ]; then
  while true; do
    echo -ne "Do you want to apply nuisance regression after ICA-AROMA? (y/n): "
    read apply_nuisance_input
    case "$apply_nuisance_input" in
      [Yy]* )
        apply_nuisance_regression=true
        echo -e "Nuisance regression after ICA-AROMA will be applied.\n"
        break
        ;;
      [Nn]* )
        apply_nuisance_regression=false
        echo -e "Skipping nuisance regression after ICA-AROMA.\n"
        break
        ;;
      * ) echo "Invalid input, please enter y or n." ;;
    esac
  done

  while true; do
    echo -ne "Do you want to apply statistics (main FEAT analysis) after ICA-AROMA? (y/n): "
    read apply_aroma_stats_input
    case "$apply_aroma_stats_input" in
      [Yy]* )
        apply_aroma_stats=true
        echo -e "Statistics will be run after ICA-AROMA.\n"
        break
        ;;
      [Nn]* )
        apply_aroma_stats=false
        echo -e "Only ICA-AROMA preprocessing (no main FEAT analysis after ICA-AROMA).\n"
        break
        ;;
      * ) echo "Invalid input, please enter y or n." ;;
    esac
  done
fi

###############################################################################
# FSF Design File Selection
###############################################################################

select_design_file() {
  local search_pattern="$1"
  local exclude_pattern="$2"
  local design_files=()

  if [ -n "$exclude_pattern" ]; then
    design_files=($(find "$DESIGN_FILES_DIR" -type f -name "$search_pattern" ! -name "$exclude_pattern"))
  else
    design_files=($(find "$DESIGN_FILES_DIR" -type f -name "$search_pattern"))
  fi

  if [ ${#design_files[@]} -eq 0 ]; then
    echo "No design files found with pattern '$search_pattern' in $DESIGN_FILES_DIR."
    exit 1
  elif [ ${#design_files[@]} -eq 1 ]; then
    # Only one match
    DEFAULT_DESIGN_FILE="${design_files[0]}"
  else
    # Multiple matches
    echo ""
    echo "Multiple design files found:"
    PS3=$'Select the design file (enter a number):\n> '
    select selected_design_file in "${design_files[@]}"; do
      echo "> $REPLY"
      if [ -n "$selected_design_file" ]; then
        DEFAULT_DESIGN_FILE="$selected_design_file"
        break
      else
        echo "Invalid selection."
      fi
    done
  fi
}

###############################################################################
# Decide design files
###############################################################################
if [ "$ica_aroma" = true ]; then
  if [ "$apply_aroma_stats" = true ]; then
    echo -e "Please enter the path for the ICA-AROMA main analysis design.fsf or press Enter/Return for [${DESIGN_FILES_DIR}]:"
    echo -ne "> "
    read design_file_input
    if [ -n "$design_file_input" ]; then
      design_file="$design_file_input"
    else
      select_design_file "*desc-ICAAROMAstats_design.fsf"
      design_file="$DEFAULT_DESIGN_FILE"
    fi
    echo -e "Using ICA-AROMA main analysis design file: $design_file"
  else
    design_file=""
  fi

  echo -e "\nPlease enter the path for the ICA-AROMA preprocessing design.fsf or press Enter/Return for [${DESIGN_FILES_DIR}]:"
  echo -ne "> "
  read preproc_design_file_input
  if [ -n "$preproc_design_file_input" ]; then
    preproc_design_file="$preproc_design_file_input"
  else
    select_design_file "*desc-ICAAROMApreproc_design.fsf"
    preproc_design_file="$DEFAULT_DESIGN_FILE"
  fi
  echo -e "Using ICA-AROMA preprocessing design file: $preproc_design_file"

else
  echo -e "\nPlease enter the path for the main analysis design.fsf or press Enter/Return for [${DESIGN_FILES_DIR}]:"
  echo -ne "> "
  read design_file_input
  if [ -n "$design_file_input" ]; then
    design_file="$design_file_input"
  else
    select_design_file "task-*.fsf" "*desc-ICAAROMAstats*"
    design_file="$DEFAULT_DESIGN_FILE"
  fi
  echo -e "Using main analysis design file: $design_file"

  preproc_design_file=""
fi

###############################################################################
# Skull-stripped T1 selection
###############################################################################

while true; do
  echo -e "\nSelect the skull-stripped T1 images directory or press Enter/Return for [BET]:"
  echo "1. BET skull-stripped T1 images"
  echo "2. SynthStrip skull-stripped T1 images"
  echo -ne "> "
  read skull_strip_choice
  case "$skull_strip_choice" in
    "1" | "" )
      skull_strip_choice="1"
      echo -e "Using BET skull-stripped T1 images.\n"
      break
      ;;
    "2" )
      echo -e "Using SynthStrip skull-stripped T1 images.\n"
      break
      ;;
    * ) echo "Invalid input, please enter 1 or 2 (or Enter for default)." ;;
  esac
done

BET_DIR="${BASE_DIR}/derivatives/fsl"
SYNTHSTRIP_DIR="${BASE_DIR}/derivatives/freesurfer"
if [ "$skull_strip_choice" = "2" ]; then
  skull_strip_dir="$SYNTHSTRIP_DIR"
else
  skull_strip_dir="$BET_DIR"
fi

# Setup data directories
TOPUP_OUTPUT_BASE="${BASE_DIR}/derivatives/fsl/topup"
ICA_AROMA_DIR="${BASE_DIR}/derivatives/ICA_AROMA"
CUSTOM_EVENTS_DIR="${BASE_DIR}/derivatives/custom_events"
SLICE_TIMING_DIR="${BASE_DIR}/derivatives/slice_timing"

# Fieldmap (Topup) selection
###############################################################################
fieldmap_corrected=false
while true; do
  echo -ne "Do you want to use field map corrected runs? (y/n): "
  read use_fieldmap
  case $use_fieldmap in
    [Yy]* )
      fieldmap_corrected=true
      echo -e "Using field map corrected runs.\n"
      break
      ;;
    [Nn]* )
      fieldmap_corrected=false
      echo -e "Skipping field map correction.\n"
      break
      ;;
    * ) echo "Invalid input, please enter y or n:" ;;
  esac
done

###############################################################################
# Prompt for EVs choice
###############################################################################
prompt_for_evs=false
if [ "$ica_aroma" = false ]; then
  prompt_for_evs=true
elif [ "$ica_aroma" = true ] && [ "$apply_aroma_stats" = true ]; then
  prompt_for_evs=true
fi

###############################################################################
# High-pass filtering (only if main analysis)
###############################################################################
highpass_filtering=false
highpass_cutoff=0
if [ "$prompt_for_evs" = true ]; then
  while true; do
    echo -ne "Do you want to apply high-pass filtering during the main FEAT analysis? (y/n): "
    read apply_highpass_filtering
    case "$apply_highpass_filtering" in
      [Yy]* )
        highpass_filtering=true
        while true; do
          echo -e "Enter the high-pass filter cutoff value in seconds, or press Enter/Return to use the default cutoff of 100:"
          echo -ne "> "
          read hp_input
          echo "> $hp_input"
          [ -z "$hp_input" ] && hp_input=100
          if [[ "$hp_input" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
            highpass_cutoff="$hp_input"
            echo -e "High-pass filtering will be applied with a cutoff of $highpass_cutoff seconds.\n"
            break 2
          else
            echo "Invalid cutoff. Please enter a numeric value."
          fi
        done
        ;;
      [Nn]* )
        highpass_filtering=false
        echo -e "Skipping high-pass filtering.\n"
        break
        ;;
      * ) echo "Invalid input, please enter y or n." ;;
    esac
  done
fi

###############################################################################
# Prompt for EVs selection
###############################################################################
EV_NAMES=()
num_evs=0
if [ "$prompt_for_evs" = true ]; then
  while true; do
    echo -ne "Enter the number of EVs: "
    read num_evs
    if [[ "$num_evs" =~ ^[0-9]+$ ]] && [ "$num_evs" -gt 0 ]; then
      break
    else
      echo "Invalid integer. Please try again."
    fi
  done

  echo ""
  echo "Enter the condition names for the EVs in order."
  for ((i=1; i<=num_evs; i++)); do
    echo -ne "Condition name for EV$i: "
    read ev_name
    EV_NAMES+=("$ev_name")
  done
fi

###############################################################################
# Template selection
###############################################################################
DEFAULT_TEMPLATE="${BASE_DIR}/derivatives/templates/MNI152_T1_2mm_brain.nii.gz"
echo -e "\nEnter template path or press Enter/Return for [$DEFAULT_TEMPLATE]:"
echo -ne "> "
read template_input
[ -n "$template_input" ] && TEMPLATE="$template_input" || TEMPLATE="$DEFAULT_TEMPLATE"
if [ ! -f "$TEMPLATE" ]; then
  echo "Error: Template $TEMPLATE does not exist."
  exit 1
fi

# Prompt for subjects
echo -e "\nEnter subject IDs (e.g., sub-01 sub-02), or press Enter/Return for all in $BASE_DIR:"
echo -ne "> "
read subjects_input
if [ -n "$subjects_input" ]; then
  SUBJECTS_ARRAY=($subjects_input)
else
  SUBJECTS_ARRAY=($(find "$BASE_DIR" -maxdepth 1 -mindepth 1 -type d -name "sub-*" | sed 's|.*/||'))
fi
IFS=$'\n' SUBJECTS_ARRAY=($(sort -V <<<"${SUBJECTS_ARRAY[*]}"))
unset IFS

###############################################################################
# Prompt for Subjects, Sessions, Runs
###############################################################################
# Determine if any sessions exist for the selected subjects
sessions_exist=false
for subj in "${SUBJECTS_ARRAY[@]}"; do
  if compgen -G "$BASE_DIR/$subj/ses-*" > /dev/null; then
    sessions_exist=true
    break
  fi
done

if [ "$sessions_exist" = true ]; then
  echo -e "\nEnter session IDs (e.g., ses-01 ses-02), or press Enter/Return for all sessions:"
  echo -ne "> "
  read sessions_input
else
  sessions_input=""
fi

# Prompt for runs
echo -e "\nEnter run numbers (e.g., 01 02), or press Enter/Return for all runs:"
echo -ne "> "
read runs_input

###############################################################################
# Helper Functions
###############################################################################
get_t1_image_path() {
  local subject=$1
  local session=$2
  local t1_image=""
  local ses_path=""
  local ses_label=""
  [ -n "$session" ] && { ses_path="/$session"; ses_label="_${session}"; }
  if [ "$skull_strip_choice" = "2" ]; then
    t1_image=$(find "${SYNTHSTRIP_DIR}/${subject}${ses_path}/anat" -type f -name "${subject}${ses_label}_*synthstrip*_brain.nii.gz" | head -n 1)
  else
    t1_image=$(find "${BET_DIR}/${subject}${ses_path}/anat" -type f -name "${subject}${ses_label}_*_brain.nii.gz" | head -n 1)
  fi
  echo "$t1_image"
}

# Helper: find bold
get_functional_image_path() {
  local subject=$1
  local session=$2
  local run=$3
  local func_image=""
  local found=false
  local ses_path=""
  local ses_label=""
  [ -n "$session" ] && { ses_path="/$session"; ses_label="_${session}"; }

  if [ "$fieldmap_corrected" = true ]; then
    func_image_paths=("${TOPUP_OUTPUT_BASE}/${subject}${ses_path}/func/${subject}${ses_label}_task-*_run-${run}_desc-topupcorrected_bold.nii.gz"
                      "${TOPUP_OUTPUT_BASE}/${subject}${ses_path}/func/${subject}${ses_label}_run-${run}_desc-topupcorrected_bold.nii.gz")
  else
    func_image_paths=("${BASE_DIR}/${subject}${ses_path}/func/${subject}${ses_label}_task-*_run-${run}_bold.nii.gz"
                      "${BASE_DIR}/${subject}${ses_path}/func/${subject}${ses_label}_run-${run}_bold.nii.gz")
  fi

  for potential_path in "${func_image_paths[@]}"; do
    for expanded_path in $(ls $potential_path 2>/dev/null); do
      if [[ "$expanded_path" == *"task-rest"* ]]; then
        continue
      fi
      func_image="$expanded_path"
      found=true
      break 2
    done
  done

  if [ "$found" = false ]; then
    echo ""
    return
  fi

  local task_in_filename=false
  if [[ "$func_image" == *"task-"* ]]; then
    task_in_filename=true
  fi
  echo "$func_image|$task_in_filename"
}

# Helper: slice timing
get_slice_timing_file_path() {
  local subject=$1
  local session=$2
  local run_label=$3
  local task_name=$4
  local slice_timing_file=""
  slice_timing_paths=()
  local ses_path=""
  local ses_label=""
  [ -n "$session" ] && { ses_path="/$session"; ses_label="_${session}"; }
  if [ -n "$task_name" ]; then
    slice_timing_paths+=("${SLICE_TIMING_DIR}/${subject}${ses_path}/func/${subject}${ses_label}_task-${task_name}_${run_label}_bold_slice_timing.txt")
  fi
  slice_timing_paths+=("${SLICE_TIMING_DIR}/${subject}${ses_path}/func/${subject}${ses_label}_${run_label}_bold_slice_timing.txt")

  for potential_path in "${slice_timing_paths[@]}"; do
    if [ -f "$potential_path" ]; then
      slice_timing_file="$potential_path"
      break
    fi
  done
  echo "$slice_timing_file"
}

# Helper: EV text files
get_ev_txt_files() {
  local subject=$1
  local session=$2
  local run_label=$3
  local ev_txt_files=()
  local ses_path=""
  local ses_label=""
  [ -n "$session" ] && { ses_path="/$session"; ses_label="_${session}"; }
  local txt_dir="${CUSTOM_EVENTS_DIR}/${subject}${ses_path}"
  for ev_name in "${EV_NAMES[@]}"; do
    local txt_file="${txt_dir}/${subject}${ses_label}_${run_label}_desc-${ev_name}_events.txt"
    if [ ! -f "$txt_file" ]; then
      return
    fi
    ev_txt_files+=("$txt_file")
  done
  echo "${ev_txt_files[@]}"
}

###############################################################################
# Main Processing Loop
###############################################################################
for subject in "${SUBJECTS_ARRAY[@]}"; do
  echo -e "\n=== PROCESSING SUBJECT: $subject ==="
  subject_has_sessions=false
  if compgen -G "$skull_strip_dir/$subject/ses-*" > /dev/null; then
    subject_has_sessions=true
  fi

  if [ "$subject_has_sessions" = true ]; then
    if [ -n "$sessions_input" ]; then
      SESSIONS_ARRAY=()
      for ses in $sessions_input; do
        [ -d "$skull_strip_dir/$subject/$ses" ] && SESSIONS_ARRAY+=("$ses")
      done
      if [ ${#SESSIONS_ARRAY[@]} -eq 0 ]; then
        echo "No sessions found for $subject."
        continue
      fi
    else
      SESSIONS_ARRAY=($(find "$skull_strip_dir/$subject" -maxdepth 1 -type d -name "ses-*" -exec basename {} \; 2>/dev/null))
    fi
    IFS=$'\n' SESSIONS_ARRAY=($(sort -V <<<"${SESSIONS_ARRAY[*]}")); unset IFS
  else
    SESSIONS_ARRAY=("")
  fi

  for session in "${SESSIONS_ARRAY[@]}"; do
    ses_path=""
    ses_label=""
    [ -n "$session" ] && { ses_path="/$session"; ses_label="_${session}"; }
    if [ -n "$runs_input" ]; then
      RUNS_ARRAY=($runs_input)
    else
      if [ "$fieldmap_corrected" = true ]; then
        if [ -n "$session" ]; then
          func_dir="${TOPUP_OUTPUT_BASE}/${subject}/${session}/func"
        else
          func_dir="${TOPUP_OUTPUT_BASE}/${subject}/func"
        fi
      else
        if [ -n "$session" ]; then
          func_dir="${BASE_DIR}/${subject}/${session}/func"
        else
          func_dir="${BASE_DIR}/${subject}/func"
        fi
      fi
      ses_label=""
      [ -n "$session" ] && ses_label="_${session}"
      RUNS_ARRAY=($(find "$func_dir" -type f -name "${subject}${ses_label}_task-*_run-*_bold.nii.gz" ! -name "*task-rest*_bold.nii.gz" 2>/dev/null | grep -o 'run-[0-9][0-9]*' | sed 's/run-//' | sort | uniq))
      if [ ${#RUNS_ARRAY[@]} -eq 0 ]; then
        RUNS_ARRAY=($(find "$func_dir" -type f -name "${subject}${ses_label}_run-*_bold.nii.gz" ! -name "*task-rest*_bold.nii.gz" 2>/dev/null | grep -o 'run-[0-9][0-9]*' | sed 's/run-//' | sort | uniq))
      fi
    fi
    if [ ${#RUNS_ARRAY[@]} -eq 0 ]; then
      if [ -n "$session" ]; then
        echo "No task-based runs found for $subject $session."
      else
        echo "No task-based runs found for $subject."
      fi
      continue
    fi
    IFS=$'\n' RUNS_ARRAY=($(sort -V <<<"${RUNS_ARRAY[*]}"))
    unset IFS

    for run in "${RUNS_ARRAY[@]}"; do
      run_label="run-${run}"
      if [ -n "$session" ]; then
        echo -e "\n--- SESSION: $session | RUN: $run_label ---"
      else
        echo -e "\n--- RUN: $run_label ---"
      fi
      t1_image=$(get_t1_image_path "$subject" "$session")
      if [ -z "$t1_image" ]; then
        echo "T1 image not found. Skipping run."
        continue
      fi

      func_image_and_task_flag=$(get_functional_image_path "$subject" "$session" "$run")
      func_image=$(echo "$func_image_and_task_flag" | cut -d '|' -f 1)
      task_in_filename=$(echo "$func_image_and_task_flag" | cut -d '|' -f 2)
      if [ -z "$func_image" ]; then
        echo "Functional image not found. Skipping."
        continue
      fi

      if [ "$task_in_filename" = "true" ]; then
        task_name=$(basename "$func_image" | grep -o 'task-[^_]*' | sed 's/task-//')
        [ "$task_name" = "rest" ] && { echo "Skipping rest task."; continue; }
      else
        task_name=""
      fi

      # EV files (if needed)
      EV_TXT_FILES=()
      if [ "$prompt_for_evs" = true ]; then
        ev_txt_files=($(get_ev_txt_files "$subject" "$session" "$run_label"))
        if [ "${#ev_txt_files[@]}" -ne "$num_evs" ]; then
          echo "EV files missing. Skipping run."
          continue
        fi
        EV_TXT_FILES=("${ev_txt_files[@]}")
      fi

      # slice timing
      use_slice_timing=false
      slice_timing_file=""
      if [ "$slice_timing_correction" = true ]; then
        slice_timing_file=$(get_slice_timing_file_path "$subject" "$session" "$run_label" "$task_name")
        [ -n "$slice_timing_file" ] && use_slice_timing=true
      fi

      # Build run_feat_analysis.sh command
      cmd="${BASE_DIR}/code/scripts/run_feat_analysis.sh"
      if [ "$ica_aroma" = true ]; then
        cmd+=" --preproc-design-file \"$preproc_design_file\""
        cmd+=" --t1-image \"$t1_image\" --func-image \"$func_image\" --template \"$TEMPLATE\" --ica-aroma"
        [ "$nonlinear_reg" = true ] && cmd+=" --nonlinear-reg"
        [ "$use_bbr" = true ] && cmd+=" --use-bbr"
        [ "$apply_nuisance_regression" = true ] && cmd+=" --apply-nuisance-reg"
        cmd+=" --subject \"$subject\""
        [ -n "$session" ] && cmd+=" --session \"$session\""
        [ -n "$task_name" ] && cmd+=" --task \"$task_name\""
        cmd+=" --run \"$run_label\""
        [ "$use_slice_timing" = true ] && cmd+=" --slice-timing-file \"$slice_timing_file\""
        [ "$highpass_filtering" = true ] && cmd+=" --highpass-cutoff \"$highpass_cutoff\""

        if [ "$apply_aroma_stats" = false ]; then
          # Preproc only
          if [ -n "$task_name" ]; then
            preproc_output_dir="${BASE_DIR}/${PREPROC_PARENT_DIR}/${subject}${ses_path}/func/${subject}${ses_label}_task-${task_name}_${run_label}.feat"
          else
            preproc_output_dir="${BASE_DIR}/${PREPROC_PARENT_DIR}/${subject}${ses_path}/func/${subject}${ses_label}_${run_label}.feat"
          fi
          cmd+=" --preproc-output-dir \"$preproc_output_dir\""
          echo -e "\n--- FEAT Preprocessing (ICA-AROMA only) ---"
          echo "$cmd"
          eval "$cmd"
        else
          # Preproc + stats
          if [ -n "$task_name" ]; then
            preproc_output_dir="${BASE_DIR}/${PREPROC_PARENT_DIR}/${subject}${ses_path}/func/${subject}${ses_label}_task-${task_name}_${run_label}.feat"
            analysis_output_dir="${BASE_DIR}/${ANALYSIS_POSTICA_PARENT_DIR}/${subject}${ses_path}/func/${subject}${ses_label}_task-${task_name}_${run_label}.feat"
          else
            preproc_output_dir="${BASE_DIR}/${PREPROC_PARENT_DIR}/${subject}${ses_path}/func/${subject}${ses_label}_${run_label}.feat"
            analysis_output_dir="${BASE_DIR}/${ANALYSIS_POSTICA_PARENT_DIR}/${subject}${ses_path}/func/${subject}${ses_label}_${run_label}.feat"
          fi
          cmd+=" --preproc-output-dir \"$preproc_output_dir\" --analysis-output-dir \"$analysis_output_dir\""
          cmd+=" --design-file \"$design_file\""
          for ((i=0; i<num_evs; i++)); do
            cmd+=" --ev$((i+1)) \"${EV_TXT_FILES[$i]}\""
          done
          echo -e "\n--- FEAT Preprocessing + Main Analysis (ICA-AROMA) ---"
          echo "$cmd"
          eval "$cmd"
        fi
      else
        # Non-ICA-AROMA
        if [ -n "$task_name" ]; then
          output_dir="${BASE_DIR}/${ANALYSIS_PARENT_DIR}/${subject}${ses_path}/func/${subject}${ses_label}_task-${task_name}_${run_label}.feat"
        else
          output_dir="${BASE_DIR}/${ANALYSIS_PARENT_DIR}/${subject}${ses_path}/func/${subject}${ses_label}_${run_label}.feat"
        fi
        cmd+=" --design-file \"$design_file\""
        cmd+=" --t1-image \"$t1_image\" --func-image \"$func_image\" --template \"$TEMPLATE\""
        cmd+=" --output-dir \"$output_dir\""
        [ "$use_bbr" = true ] && cmd+=" --use-bbr"
        [ "$nonlinear_reg" = true ] && cmd+=" --nonlinear-reg"
        for ((i=0; i<num_evs; i++)); do
          cmd+=" --ev$((i+1)) \"${EV_TXT_FILES[$i]}\""
        done
        cmd+=" --subject \"$subject\""
        [ -n "$session" ] && cmd+=" --session \"$session\""
        [ -n "$task_name" ] && cmd+=" --task \"$task_name\""
        cmd+=" --run \"$run_label\""
        [ "$use_slice_timing" = true ] && cmd+=" --slice-timing-file \"$slice_timing_file\""
        [ "$highpass_filtering" = true ] && cmd+=" --highpass-cutoff \"$highpass_cutoff\""

        echo -e "\n--- FEAT Main Analysis ---"
        echo "$cmd"
        eval "$cmd"
      fi
    done
  done
done

echo "FEAT FSL level 1 analysis setup complete." >> "$LOG_FILE"
echo "Base Directory: $BASE_DIR" >> "$LOG_FILE"
echo "Skull-stripped Directory: $skull_strip_dir" >> "$LOG_FILE"
echo "Field Map Corrected Directory: $TOPUP_OUTPUT_BASE" >> "$LOG_FILE"
echo "ICA-AROMA Directory: $ICA_AROMA_DIR" >> "$LOG_FILE"
echo "Log File: $LOG_FILE" >> "$LOG_FILE"
