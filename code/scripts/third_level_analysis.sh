#!/bin/bash
###############################################################################
# third_level_analysis.sh
#
# Purpose:
#   Perform mixed-effects (third-level) FEAT analysis using OLS or FLAME.
#   Can run interactively or via command-line flags.
#
# Usage:
#   third_level_analysis.sh [options]
#
# Usage Examples:
#   ./third_level_analysis.sh \
#       --analysis-dir "/path/to/level-2" \
#       --session "ses-01" \
#       --subjects "sub-001 sub-002" \
#       --mixed-effects FLAME1 \
#       --z-thresh 2.3 \
#       --cluster-p-thresh 0.05
#
# Options:
#   --analysis-dir DIR   Level-2 directory
#   --session SES        Session label
#   --subjects LIST      Space separated subject IDs
#   --mixed-effects TYPE OLS|FLAME1|FLAME1plus2
#   --z-thresh VALUE     Z threshold
#   --cluster-p-thresh V Cluster p threshold
#   --robust             Enable robust estimation
#   --task-name NAME     Optional task label
#   --desc DESC          Optional description
#   --help               Show help
#
# Requirements:
#   FSL and yq; create_dataset_description.sh available
#
# Notes:
#   Outputs go to derivatives/fsl/level-3 with names reflecting analysis options.
#   Common cope numbers across input directories are identified, and FEAT is
#   run for each cope.
#
###############################################################################

# ------------------------------------------------------------------------------
# tcl_escape
#
# Purpose:
#   Escapes characters that can confuse Tcl’s parser.
#
# Description:
#   Reads from stdin and uses sed to replace backslashes, quotes, dollar signs,
#   braces, brackets, parentheses, asterisks, semicolons, and ampersands with
#   their escaped versions.
# ------------------------------------------------------------------------------
tcl_escape() {
  sed -E \
    -e 's/\\/\\\\/g' \
    -e 's/"/\\"/g' \
    -e 's/\$/\\\$/g' \
    -e 's/\{/\\\{/g' \
    -e 's/\}/\\\}/g' \
    -e 's/\[/\\\[/g' \
    -e 's/\]/\\\]/g' \
    -e 's/\(/\\\(/g' \
    -e 's/\)/\\\)/g' \
    -e 's/\*/\\\*/g' \
    -e 's/\;/\\\;/g' \
    -e 's/\&/\\\&/g'
}

# ------------------------------------------------------------------------------
# gather_cope_numbers
#
# Purpose:
#   Gathers cope numbers from lower-level or higher-level FEAT directories.
#
# Usage:
#   gather_cope_numbers <dir> <dir_type>
#     dir_type = "lower" or "higher"
#
#   If dir_type == "lower", searches for cope*.nii.gz in <dir>/stats.
#   If dir_type == "higher", searches for subdirectories named cope*.feat in <dir>.
#
# Returns:
#   Echos a space-separated list of unique numeric cope indices.
# ------------------------------------------------------------------------------
gather_cope_numbers() {
    local input_dir="$1"
    local dir_type="$2"
    local -a result=()

    if [ "$dir_type" == "lower" ]; then
        local cope_files=($(find "$input_dir/stats" -maxdepth 1 -name "cope*.nii.gz" 2>/dev/null))
        for cfile in "${cope_files[@]}"; do
            local fname="$(basename "$cfile")"
            if [[ "$fname" =~ ^cope([0-9]+)\.nii\.gz$ ]]; then
                result+=("${BASH_REMATCH[1]}")
            fi
        done
    else
        local cope_dirs=($(find "$input_dir" -maxdepth 1 -type d -name "cope*.feat" 2>/dev/null))
        for cdir in "${cope_dirs[@]}"; do
            local bname="$(basename "$cdir")"
            if [[ "$bname" =~ ^cope([0-9]+)\.feat$ ]]; then
                result+=("${BASH_REMATCH[1]}")
            fi
        done
    fi

    if [ ${#result[@]} -gt 0 ]; then
        result=($(printf "%s\n" "${result[@]}" | sort -n | uniq))
    fi

    echo "${result[*]}"
}

# ------------------------------------------------------------------------------
# find_common_copes
#
# Purpose:
#   Finds the intersection of cope numbers across multiple space-separated lists.
#
# Usage:
#   find_common_copes <list1> <list2> ... <listN>
#     Each argument is a space-separated string of cope numbers.
#
# Returns:
#   Echos the space-separated intersection of cope numbers.
# ------------------------------------------------------------------------------
find_common_copes() {
    local -a all_args=("$@")
    local -a common=()
    local is_first=true

    for arg in "${all_args[@]}"; do
        IFS=' ' read -ra this_cope_array <<< "$arg"
        if $is_first; then
            common=("${this_cope_array[@]}")
            is_first=false
        else
            local -a new_common=()
            for cval in "${common[@]}"; do
                for cc in "${this_cope_array[@]}"; do
                    if [ "$cval" == "$cc" ]; then
                        new_common+=("$cval")
                        break
                    fi
                done
            done
            new_common=($(printf "%s\n" "${new_common[@]}" | sort -n | uniq))
            common=("${new_common[@]}")
        fi

        [ ${#common[@]} -eq 0 ] && break
    done

    echo "${common[*]}"
}

# ------------------------------------------------------------------------------
# run_third_level_feat
#
# Purpose:
#   Runs a third-level FEAT analysis for a single cope using a design file template.
#
# Usage:
#   run_third_level_feat \
#       <cope_num> \
#       <output_dir> \
#       <design_template> \
#       <z_threshold> \
#       <cluster_p_threshold> \
#       <standard_image> \
#       <fmri_mixed> \
#       <fmri_robust> \
#       <num_inputs> \
#       <input_lines> \
#       <ev_values> \
#       <group_membership>
#
# Description:
#   Creates a temporary .fsf file from the design template, appends lines for
#   feat_files, EVs, and group membership, then runs FEAT. The temporary design
#   file is removed upon completion.
# ------------------------------------------------------------------------------
run_third_level_feat() {
  local cope_num="$1"
  local output_dir="$2"
  local design_template="$3"
  local z_threshold="$4"
  local cluster_p_threshold="$5"
  local standard_image="$6"
  local fmri_mixed="$7"
  local fmri_robust="$8"
  local num_inputs="$9"
  shift
  local input_lines="$9"
  shift
  local ev_values="$9"
  shift
  local group_membership="$9"

  local cope_output_dir="${output_dir}/cope${cope_num}"

  if [ -d "${cope_output_dir}.gfeat" ]; then
    echo "[Skipping] Output directory already exists for cope${cope_num}: ${cope_output_dir}.gfeat"
    return 0
  fi

  mkdir -p "$output_dir"

  export COPE_OUTPUT_DIR="$cope_output_dir"
  export Z_THRESHOLD="$z_threshold"
  export CLUSTER_P_THRESHOLD="$cluster_p_threshold"
  export STANDARD_IMAGE="$standard_image"
  export NUM_INPUTS="$num_inputs"
  export MIXED_YN="$fmri_mixed"
  export ROBUST_YN="$fmri_robust"

  local temp_design_file="${cope_output_dir}_design.fsf"

  if [ ! -f "$design_template" ]; then
      echo "Error: Design template file not found at $design_template"
      return 1
  fi

  envsubst < "$design_template" > "$temp_design_file"

  {
    echo -e "$input_lines"
    echo -e "$ev_values"
    echo -e "$group_membership"
  } >> "$temp_design_file"

  feat "$temp_design_file"

  rm -f "$temp_design_file"
  return 0
}

# ------------------------------------------------------------------------------
# create_dataset_description_json
#
# Purpose:
#   Creates or updates dataset_description.json with analysis details.
#
# Usage:
#   create_dataset_description_json \
#       "<OUTPUT_DIR>" \
#       "<CONFIG_FILE>" \
#       "<mixed_label>" \
#       "<z_threshold>" \
#       "<cluster_p_threshold>" \
#       "<fmri_robust>" \
#       "<bids_version>" \
#       "<log_file>"
#
# Description:
#   Reads optional fields from config_file (via yq), populates a set of
#   arguments for create_dataset_description.sh, and invokes that script if
#   present.
# ------------------------------------------------------------------------------
create_dataset_description_json() {
  local output_dir="$1"
  local config_file="$2"
  local mixed_label="$3"
  local z_threshold="$4"
  local cluster_p_threshold="$5"
  local fmri_robust="$6"
  local bids_version="$7"
  local log_file="$8"

  local FSL_VERSION="Unknown"
  if [ -n "$FSLDIR" ] && [ -f "$FSLDIR/etc/fslversion" ]; then
      FSL_VERSION=$(cut -d'%' -f1 < "$FSLDIR/etc/fslversion")
  fi

  local ds_name=""
  local ds_type=""
  local ds_description=""
  local -a ds_generatedby=()

  if command -v yq &>/dev/null && [ -f "$config_file" ]; then
    local approach_key
    case "$(echo "$mixed_label" | tr '[:upper:]' '[:lower:]')" in
      "ols") approach_key="ols" ;;
      "flame1") approach_key="flame1" ;;
      "flame1plus2") approach_key="flame1plus2" ;;
      *) approach_key="" ;;
    esac

    if [ -n "$approach_key" ]; then
      local y_name y_type y_desc
      y_name="$(yq e ".dataset_descriptions.level-3.${approach_key}.name" "$config_file")"
      y_type="$(yq e ".dataset_descriptions.level-3.${approach_key}.dataset_type" "$config_file")"
      y_desc="$(yq e ".dataset_descriptions.level-3.${approach_key}.description" "$config_file")"

      [ "$y_name" != "null" ] && [ -n "$y_name" ] && ds_name="$y_name"
      [ "$y_type" != "null" ] && [ -n "$y_type" ] && ds_type="$y_type"
      [ "$y_desc" != "null" ] && [ -n "$y_desc" ] && ds_description="$y_desc"

      local count_generatedby
      count_generatedby="$(yq e ".dataset_descriptions.level-3.${approach_key}.generatedby | length" "$config_file" 2>/dev/null)"
      [[ "$count_generatedby" == "null" ]] && count_generatedby=0

      local i
      for ((i=0; i<"$count_generatedby"; i++)); do
        local gb_name gb_version gb_desc
        gb_name="$(yq e ".dataset_descriptions.level-3.${approach_key}.generatedby[$i].name" "$config_file")"
        gb_version="$(yq e ".dataset_descriptions.level-3.${approach_key}.generatedby[$i].version" "$config_file")"
        gb_desc="$(yq e ".dataset_descriptions.level-3.${approach_key}.generatedby[$i].description" "$config_file")"

        if [ "$gb_name" == "FSL" ] && ( [ "$gb_version" == "null" ] || [ -z "$gb_version" ] ); then
          gb_version="$FSL_VERSION"
        fi

        local gb_string="Name=$gb_name"
        [ "$gb_version" != "null" ] && [ -n "$gb_version" ] && gb_string+=",Version=$gb_version"
        [ "$gb_desc" != "null" ] && [ -n "$gb_desc" ] && gb_string+=",Description=$gb_desc"

        ds_generatedby+=("$gb_string")
      done
    fi
  fi

  local appended_params="(Modelling=${mixed_label}, Z-threshold=${z_threshold}, ClusterP=${cluster_p_threshold}, RobustOutlier=$([ "$fmri_robust" == "1" ] && echo 'Enabled' || echo 'Disabled'))"
  if [ -n "$ds_description" ]; then
    ds_description="${ds_description} ${appended_params}"
  else
    ds_description="${appended_params}"
  fi

  local -a desc_script_args=("--analysis-dir" "$output_dir")
  [ -n "$ds_name" ]        && desc_script_args+=(--ds-name "$ds_name")
  [ -n "$ds_type" ]        && desc_script_args+=(--dataset-type "$ds_type")
  [ -n "$ds_description" ] && desc_script_args+=(--description "$ds_description")
  [ -n "$bids_version" ]   && desc_script_args+=(--bids-version "$bids_version")

  for gb in "${ds_generatedby[@]}"; do
    desc_script_args+=(--generatedby "$gb")
  done

  if [ -f "$CREATE_DS_DESC_SCRIPT" ]; then
    "$CREATE_DS_DESC_SCRIPT" "${desc_script_args[@]}"
  else
    echo "[Notice] create_dataset_description.sh not found; skipping JSON creation." >> "$log_file"
  fi
}

# Initial settings
script_dir="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(dirname "$(dirname "$script_dir")")"

CONFIG_FILE="$BASE_DIR/code/config/config.yaml"
CREATE_DS_DESC_SCRIPT="$BASE_DIR/code/scripts/create_dataset_description.sh"

# Default paths
LEVEL_1_ANALYSIS_BASE_DIR="$BASE_DIR/derivatives/fsl/level-1"
LEVEL_2_ANALYSIS_BASE_DIR="$BASE_DIR/derivatives/fsl/level-2"
LEVEL_3_ANALYSIS_BASE_DIR="$BASE_DIR/derivatives/fsl/level-3"

LOG_DIR="$BASE_DIR/code/logs"
mkdir -p "$LOG_DIR"
LOGFILE="$LOG_DIR/$(basename "$0" .sh)_$(date +'%Y%m%d_%H%M%S').log"

# Reading config.yaml for output directory overrides
if [ -f "$CONFIG_FILE" ] && command -v yq &>/dev/null; then
  # Attempt to read a custom level-2 path
  L2_FROM_CONFIG="$(yq e '.level-2.fixed_effects_output_dir' "$CONFIG_FILE" 2>/dev/null)"
  if [ "$L2_FROM_CONFIG" != "null" ] && [ -n "$L2_FROM_CONFIG" ]; then
    LEVEL_2_ANALYSIS_BASE_DIR="$BASE_DIR/$L2_FROM_CONFIG"
  fi

  # Attempt to read a custom level-3 path
  L3_FROM_CONFIG="$(yq e '.level-3.higher_level_output_dir' "$CONFIG_FILE" 2>/dev/null)"
  if [ "$L3_FROM_CONFIG" != "null" ] && [ -n "$L3_FROM_CONFIG" ]; then
    LEVEL_3_ANALYSIS_BASE_DIR="$BASE_DIR/$L3_FROM_CONFIG"
  fi
fi

exec > >(tee -a "$LOGFILE") 2>&1

if ! command -v yq &> /dev/null; then
    echo "[Warning] 'yq' is required to parse $CONFIG_FILE but was not found in PATH. Some config fields may not load."
fi

BIDS_VERSION_FALLBACK="1.10.0"
if [ -f "$CONFIG_FILE" ] && command -v yq &> /dev/null; then
    BIDS_VERSION="$(yq e '.bids_version' "$CONFIG_FILE")"
    if [ "$BIDS_VERSION" == "null" ] || [ -z "$BIDS_VERSION" ]; then
        BIDS_VERSION="$BIDS_VERSION_FALLBACK"
    fi
else
    BIDS_VERSION="$BIDS_VERSION_FALLBACK"
fi

usage() {
  cat <<EOM
Usage: $(basename "$0") [OPTIONS]

Third-level analysis script with both interactive and non-interactive modes.

Options (non-interactive):
  --analysis-dir <path>      : Path to the second-level directory containing .gfeat directories
  --session <str>            : Which session to analyze (e.g., "ses-01")
  --subjects <"sub-...">     : Space-separated list of subjects or wildcard (e.g., "sub-*")
  --mixed-effects <OLS|FLAME1|FLAME1plus2>
                              : Which higher-level modeling approach to use
  --z-thresh <float>         : Z threshold (e.g. 2.3)
  --cluster-p-thresh <float> : Cluster P threshold (e.g. 0.05)
  --robust                   : If included, robust outlier detection is enabled
  --task-name <str>          : Optional custom "task-<str>" for output folder naming
  --desc <str>               : Optional "desc-<str>" for output folder naming
  --help                     : Show this help message and exit

If no recognized arguments are supplied, the script runs interactively with
prompt-based inputs.

Examples:
  1) Non-interactive:
     ./third_level_analysis.sh --analysis-dir "/path/to/level-2" --session "ses-01" \\
       --subjects "sub-001 sub-002" --mixed-effects "FLAME1" --z-thresh 2.3 \\
       --cluster-p-thresh 0.05 --robust

  2) Interactive:
     ./third_level_analysis.sh
EOM
  exit 1
}

analysis_dir_arg=""
session_arg=""
subjects_arg=""
mixed_arg=""
z_thresh_arg=""
cluster_p_arg=""
robust_arg=false
task_name_arg=""
desc_arg=""

used_cli_flags=false

while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        --analysis-dir)
            analysis_dir_arg="$2"
            used_cli_flags=true
            shift; shift
            ;;
        --session)
            session_arg="$2"
            used_cli_flags=true
            shift; shift
            ;;
        --subjects)
            subjects_arg="$2"
            used_cli_flags=true
            shift; shift
            ;;
        --mixed-effects)
            mixed_arg="$2"
            used_cli_flags=true
            shift; shift
            ;;
        --z-thresh)
            z_thresh_arg="$2"
            used_cli_flags=true
            shift; shift
            ;;
        --cluster-p-thresh)
            cluster_p_arg="$2"
            used_cli_flags=true
            shift; shift
            ;;
        --robust)
            robust_arg=true
            used_cli_flags=true
            shift
            ;;
        --task-name)
            task_name_arg="$2"
            used_cli_flags=true
            shift; shift
            ;;
        --desc)
            desc_arg="$2"
            used_cli_flags=true
            shift; shift
            ;;
        --help)
            usage
            ;;
        *)
            echo "Unrecognized argument: $1"
            usage
            ;;
    esac
done

# ------------------------------------------------------------------
# 1) If no flags: Interactive Mode
# ------------------------------------------------------------------
if [ "$used_cli_flags" = false ]; then
    echo "[Info] No command-line flags provided => Running in interactive mode." >> $LOGFILE

    script_dir="$(cd "$(dirname "$0")" && pwd)"
    BASE_DIR="$(dirname "$(dirname "$script_dir")")"

    LOG_DIR="$BASE_DIR/code/logs"
    mkdir -p "$LOG_DIR"
    LOGFILE="$LOG_DIR/$(basename "$0" .sh)_$(date +'%Y%m%d_%H%M%S').log"

    exec > >(tee -a "$LOGFILE") 2>&1

    # These directories might be overridden by config.yaml read above
    LEVEL_1_ANALYSIS_BASE_DIR="$LEVEL_1_ANALYSIS_BASE_DIR"
    LEVEL_2_ANALYSIS_BASE_DIR="$LEVEL_2_ANALYSIS_BASE_DIR"
    LEVEL_3_ANALYSIS_BASE_DIR="$LEVEL_3_ANALYSIS_BASE_DIR"

    find_lower_level_analysis_dirs() {
        local base_dir="$1"
        ANALYSIS_DIRS=()
        while IFS= read -r -d $'\0' dir; do
            if find "$dir" -type d -name "*.feat" -print -quit | grep -q .; then
                ANALYSIS_DIRS+=("$dir")
            fi
        done < <(find "$base_dir" -mindepth 1 -maxdepth 1 -type d -print0)
    }

    find_higher_level_analysis_dirs() {
        local base_dir="$1"
        ANALYSIS_DIRS=()
        while IFS= read -r -d $'\0' dir; do
            if find "$dir" -type d -name "*.gfeat" -print -quit | grep -q .; then
                ANALYSIS_DIRS+=("$dir")
            fi
        done < <(find "$base_dir" -mindepth 1 -maxdepth 1 -type d -print0)
    }

    display_selections() {
        clear
        echo -e "\n=== Confirm Your Selections for Mixed Effects Analysis ==="
        session_label="$SESSION"
        [ -z "$session_label" ] && session_label="None"
        echo "Session: $session_label"
        echo

        sorted_subjects=($(printf "%s\n" "${subjects[@]}" | sort))

        for subject in "${sorted_subjects[@]}"; do
            for idx in "${!subjects[@]}"; do
                if [ "${subjects[$idx]}" == "$subject" ]; then
                    directories_str="${directories[$idx]}"
                    directory_types_str="${directory_types[$idx]}"
                    session="${sessions[$idx]}"
                    break
                fi
            done

            IFS='::' read -ra directories_list <<< "$directories_str"
            IFS='::' read -ra directory_types_list <<< "$directory_types_str"

            [ -z "$session" ] && session_display="None" || session_display="$session"
            echo "Subject: $subject | Session: $session_display"
            echo "----------------------------------------"

            for idx2 in "${!directories_list[@]}"; do
                dir="${directories_list[$idx2]}"
                dir_type="${directory_types_list[$idx2]}"

                if [ "$dir_type" == "lower" ]; then
                    echo "Selected Feat Directory:"
                else
                    echo "Higher-level Feat Directory:"
                fi

                echo "  - ${dir#$BASE_DIR/}"
            done
            echo
        done

        echo "============================================"
        echo
        echo "Options:"
        echo "  • To exclude subjects, type '-' followed by subject IDs separated by spaces (e.g., '- sub-01 sub-02')."
        echo "  • To edit (add new or replace existing) directories for a specific subject, type 'edit'."
        echo "  • Press Enter/Return to confirm and proceed with third-level mixed effects analysis if the selections are final."
        echo
        read -p "> " user_input
    }

    echo -e "\n=== Third Level Analysis  ==="

    find_higher_level_analysis_dirs "$LEVEL_2_ANALYSIS_BASE_DIR"
    if [ ${#ANALYSIS_DIRS[@]} -eq 0 ]; then
        echo -e "\nNo available directories for higher-level analysis found."
        echo "Please ensure that second-level fixed-effects analysis has been completed and the directories exist."
        echo -e "Exiting...\n"
        exit 1
    fi

    INPUT_TYPE="higher"
    ANALYSIS_BASE_DIR="$LEVEL_2_ANALYSIS_BASE_DIR"
    echo -e "\n---- Higher level FEAT directories ----"
    echo "Select analysis directory containing 3D cope images"
    echo

    ANALYSIS_DIR_OPTIONS=()
    for idx in "${!ANALYSIS_DIRS[@]}"; do
        echo "$((idx + 1))) ${ANALYSIS_DIRS[$idx]#$BASE_DIR/}"
        ANALYSIS_DIR_OPTIONS+=("$((idx + 1))")
    done

    echo ""
    read -p "Please enter your choice: " analysis_choice

    while ! [[ "$analysis_choice" =~ ^[0-9]+$ ]] || (( analysis_choice < 1 || analysis_choice > ${#ANALYSIS_DIRS[@]} )); do
        echo "Invalid selection. Please try again."
        read -p "Please enter your choice: " analysis_choice
    done

    ANALYSIS_DIR="${ANALYSIS_DIRS[$((analysis_choice - 1))]}"
    echo -e "\nYou have selected the following analysis directory:"
    echo "$ANALYSIS_DIR"

    SESSION_NAME_PATTERNS=("ses-*" "session-*" "ses_*" "session_*" "ses*" "session*" "baseline" "endpoint" "ses-001" "ses-002")
    FIND_SESSION_EXPR=()
    first_session_pattern=true
    for pattern in "${SESSION_NAME_PATTERNS[@]}"; do
        if $first_session_pattern; then
            FIND_SESSION_EXPR+=( -name "$pattern" )
            first_session_pattern=false
        else
            FIND_SESSION_EXPR+=( -o -name "$pattern" )
        fi
    done

    session_dirs=($(find "$ANALYSIS_DIR" -type d \( "${FIND_SESSION_EXPR[@]}" \)))
    session_dirs=($(printf "%s\n" "${session_dirs[@]}" | sort))

    session_names=()
    for session_dir in "${session_dirs[@]}"; do
        session_name=$(basename "$session_dir")
        if [[ ! " ${session_names[@]} " =~ " ${session_name} " ]]; then
            session_names+=("$session_name")
        fi
    done

    if [ ${#session_names[@]} -eq 0 ]; then
        SESSION=""
        echo "No sessions found in $ANALYSIS_DIR. Proceeding without sessions."
    else
        echo -e "\n--- Select session ---"
        echo "Higher level FEAT directories"
        echo -e "\nSelect available sessions:\n"
        SESSION_OPTIONS=()
        for idx in "${!session_names[@]}"; do
            echo "$((idx + 1))) ${session_names[$idx]}"
            SESSION_OPTIONS+=("$((idx + 1))")
        done

        echo ""
        read -p "Please enter your choice: " session_choice
        while ! [[ "$session_choice" =~ ^[0-9]+$ ]] || (( session_choice < 1 || session_choice > ${#session_names[@]} )); do
            echo "Invalid selection. Please try again."
            read -p "Please enter your choice: " session_choice
        done

        SESSION="${session_names[$((session_choice - 1))]}"
        echo -e "\nYou have selected session: $SESSION"
    fi

    subjects=()
    directories=()
    directory_types=()
    sessions=()

    SUBJECT_NAME_PATTERNS=("sub-*" "subject-*" "pilot-*" "subj-*" "subjpilot-*")
    FIND_SUBJECT_EXPR=()
    first_pattern=true
    for pattern in "${SUBJECT_NAME_PATTERNS[@]}"; do
        if $first_pattern; then
            FIND_SUBJECT_EXPR+=( -name "$pattern" )
            first_pattern=false
        else
            FIND_SUBJECT_EXPR+=( -o -name "$pattern" )
        fi
    done

    subject_dirs=($(find "$ANALYSIS_DIR" -mindepth 1 -maxdepth 1 -type d \( "${FIND_SUBJECT_EXPR[@]}" \)))
    subject_dirs=($(printf "%s\n" "${subject_dirs[@]}" | sort))

    if [ ${#subject_dirs[@]} -eq 0 ]; then
        echo "No subject directories found in $ANALYSIS_DIR."
        exit 1
    fi

    for subject_dir in "${subject_dirs[@]}"; do
        subject=$(basename "$subject_dir")

        directories_list=()
        directory_types_list=()
        subject_session="${SESSION}"

        search_dir=""
        if [ -n "$SESSION" ] && [ -d "$subject_dir/$SESSION" ]; then
            search_dir="$subject_dir/$SESSION"
        else
            search_dir="$subject_dir"
            subject_session=""
        fi

        gfeat_dirs=($(find "$search_dir" -mindepth 1 -maxdepth 1 -type d -name "*.gfeat"))
        gfeat_dirs=($(printf "%s\n" "${gfeat_dirs[@]}" | sort))
        [ ${#gfeat_dirs[@]} -eq 0 ] && continue

        directories_list+=("${gfeat_dirs[@]}")
        for ((i=0; i<${#gfeat_dirs[@]}; i++)); do
            directory_types_list+=("higher")
        done

        directories_list_filtered=()
        directory_types_list_filtered=()
        for idx2 in "${!directories_list[@]}"; do
            dir="${directories_list[$idx2]}"
            if [ -n "$dir" ]; then
                directories_list_filtered+=("$dir")
                directory_types_list_filtered+=("${directory_types_list[$idx2]}")
            fi
        done

        if [ ${#directories_list_filtered[@]} -gt 0 ]; then
            subjects+=("$subject")
            directories_str=$(printf "::%s" "${directories_list_filtered[@]}")
            directories_str="${directories_str:2}"
            directories+=("$directories_str")

            directory_types_str=$(printf "::%s" "${directory_types_list_filtered[@]}")
            directory_types_str="${directory_types_str:2}"
            directory_types+=("$directory_types_str")

            sessions+=("$subject_session")
        fi
    done

    while true; do
        display_selections

        lower_input=$(echo "$user_input" | tr '[:upper:]' '[:lower:]')

        if [ -z "$user_input" ]; then
            clear
            break
        elif [[ "$lower_input" == "edit" ]]; then
            echo -e "\nSelect input options:\n"
            echo "1) Inputs are lower-level FEAT directories"
            echo "2) Inputs are higher-level .gfeat directories"
            echo "3) Cancel"
            echo ""
            read -p "Please enter your choice: " edit_choice
            while ! [[ "$edit_choice" =~ ^[0-9]+$ ]] || (( edit_choice < 1 || edit_choice > 3 )); do
                echo "Invalid selection. Please try again."
                read -p "Please enter your choice: " edit_choice
            done

            if [ "$edit_choice" == "3" ]; then
                continue
            elif [ "$edit_choice" == "1" ]; then
                ADD_INPUT_TYPE="lower"
                ADD_ANALYSIS_BASE_DIR="$LEVEL_1_ANALYSIS_BASE_DIR"
            else
                ADD_INPUT_TYPE="higher"
                ADD_ANALYSIS_BASE_DIR="$LEVEL_2_ANALYSIS_BASE_DIR"
            fi

            if [ "$ADD_INPUT_TYPE" == "lower" ]; then
                find_lower_level_analysis_dirs "$ADD_ANALYSIS_BASE_DIR"
            else
                find_higher_level_analysis_dirs "$ADD_ANALYSIS_BASE_DIR"
            fi

            if [ ${#ANALYSIS_DIRS[@]} -eq 0 ]; then
                echo "No analysis directories found."
                continue
            fi

            echo
            ANALYSIS_DIR_OPTIONS=()
            for idx in "${!ANALYSIS_DIRS[@]}"; do
                echo "$((idx + 1))) ${ANALYSIS_DIRS[$idx]#$BASE_DIR/}"
                ANALYSIS_DIR_OPTIONS+=("$((idx + 1))")
            done

            echo ""
            read -p "Please enter your choice: " analysis_choice
            while ! [[ "$analysis_choice" =~ ^[0-9]+$ ]] || (( analysis_choice < 1 || analysis_choice > ${#ANALYSIS_DIRS[@]} )); do
                echo "Invalid selection. Please try again."
                read -p "Please enter your choice: " analysis_choice
            done

            ADD_ANALYSIS_DIR="${ANALYSIS_DIRS[$((analysis_choice - 1))]}"
            echo -e "\nYou have selected the following analysis directory:"
            echo "$ADD_ANALYSIS_DIR"

            session_dirs=($(find "$ADD_ANALYSIS_DIR" -type d \( "${FIND_SESSION_EXPR[@]}" \)))
            session_dirs=($(printf "%s\n" "${session_dirs[@]}" | sort))

            session_names=()
            for session_dir in "${session_dirs[@]}"; do
                session_name=$(basename "$session_dir")
                [[ " ${session_names[@]} " =~ " ${session_name} " ]] || session_names+=("$session_name")
            done

            if [ ${#session_names[@]} -eq 0 ]; then
                ADD_SESSION=""
                echo "No sessions found in $ADD_ANALYSIS_DIR. Proceeding without sessions."
            else
                echo -e "\nSelect available sessions:\n"
                SESSION_OPTIONS=()
                for idx in "${!session_names[@]}"; do
                    echo "$((idx + 1))) ${session_names[$idx]}"
                    SESSION_OPTIONS+=("$((idx + 1))")
                done

                echo ""
                read -p "Please enter your choice: " session_choice
                while ! [[ "$session_choice" =~ ^[0-9]+$ ]] || (( session_choice < 1 || session_choice > ${#session_names[@]} )); do
                    echo "Invalid selection. Please try again."
                    read -p "Please enter your choice: " session_choice
                done

                ADD_SESSION="${session_names[$((session_choice - 1))]}"
                echo -e "\nYou have selected session: $ADD_SESSION"
            fi

            echo -e "\nSelect subject to edit:\n"
            ADD_SUBJECT_OPTIONS=()
            ADD_SUBJECT_DIRS=()
            subject_dirs=($(find "$ADD_ANALYSIS_DIR" -mindepth 1 -maxdepth 1 -type d \( "${FIND_SUBJECT_EXPR[@]}" \) | sort))

            idx=0
            for dir in "${subject_dirs[@]}"; do
                subject_name=$(basename "$dir")
                if [ -n "$ADD_SESSION" ] && [ -d "$dir/$ADD_SESSION" ]; then
                    session_dir="$dir/$ADD_SESSION"
                else
                    session_dir="$dir"
                fi
                [ ! -d "$session_dir" ] && continue
                idxpadded=$(printf "%2d" $((idx + 1)))
                echo "${idxpadded})  $subject_name"
                ADD_SUBJECT_OPTIONS+=("$((idx + 1))")
                ADD_SUBJECT_DIRS+=("$dir")
                idx=$((idx + 1))
            done

            if [ ${#ADD_SUBJECT_OPTIONS[@]} -eq 0 ]; then
                if [ -n "$ADD_SESSION" ]; then
                    echo "No subjects found in session $ADD_SESSION."
                else
                    echo "No subjects found."
                fi
                continue
            fi
            echo ""
            read -p "Please enter your choice: " subject_choice
            while ! [[ "$subject_choice" =~ ^[0-9]+$ ]] || (( subject_choice < 1 || subject_choice > ${#ADD_SUBJECT_OPTIONS[@]} )); do
                echo "Invalid selection. Please try again."
                read -p "Please enter your choice: " subject_choice
            done

            ADD_SUBJECT_DIR="${ADD_SUBJECT_DIRS[$((subject_choice - 1))]}"
            subject=$(basename "$ADD_SUBJECT_DIR")
            subject_session="$ADD_SESSION"
            if [ -n "$ADD_SESSION" ]; then
                if [ -d "$ADD_SUBJECT_DIR/$ADD_SESSION" ]; then
                    echo -e "\nListing directories for $subject in session $ADD_SESSION..."
                    session_dir="$ADD_SUBJECT_DIR/$ADD_SESSION"
                else
                    echo -e "\nSession $ADD_SESSION not found for $subject. Listing directories without session..."
                    session_dir="$ADD_SUBJECT_DIR"
                    subject_session=""
                fi
            else
                echo -e "\nListing directories for $subject..."
                session_dir="$ADD_SUBJECT_DIR"
            fi
            directories_list=()
            directory_types_list=()

            if [ "$ADD_INPUT_TYPE" == "lower" ]; then
                func_dir="$session_dir/func"
                if [ ! -d "$func_dir" ]; then
                    if [ -n "$ADD_SESSION" ]; then
                        echo "  - No func directory found for $subject in session $ADD_SESSION."
                    else
                        echo "  - No func directory found for $subject."
                    fi
                    continue
                fi
                feat_dirs=($(find "$func_dir" -mindepth 1 -maxdepth 1 -type d -name "*.feat"))
                feat_dirs=($(printf "%s\n" "${feat_dirs[@]}" | sort))
                if [ ${#feat_dirs[@]} -eq 0 ]; then
                    if [ -n "$ADD_SESSION" ]; then
                        echo "  - No feat directories found for $subject in session $ADD_SESSION."
                    else
                        echo "  - No feat directories found for $subject."
                    fi
                    continue
                fi
                echo -e "\nFeat Directories:\n"
                for idx3 in "${!feat_dirs[@]}"; do
                    idxpadded=$(printf "%2d" $((idx3 + 1)))
                    echo "${idxpadded})  ${feat_dirs[$idx3]#$BASE_DIR/}"
                done
                echo -e "\nSelect the run corresponding to the lower-level FEAT directory to add/replace by entering its number:"
                read -p "> " feat_choice
                while ! [[ "$feat_choice" =~ ^[0-9]+$ ]] || (( feat_choice < 1 || feat_choice > ${#feat_dirs[@]} )); do
                    echo "Invalid selection. Please enter a single valid number in the available range."
                    echo -n "> "
                    read feat_choice
                done
                selected_feat="${feat_dirs[$((feat_choice - 1))]}"
                directories_list+=("$selected_feat")
                directory_types_list+=("lower")

            else
                gfeat_dirs=($(find "$session_dir" -mindepth 1 -maxdepth 1 -type d -name "*.gfeat"))
                gfeat_dirs=($(printf "%s\n" "${gfeat_dirs[@]}" | sort))
                if [ ${#gfeat_dirs[@]} -eq 0 ]; then
                    if [ -n "$ADD_SESSION" ]; then
                        echo "  - No .gfeat directories found for $subject in session $ADD_SESSION."
                    else
                        echo "  - No .gfeat directories found for $subject."
                    fi
                    continue
                fi
                echo -e "\ngfeat Directories:\n"
                for idx3 in "${!gfeat_dirs[@]}"; do
                    idxpadded=$(printf "%2d" $((idx3 + 1)))
                    echo "${idxpadded})  ${gfeat_dirs[$idx3]#$BASE_DIR/}"
                done
                echo -e "\nSelect the number corresponding to the .gfeat directory to edit (e.g., 1):"
                read -p "> " gfeat_choice
                while ! [[ "$gfeat_choice" =~ ^[0-9]+$ ]] || (( gfeat_choice < 1 || gfeat_choice > ${#gfeat_dirs[@]} )); do
                    echo "Invalid selection. Please enter a single valid number in the available range."
                    echo -n "> "
                    read gfeat_choice
                done
                selected_gfeat="${gfeat_dirs[$((gfeat_choice - 1))]}"
                directories_list+=("$selected_gfeat")
                directory_types_list+=("higher")
            fi

            directories_list_filtered=()
            directory_types_list_filtered=()
            for idx3 in "${!directories_list[@]}"; do
                dir="${directories_list[$idx3]}"
                [ -n "$dir" ] || continue
                directories_list_filtered+=("$dir")
                directory_types_list_filtered+=("${directory_types_list[$idx3]}")
            done

            directories_str=$(printf "::%s" "${directories_list_filtered[@]}")
            directories_str="${directories_str:2}"
            directory_types_str=$(printf "::%s" "${directory_types_list_filtered[@]}")
            directory_types_str="${directory_types_str:2}"

            subject_found=false
            for idx4 in "${!subjects[@]}"; do
                if [ "${subjects[$idx4]}" == "$subject" ]; then
                    directories[$idx4]="$directories_str"
                    directory_types[$idx4]="$directory_types_str"
                    sessions[$idx4]="$subject_session"
                    subject_found=true
                    break
                fi
            done
            if [ "$subject_found" == false ]; then
                subjects+=("$subject")
                directories+=("$directories_str")
                directory_types+=("$directory_types_str")
                sessions+=("$subject_session")
            fi
        elif [[ "$user_input" =~ ^- ]]; then
            read -ra remove_args <<< "$user_input"
            if [ ${#remove_args[@]} -lt 2 ]; then
                echo -e "\nError: No subjects provided to remove. Please try again."
                continue
            fi
            to_remove=("${remove_args[@]:1}")
            invalid_remove=false
            for sub in "${to_remove[@]}"; do
                if [ "$sub" == "edit" ]; then
                    echo -e "\nError: 'edit' keyword found while trying to remove subjects. Invalid input."
                    invalid_remove=true
                    break
                fi
                if ! printf '%s\n' "${subjects[@]}" | grep -qx "$sub"; then
                    echo -e "\nError: Subject '$sub' is not in the dataset or already excluded."
                    invalid_remove=true
                    break
                fi
            done
            if $invalid_remove; then
                continue
            fi

            new_subjects=()
            new_directories=()
            new_directory_types=()
            new_sessions=()
            for idx4 in "${!subjects[@]}"; do
                remove_this=false
                for rsub in "${to_remove[@]}"; do
                    if [ "${subjects[$idx4]}" == "$rsub" ]; then
                        remove_this=true
                        break
                    fi
                done
                if ! $remove_this; then
                    new_subjects+=("${subjects[$idx4]}")
                    new_directories+=("${directories[$idx4]}")
                    new_directory_types+=("${directory_types[$idx4]}")
                    new_sessions+=("${sessions[$idx4]}")
                fi
            done
            subjects=("${new_subjects[@]}")
            directories=("${new_directories[@]}")
            directory_types=("${new_directory_types[@]}")
            sessions=("${new_sessions[@]}")
        else
            echo "Invalid input. Please try again."
        fi
    done

    total_directories=0
    for idx in "${!subjects[@]}"; do
        directories_str="${directories[$idx]}"
        IFS='::' read -a directories_list <<< "$directories_str"
        total_directories=$((total_directories + ${#directories_list[@]}))
    done

    if [ "$total_directories" -lt 3 ]; then
        echo -e "\nError: At least 3 directories are required for mixed effects analysis."
        echo "You have selected only $total_directories directories."
        exit 1
    fi

    cope_numbers_per_directory=()
    dir_index=0
    for idx in "${!subjects[@]}"; do
        directories_str="${directories[$idx]}"
        directory_types_str="${directory_types[$idx]}"
        IFS='::' read -ra directories_list <<< "$directories_str"
        IFS='::' read -ra directory_types_list <<< "$directory_types_str"

        for ((d=0; d<${#directories_list[@]}; d++)); do
            dir="${directories_list[$d]}"
            dtype="${directory_types_list[$d]}"
            cnums_str="$(gather_cope_numbers "$dir" "$dtype")"
            cope_numbers_per_directory[$dir_index]="$cnums_str"
            ((dir_index++))
        done
    done

    common_cope_numbers_str="$(find_common_copes "${cope_numbers_per_directory[@]}")"
    IFS=' ' read -ra common_cope_numbers <<< "$common_cope_numbers_str"

    if [ ${#common_cope_numbers[@]} -eq 0 ]; then
        echo -e "\nError: No common copes found across all selected directories."
        exit 1
    fi

    for cope_num in "${common_cope_numbers[@]}"; do
        for subject in "${subjects[@]}"; do
            for idx in "${!subjects[@]}"; do
                if [ "${subjects[$idx]}" == "$subject" ]; then
                    directories_str="${directories[$idx]}"
                    directory_types_str="${directory_types[$idx]}"
                    break
                fi
            done

            IFS='::' read -ra directories_list <<< "$directories_str"
            IFS='::' read -ra directory_types_list <<< "$directory_types_str"

            for ((di=0; di<${#directories_list[@]}; di++)); do
                dir="${directories_list[$di]}"
                dir_type="${directory_types_list[$di]}"
                if [ "$dir_type" == "lower" ]; then
                    cope_file="$dir/stats/cope${cope_num}.nii.gz"
                    if [ ! -f "$cope_file" ]; then
                        echo "Error: Missing cope${cope_num} for subject $subject in directory $dir."
                        exit 1
                    fi
                else
                    cope_dir="$dir/cope${cope_num}.feat"
                    cope_file="$cope_dir/stats/cope1.nii.gz"
                    if [ ! -d "$cope_dir" ] || [ ! -f "$cope_file" ]; then
                        echo "Error: Missing cope${cope_num} for subject $subject in directory $dir."
                        exit 1
                    fi
                fi
            done
        done
    done

    echo -e "\n=== Mixed Effects ==="
    echo "Please select a higher-level modelling approach:"
    echo
    echo "1) Simple OLS (Ordinary Least Squares)"
    echo "2) Mixed Effects: FLAME 1"
    echo "3) Mixed Effects: FLAME 1+2"
    echo -n "> "
    read mixed_choice

    valid_mixed=false
    while [ "$valid_mixed" = false ]; do
        case "$mixed_choice" in
            1)
                echo "You selected Mixed Effects: Simple OLS"
                fmri_mixed="0"
                mixed_label="OLS"
                valid_mixed=true
                ;;
            2)
                echo "You selected Mixed Effects: FLAME 1"
                fmri_mixed="2"
                mixed_label="FLAME1"
                valid_mixed=true
                ;;
            3)
                echo "You selected Mixed Effects: FLAME 1+2"
                fmri_mixed="1"
                mixed_label="FLAME1plus2"
                valid_mixed=true
                ;;
            *)
                echo "Invalid input. Please enter 1, 2, or 3."
                echo -n "> "
                read mixed_choice
                ;;
        esac
    done

    echo -e "\n=== Customize Output Folder Name (Optional) ==="
    echo "Enter a task name to include in the group analysis output folder."
    echo "Press Enter/Return to skip the task name."

    valid_task=false
    task_name=""
    while [ "$valid_task" = false ]; do
        echo -en "\nTask name (leave blank for no task):\n> "
        read task_name
        if [[ -z "$task_name" ]]; then
            valid_task=true
        else
            if [[ "$task_name" =~ ^[A-Za-z0-9_-]+$ ]]; then
                valid_task=true
            else
                echo "Invalid task name. Only alphanumeric, underscores, and dashes are allowed. No spaces."
            fi
        fi
    done

    echo
    echo "Enter a descriptor (e.g., \"postICA\") to customize the group analysis output folder."
    echo "Press Enter/Return to use the default format."
    if [ -n "$task_name" ]; then
        echo "Default format: /level-3/task-${task_name}_desc-group-${mixed_label}/cope*.gfeat"
    else
        echo "Default format: /level-3/desc-group-${mixed_label}/cope*.gfeat"
    fi
    echo

    valid_desc=false
    custom_desc=""
    while [ "$valid_desc" = false ]; do
        echo -en "Descriptor (e.g., postICA or leave blank for default):\n> "
        read custom_desc
        if [[ -z "$custom_desc" ]]; then
            valid_desc=true
        else
            if [[ "$custom_desc" =~ ^[A-Za-z0-9_-]+$ ]]; then
                valid_desc=true
            else
                echo "Invalid descriptor. Only alphanumeric, underscores, and dashes are allowed. No spaces."
            fi
        fi
    done

    output_subdir=""
    if [ -n "$task_name" ] && [ -n "$custom_desc" ]; then
        output_subdir="task-${task_name}_desc-${custom_desc}_group-${mixed_label}"
    elif [ -n "$task_name" ] && [ -z "$custom_desc" ]; then
        output_subdir="task-${task_name}_desc-group-${mixed_label}"
    elif [ -z "$task_name" ] && [ -n "$custom_desc" ]; then
        output_subdir="desc-${custom_desc}_group-${mixed_label}"
    else
        output_subdir="desc-group-${mixed_label}"
    fi

    OUTPUT_DIR="$LEVEL_3_ANALYSIS_BASE_DIR/$output_subdir"

    echo -e "\nOutput directory will be set to:"
    echo "  - $OUTPUT_DIR"

    mkdir -p "$OUTPUT_DIR"

    echo -e "\n=== FEAT Thresholding Options ==="
    echo "You can specify the Z threshold and Cluster P threshold."
    echo "Press Enter/Return to use default values (Z threshold: 2.3, Cluster P threshold: 0.05)."

    default_z=2.3
    default_p=0.05
    valid_z=false
    while [ "$valid_z" = false ]; do
        echo -e "\nEnter Z threshold (default $default_z):"
        echo -n "> "
        read z_threshold_input
        while [ -n "$z_threshold_input" ] && ! [[ "$z_threshold_input" =~ ^[0-9]*\.?[0-9]+$ ]]; do
            echo "Invalid input. Please enter a numeric value or press Enter/Return to use default value of $default_z."
            echo -n "> "
            read z_threshold_input
        done
        if [ -z "$z_threshold_input" ]; then
            z_threshold=$default_z
            valid_z=true
            echo "Using Z threshold of $z_threshold"
        else
            z_threshold="$z_threshold_input"
            valid_z=true
            echo "Using Z threshold of $z_threshold"
        fi
    done

    valid_p=false
    while [ "$valid_p" = false ]; do
        echo -e "\nEnter Cluster P threshold (default $default_p):"
        echo -n "> "
        read cluster_p_input
        while [ -n "$cluster_p_input" ] && ! [[ "$cluster_p_input" =~ ^[0-9]*\.?[0-9]+$ ]]; do
            echo "Invalid input. Please enter a numeric value or press Enter/Return to use default value of $default_p."
            echo -n "> "
            read cluster_p_input
        done
        if [ -z "$cluster_p_input" ]; then
            cluster_p_threshold=$default_p
            valid_p=true
            echo "Using Cluster P threshold of $cluster_p_threshold"
        else
            cluster_p_threshold="$cluster_p_input"
            valid_p=true
            echo "Using Cluster P threshold of $cluster_p_threshold"
        fi
    done

    echo -e "\n=== Robust Outlier Detection in FLAME ==="
    echo "Would you like to enable robust outlier detection? (y/n)"
    valid_robust=false
    while [ "$valid_robust" = false ]; do
        echo -n "> "
        read robust_choice
        robust_choice=$(echo "$robust_choice" | tr '[:upper:]' '[:lower:]')
        [ -z "$robust_choice" ] && robust_choice="n"
        if [ "$robust_choice" == "y" ]; then
            fmri_robust=1
            echo "Robust outlier detection will be ENABLED."
            valid_robust=true
        elif [ "$robust_choice" == "n" ]; then
            fmri_robust=0
            echo "Robust outlier detection will be DISABLED."
            valid_robust=true
        else
            echo "Invalid input. Please enter 'y' or 'n'."
        fi
    done

    TEMPLATE="$BASE_DIR/derivatives/templates/MNI152_T1_2mm_brain.nii.gz"
    if [ ! -f "$TEMPLATE" ]; then
        echo "[Warning] Template file $TEMPLATE not found (not fatal, but check)."
    fi

    echo -e "\n====================================="
    echo ">>> Third-Level Group Analysis <<<"
    echo "====================================="
    echo -e "\nTotal copes to process: ${#common_cope_numbers[@]}\n"

    total_copes=${#common_cope_numbers[@]}
    i=1

    for cope_num in "${common_cope_numbers[@]}"; do
        echo "=== ($i/$total_copes) Cope${cope_num} ==="

        input_lines=""
        group_membership=""
        ev_values=""
        input_index=0
        num_inputs=0

        current_inputs=()

        sorted_subjects=($(printf "%s\n" "${subjects[@]}" | sort))
        for subject in "${sorted_subjects[@]}"; do
            for idx in "${!subjects[@]}"; do
                if [ "${subjects[$idx]}" == "$subject" ]; then
                    directories_str="${directories[$idx]}"
                    directory_types_str="${directory_types[$idx]}"
                    break
                fi
            done
            IFS='::' read -ra directories_list <<< "$directories_str"
            IFS='::' read -ra directory_types_list <<< "$directory_types_str"

            sorted_pairs=($(paste -d ':' \
                <(printf "%s\n" "${directories_list[@]}") \
                <(printf "%s\n" "${directory_types_list[@]}") | sort))

            directories_list=()
            directory_types_list=()
            for pair in "${sorted_pairs[@]}"; do
                IFS=':' read -r dir dir_type <<< "$pair"
                directories_list+=("$dir")
                directory_types_list+=("$dir_type")
            done

            for ((d=0; d<${#directories_list[@]}; d++)); do
                dir="${directories_list[$d]}"
                dir_type="${directory_types_list[$d]}"

                ((input_index++))
                ((num_inputs++))

                if [ "$dir_type" == "lower" ]; then
                    cope_file="$dir/stats/cope${cope_num}.nii.gz"
                else
                    cope_file="$dir/cope${cope_num}.feat/stats/cope1.nii.gz"
                fi

                cope_file_escaped="$(echo "$cope_file" | tcl_escape)"
                input_lines+="set feat_files($input_index) \"$cope_file_escaped\"\n"
                group_membership+="set fmri(groupmem.$input_index) 1\n"
                ev_values+="set fmri(evg$input_index.1) 1\n"

                short_path="${cope_file#$BASE_DIR/}"
                current_inputs+=("$short_path")
            done
        done

        echo "  Inputs:"
        for path in "${current_inputs[@]}"; do
            echo "    • $path"
        done

        temp_design_file="${OUTPUT_DIR}/cope${cope_num}_design.fsf"
        echo -e "\n  Design file: $temp_design_file"
        echo "  Running FEAT..."

        run_third_level_feat \
            "$cope_num" \
            "$OUTPUT_DIR" \
            "$BASE_DIR/code/design_files/desc-mixedeffects_design.fsf" \
            "$z_threshold" \
            "$cluster_p_threshold" \
            "$TEMPLATE" \
            "$fmri_mixed" \
            "$fmri_robust" \
            "$num_inputs" \
            "$input_lines" \
            "$ev_values" \
            "$group_membership"

        echo "  [Done] Third-level analysis complete."
        echo -e "\n--------------------------------------------\n"

        ((i++))
    done

    echo "All third-level analyses completed"

    create_dataset_description_json \
      "$OUTPUT_DIR" \
      "$CONFIG_FILE" \
      "$mixed_label" \
      "$z_threshold" \
      "$cluster_p_threshold" \
      "$fmri_robust" \
      "$BIDS_VERSION" \
      "$LOGFILE"

    exit 0

# ------------------------------------------------------------------
# 2) Have CLI FLAGS: Non-interactive Mode
# ------------------------------------------------------------------
else
    echo "[Info] Detected command-line flags => Running in NON-INTERACTIVE mode." >> $LOGFILE

    if [ -z "$analysis_dir_arg" ] || [ ! -d "$analysis_dir_arg" ]; then
        echo "Error: --analysis-dir must be a valid directory. You passed: $analysis_dir_arg"
        exit 1
    fi


    if [ -z "$subjects_arg" ]; then
        echo "Error: --subjects is required (space-separated or wildcard)."
        exit 1
    fi

    case "$mixed_arg" in
        "OLS"|"ols")
            fmri_mixed="0"
            mixed_label="OLS"
            ;;
        "FLAME1"|"flame1")
            fmri_mixed="2"
            mixed_label="FLAME1"
            ;;
        "FLAME1plus2"|"flame1plus2")
            fmri_mixed="1"
            mixed_label="FLAME1plus2"
            ;;
        *)
            echo "Error: --mixed-effects must be one of: OLS, FLAME1, FLAME1plus2"
            exit 1
            ;;
    esac

    z_threshold="${z_thresh_arg:-2.3}"
    cluster_p_threshold="${cluster_p_arg:-0.05}"
    fmri_robust=0
    if [ "$robust_arg" = true ]; then
        fmri_robust=1
    fi

    if [ -n "$task_name_arg" ] && [ -n "$desc_arg" ]; then
        output_subdir="task-${task_name_arg}_desc-${desc_arg}_group-${mixed_label}"
    elif [ -n "$task_name_arg" ] && [ -z "$desc_arg" ]; then
        output_subdir="task-${task_name_arg}_desc-group-${mixed_label}"
    elif [ -z "$task_name_arg" ] && [ -n "$desc_arg" ]; then
        output_subdir="desc-${desc_arg}_group-${mixed_label}"
    else
        output_subdir="desc-group-${mixed_label}"
    fi

    OUTPUT_DIR="$LEVEL_3_ANALYSIS_BASE_DIR/$output_subdir"
    mkdir -p "$OUTPUT_DIR"

    echo "=== Non-interactive run, summary of inputs ===" >> $LOGFILE
    echo "  Analysis Dir:      $analysis_dir_arg" >> $LOGFILE
    echo "  Session:           $session_arg" >> $LOGFILE
    session_display="$session_arg"
    [ -z "$session_display" ] && session_display="None"
    echo "Session: $session_display"
    echo "  Subjects:          $subjects_arg" >> $LOGFILE
    echo "  Mixed Effects:     $mixed_label" >> $LOGFILE
    echo "  Z threshold:       $z_threshold" >> $LOGFILE
    echo "  Cluster P thresh:  $cluster_p_threshold" >> $LOGFILE
    echo "  Robust Outliers:   $([ "$fmri_robust" == "1" ] && echo 'Enabled' || echo 'Disabled')" >> $LOGFILE
    echo "  Task Name:         $task_name_arg" >> $LOGFILE
    echo "  Descriptor:        $desc_arg" >> $LOGFILE
    echo "  Output Dir:        $OUTPUT_DIR" >> $LOGFILE
    echo "===========================================" >> $LOGFILE

    declare -a subject_array=($subjects_arg)
    declare -a final_subjects=()
    declare -a directories=()
    declare -a sessions=()

    shopt -s nullglob
    for subj_pattern in "${subject_array[@]}"; do
        for found_subj_path in "$analysis_dir_arg"/$subj_pattern; do
            [ ! -d "$found_subj_path" ] && continue
            actual_subj="$(basename "$found_subj_path")"
            if [ -n "$session_arg" ] && [ -d "$found_subj_path/$session_arg" ]; then
                search_dir="$found_subj_path/$session_arg"
                subj_session="$session_arg"
            else
                search_dir="$found_subj_path"
                subj_session=""
            fi

            gfeat_dirs=($(find "$search_dir" -mindepth 1 -maxdepth 1 -type d -name "*.gfeat" | sort))
            if [ ${#gfeat_dirs[@]} -lt 1 ]; then
                if [ -n "$session_arg" ]; then
                    echo "[Warn] No .gfeat found for $actual_subj in session $session_arg"
                fi
                continue
            fi

            final_subjects+=("$actual_subj")
            joined_gfeats="$(printf "::%s" "${gfeat_dirs[@]}")"
            directories+=("${joined_gfeats:2}")
            sessions+=("$subj_session")
        done
    done
    shopt -u nullglob

    if [ ${#final_subjects[@]} -lt 1 ]; then
        if [ -n "$session_arg" ]; then
            echo "Error: No matching .gfeat directories found for the specified subjects in session $session_arg."
        else
            echo "Error: No matching .gfeat directories found for the specified subjects."
        fi
        exit 1
    fi

    total_dirs=0
    for idx in "${!final_subjects[@]}"; do
        IFS='::' read -ra splitted <<< "${directories[$idx]}"
        total_dirs=$(( total_dirs + ${#splitted[@]} ))
    done
    if [ "$total_dirs" -lt 3 ]; then
        echo "Error: At least 3 .gfeat directories are required for group analysis. Found $total_dirs."
        exit 1
    fi

    declare -a cope_numbers_per_dir=()
    dir_index=0

    for idx in "${!final_subjects[@]}"; do
        IFS='::' read -ra gfeats <<< "${directories[$idx]}"
        for gfeat_dir in "${gfeats[@]}"; do
            cnums_str="$(gather_cope_numbers "$gfeat_dir" "higher")"
            cope_numbers_per_dir[$dir_index]="$cnums_str"
            ((dir_index++))
        done
    done

    common_cope_nums_str="$(find_common_copes "${cope_numbers_per_dir[@]}")"
    IFS=' ' read -ra common_cope_nums <<< "$common_cope_nums_str"

    if [ ${#common_cope_nums[@]} -lt 1 ]; then
        echo "Error: No common cope numbers found across the selected .gfeat directories."
        exit 1
    fi

    TEMPLATE="$BASE_DIR/derivatives/templates/MNI152_T1_2mm_brain.nii.gz"
    if [ ! -f "$TEMPLATE" ]; then
        echo "[Warning] Template file $TEMPLATE not found (not fatal, but check)."
    fi

    echo
    echo "====================================="
    echo ">>> Third-Level Group Analysis <<<"
    echo "====================================="
    echo -e "\nTotal copes to process: ${#common_cope_nums[@]}\n"

    total_copes=${#common_cope_nums[@]}
    i=1

    for cnum in "${common_cope_nums[@]}"; do
        echo "=== ($i/$total_copes) Cope${cnum} ==="

        input_lines=""
        group_membership=""
        ev_values=""
        input_index=0
        num_inputs=0
        current_inputs=()

        sorted_subjs=($(printf "%s\n" "${final_subjects[@]}" | sort))
        for s_idx in "${!sorted_subjs[@]}"; do
            for match_idx in "${!final_subjects[@]}"; do
                if [ "${final_subjects[$match_idx]}" == "${sorted_subjs[$s_idx]}" ]; then
                    IFS='::' read -ra s_gfeats <<< "${directories[$match_idx]}"
                    break
                fi
            done

            for gfeat_dir in "${s_gfeats[@]}"; do
                cope_dir="$gfeat_dir/cope${cnum}.feat"
                cope_file="$cope_dir/stats/cope1.nii.gz"

                if [ -d "$cope_dir" ] && [ -f "$cope_file" ]; then
                    ((input_index++))
                    ((num_inputs++))

                    cope_file_escaped="$(echo "$cope_file" | tcl_escape)"
                    input_lines+="set feat_files($input_index) \"$cope_file_escaped\"\n"
                    group_membership+="set fmri(groupmem.$input_index) 1\n"
                    ev_values+="set fmri(evg$input_index.1) 1\n"

                    short_path="${cope_file#$BASE_DIR/}"
                    current_inputs+=("$short_path")
                fi
            done
        done

        if [ "$num_inputs" -lt 3 ]; then
            echo "  - Only $num_inputs valid inputs found for cope$cnum; skipping (need >=3)."
            ((i++))
            echo -e "\n--------------------------------------------\n"
            continue
        fi

        echo "  Inputs:"
        for inp in "${current_inputs[@]}"; do
            echo "    • $inp"
        done

        temp_design_file="${OUTPUT_DIR}/cope${cnum}_design.fsf"
        echo -e "\n  Design file: $temp_design_file"
        echo "  Running FEAT..."

        run_third_level_feat \
          "$cnum" \
          "$OUTPUT_DIR" \
          "$BASE_DIR/code/design_files/desc-mixedeffects_design.fsf" \
          "$z_threshold" \
          "$cluster_p_threshold" \
          "$TEMPLATE" \
          "$fmri_mixed" \
          "$fmri_robust" \
          "$num_inputs" \
          "$input_lines" \
          "$ev_values" \
          "$group_membership"

        echo "  [Done] Third-level analysis complete."
        echo -e "\n--------------------------------------------\n"

        ((i++))
    done

    echo "All third-level analyses completed"

    create_dataset_description_json \
      "$OUTPUT_DIR" \
      "$CONFIG_FILE" \
      "$mixed_label" \
      "$z_threshold" \
      "$cluster_p_threshold" \
      "$fmri_robust" \
      "$BIDS_VERSION" \
      "$LOGFILE"

    echo
    echo "=== Third-level analysis complete (CLI) ==="
fi

exit 0
