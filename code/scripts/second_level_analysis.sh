#!/bin/bash
###############################################################################
# second_level_analysis.sh
#
# Purpose:
#   Run FSL fixed-effects analyses across runs or sessions.
#   Supports interactive prompts or command-line options.
#
# Usage:
#   second_level_analysis.sh [options]
#
# Usage Examples:
#   1) ./second_level_analysis.sh \
#        --analysis-dir "analysis_postICA" \
#        --exclude "sub-*:ses-01" \
#        --z-thresh 2.3 \
#        --cluster-p-thresh 0.05
#   2) ./second_level_analysis.sh \
#        --analysis-dir "analysis" \
#        --exclude "sub-002" \
#        --exclude "sub-005" \
#        --exclude "sub-007" \
#        --z-thresh 1.65 \
#        --cluster-p-thresh 0.05
#   3) ./second_level_analysis.sh \
#        --analysis-dir "analysis_postICA" \
#        --subject "sub-001" \
#        --subject "sub-002:ses-01:01,02" \
#        --exclude "sub-003" \
#        --exclude "sub-002:ses-01:03" \
#        --z-thresh 3.1 \
#        --cluster-p-thresh 0.01 \
#        --task-name "SomeTaskName"
#   4) ./second_level_analysis.sh \
#        --analysis-dir "analysis_postICA" \
#        --subject "sub-002:ses-01" \
#        --z-thresh 1.65 \
#        --cluster-p-thresh 0.05
#
# Options:
#   --analysis-dir DIR     Output analysis directory name
#   --subject ID[:SES[:RUNS]]  Subject include list
#   --exclude ID           Subjects or sessions to exclude
#   --z-thresh VALUE       Z threshold
#   --cluster-p-thresh VAL Cluster p threshold
#   --task-name NAME       Task name override
#   -h, --help             Show help
#
# Requirements:
#   FSL and yq
#
# Notes:
#   If no options are provided, the script runs interactively.
#   Reads config.yaml for dataset description information.
#
###############################################################################

# ---------------
# CONFIG / PATHS
# ---------------
script_dir="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(dirname "$(dirname "$script_dir")")"

CONFIG_FILE="$BASE_DIR/code/config/config.yaml"  # Path to config.yaml

GENERATE_DESIGN_SCRIPT="$BASE_DIR/code/scripts/generate_fixed_effects_design_fsf.sh"
CREATE_DS_DESC_SCRIPT="$BASE_DIR/code/scripts/create_dataset_description.sh"

ANALYSIS_BASE_DIR="$BASE_DIR/derivatives/fsl/level-1"
BASE_DESIGN_FSF="$BASE_DIR/code/design_files/desc-fixedEffects_design.fsf"
TEMPLATE="$BASE_DIR/derivatives/templates/MNI152_T1_2mm_brain.nii.gz"

# ---------------
# Check existence
# ---------------
if [ ! -f "$BASE_DESIGN_FSF" ]; then
    echo "Error: Base design file not found at $BASE_DESIGN_FSF"
    exit 1
fi

if [ ! -f "$TEMPLATE" ]; then
    echo "Error: Template not found at $TEMPLATE"
    exit 1
fi

if [ ! -f "$GENERATE_DESIGN_SCRIPT" ]; then
    echo "Error: generate_fixed_effects_design_fsf.sh not found at $GENERATE_DESIGN_SCRIPT"
    exit 1
fi

# ---------------
# Parse config.yaml
# ---------------
if ! command -v yq &>/dev/null; then
    echo -e "\nError: 'yq' is required but not found in PATH.\n"
    exit 1
fi

# Ensure FSL's FEAT command is available
if ! command -v feat >/dev/null; then
    echo "Error: FSL 'feat' command not found in PATH."
    exit 1
fi

BIDS_VERSION="$(yq e '.bids_version' "$CONFIG_FILE")"
LEVEL_2_BASE_DIR="$(yq e '.fsl.level-2.fixed_effects_output_dir' "$CONFIG_FILE")"
[ -z "$LEVEL_2_BASE_DIR" ] && LEVEL_2_BASE_DIR="derivatives/fsl/level-2"

# Parse second-level "fixed_effects" fields
L2_NAME="$(yq e '.dataset_descriptions.level-2.fixed_effects.name' "$CONFIG_FILE")"
L2_DATASET_TYPE="$(yq e '.dataset_descriptions.level-2.fixed_effects.dataset_type' "$CONFIG_FILE")"
L2_DESCRIPTION="$(yq e '.dataset_descriptions.level-2.fixed_effects.description' "$CONFIG_FILE")"

# Build array of generatedby entries (loop)
L2_GENERATEDBY=()
n_gb=$(yq e '.dataset_descriptions.level-2.fixed_effects.generatedby | length' "$CONFIG_FILE")

for ((idx=0; idx<n_gb; idx++)); do
  # Pull each subkey
  gb_name=$(yq e ".dataset_descriptions.level-2.fixed_effects.generatedby[$idx].name" "$CONFIG_FILE")
  gb_version=$(yq e ".dataset_descriptions.level-2.fixed_effects.generatedby[$idx].version" "$CONFIG_FILE")
  gb_desc=$(yq e ".dataset_descriptions.level-2.fixed_effects.generatedby[$idx].description" "$CONFIG_FILE")

  # Construct 'Name=...,Version=...,Description=...'
  gb_str="Name=${gb_name}"
  [ "$gb_version" != "null" ] && gb_str+=",Version=${gb_version}"
  [ "$gb_desc"   != "null" ] && gb_str+=",Description=${gb_desc}"

  L2_GENERATEDBY+=("$gb_str")
done


# ---------------
# Logging setup
# ---------------
LOG_DIR="$BASE_DIR/code/logs"
mkdir -p "$LOG_DIR"
LOGFILE="$LOG_DIR/$(basename "$0" .sh)_$(date +'%Y%m%d_%H%M%S').log"
exec > >(tee -a "$LOGFILE") 2>&1

# ---------------
# Parse CLI arguments
# ---------------
analysis_dir_arg=""
declare -a subject_inclusion_args=()
declare -a subject_exclusion_args=()
z_threshold_arg=""
cluster_p_threshold_arg=""
task_name_arg=""
SHOW_HELP=false

# Add a boolean to track whether ANY recognized CLI flag is used
used_cli_flags=false

usage() {
    local mode="$1"

    echo "Usage: $(basename $0) [options]"
    echo
    echo "Optional arguments:"
    echo "  --analysis-dir <str>         Which first-level analysis folder to use"
    echo "  --subject <pattern>          Include subject/session/run pattern"
    echo "  --exclude <pattern>          Exclude subject/session/run pattern"
    echo "  --z-thresh <float>           Z-threshold (e.g. 2.3)"
    echo "  --cluster-p-thresh <float>   Cluster p-threshold (e.g. 0.05)"
    echo "  --task-name <str>            Optional custom task name for output directories"
    echo "  --help                       Show this help and exit"
    echo
    echo "If you omit all arguments, the script runs in interactive mode."
    echo

    # If called without 'no-exit', then exit the script
    if [ "$mode" = "no-exit" ]; then
        return 0
    else
        exit 1
    fi
}

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --analysis-dir)
            analysis_dir_arg="$2"
            used_cli_flags=true
            shift 2
            ;;
        --subject)
            subject_inclusion_args+=("$2")
            used_cli_flags=true
            shift 2
            ;;
        --exclude)
            subject_exclusion_args+=("$2")
            used_cli_flags=true
            shift 2
            ;;
        --z-thresh)
            z_threshold_arg="$2"
            used_cli_flags=true
            shift 2
            ;;
        --cluster-p-thresh)
            cluster_p_threshold_arg="$2"
            used_cli_flags=true
            shift 2
            ;;
        --task-name)
            task_name_arg="$2"
            used_cli_flags=true
            shift 2
            ;;
        --help)
            SHOW_HELP=true
            shift
            ;;
        *)
            echo "Unknown argument: $1"
            SHOW_HELP=true
            shift
            ;;
    esac
done

if [ "$SHOW_HELP" = true ]; then
    usage
fi

# ---------------
# Helper functions
# ---------------
add_unique_item() {
    local arr_name=$1
    local item=$2
    eval "local arr=(\"\${$arr_name[@]}\")"
    for existing in "${arr[@]}"; do
        if [ "$existing" = "$item" ]; then
            return 0
        fi
    done
    eval "$arr_name+=(\"$item\")"
}

array_contains() {
    local seeking=$1
    shift
    for elem in "$@"; do
        if [ "$elem" = "$seeking" ]; then
            return 0
        fi
    done
    return 1
}

count_cope_files() {
    local feat_dir="$1"
    local stats_dir="$feat_dir/stats"
    local cope_count=0
    if [ -d "$stats_dir" ]; then
        cope_count=$(find "$stats_dir" -mindepth 1 -maxdepth 1 -type f -name "cope*.nii.gz" | wc -l | xargs)
    fi
    echo "$cope_count"
}

check_common_cope_count() {
    local feat_dirs=("$@")
    local cope_counts=()
    local valid_feat_dirs=()
    local warning_messages=""
    local total_runs=${#feat_dirs[@]}

    for feat_dir in "${feat_dirs[@]}"; do
        local c
        c=$(count_cope_files "$feat_dir")
        cope_counts+=("$c")
    done

    unique_cope_counts=()
    cope_counts_freq=()

    for c in "${cope_counts[@]}"; do
        local found=false
        for ((i=0; i<${#unique_cope_counts[@]}; i++)); do
            if [ "${unique_cope_counts[i]}" -eq "$c" ]; then
                cope_counts_freq[i]=$(( cope_counts_freq[i] + 1 ))
                found=true
                break
            fi
        done
        if [ "$found" = false ]; then
            unique_cope_counts+=("$c")
            cope_counts_freq+=(1)
        fi
    done

    local max_freq=0
    local common_cope_counts=()
    for ((i=0; i<${#unique_cope_counts[@]}; i++)); do
        local freq=${cope_counts_freq[i]}
        if [ "$freq" -gt "$max_freq" ]; then
            max_freq=$freq
            common_cope_counts=("${unique_cope_counts[i]}")
        elif [ "$freq" -eq "$max_freq" ]; then
            common_cope_counts+=("${unique_cope_counts[i]}")
        fi
    done

    if [ ${#common_cope_counts[@]} -gt 1 ]; then
        echo "UNEQUAL_COPES_TIE"
        echo "  - Unequal cope counts found across runs: ${unique_cope_counts[*]}."
        return
    fi

    local common_cope_count="${common_cope_counts[0]}"
    if [ "$max_freq" -gt $((total_runs / 2)) ]; then
        for idx in "${!feat_dirs[@]}"; do
            if [ "${cope_counts[$idx]}" -eq "$common_cope_count" ]; then
                valid_feat_dirs+=("${feat_dirs[$idx]}")
            else
                if [ -n "$warning_messages" ]; then
                    warning_messages="${warning_messages}\n  - $(basename "${feat_dirs[$idx]}") does not have the common cope count $common_cope_count and will be excluded."
                else
                    warning_messages="  - $(basename "${feat_dirs[$idx]}") does not have the common cope count $common_cope_count and will be excluded."
                fi
            fi
        done
        echo "$common_cope_count"
        for dir in "${valid_feat_dirs[@]}"; do
            echo "$dir"
        done
        if [ -n "$warning_messages" ]; then
            echo "WARNINGS_START"
            echo -e "$warning_messages"
        fi
    else
        echo "UNEQUAL_COPES"
        echo "  - Unequal cope counts across runs: ${unique_cope_counts[*]}. Excluding subject-session."
    fi
}

parse_generatedby() {
  local entry="$1"

  # Extract Name (ends at next comma)
  local name
  name="$(echo "$entry" | sed -nE 's/.*Name=([^,]+).*/\1/p')"

  # Extract Version (ends at next comma)
  local version
  version="$(echo "$entry" | sed -nE 's/.*Version=([^,]+).*/\1/p')"

  # Extract EVERYTHING after "Description="
  local desc
  desc="$(echo "$entry" | sed -nE 's/.*Description=(.*)/\1/p')"

  # Return them separated by |
  echo "$name|$version|$desc"
}

# ---------------
# Main logic
# ---------------
SUBJECT_NAME_PATTERNS=("sub-*" "subject-*" "pilot-*" "subj-*" "subjpilot-*")
SESSION_NAME_PATTERNS=("ses-*" "session-*" "ses_*" "session_*" "ses*" "session*" "baseline" "endpoint" "ses-001" "ses-002")

ALL_SUBJECTS=()
ALL_SESSIONS=()
SUBJECT_SESSION_LIST=()
subject_dirs=()
all_valid_feat_dirs=()
subject_session_keys=()
subject_session_cope_counts=()
available_subject_sessions=()

###############################################################################
# 1) Figure out which first-level directory
###############################################################################
ANALYSIS_DIR_CHOOSEN=""
ANALYSIS_DIRS=($(find "$ANALYSIS_BASE_DIR" -maxdepth 1 -type d -name "*analysis*" 2>/dev/null | sort))
if [ ${#ANALYSIS_DIRS[@]} -eq 0 ]; then
    echo "No analysis directories found in $ANALYSIS_BASE_DIR."
    exit 1
fi

if [ -n "$analysis_dir_arg" ]; then
    # Attempt to find a match
    possible_path="$ANALYSIS_BASE_DIR/$analysis_dir_arg"
    if [ -d "$possible_path" ]; then
        ANALYSIS_DIR_CHOOSEN="$possible_path"
    else
        # If absolute path provided
        if [ -d "$analysis_dir_arg" ]; then
            ANALYSIS_DIR_CHOOSEN="$analysis_dir_arg"
        else
            echo "Error: The specified --analysis-dir '$analysis_dir_arg' was not found."
            exit 1
        fi
    fi
else
    # Interactive selection
    echo
    echo "=== First-Level Analysis Directory Selection ==="
    echo "Please select a first-level analysis directory for second-level fixed effects processing:"
    echo

    i=1
    for dir in "${ANALYSIS_DIRS[@]}"; do
        echo "  $i) $dir"
        ((i++))
    done
    echo

    valid_choice=false
    while [ "$valid_choice" = false ]; do
        echo -n "Please enter your choice (1-${#ANALYSIS_DIRS[@]}): "
        read choice
        if ! [[ "$choice" =~ ^[0-9]+$ ]]; then
            echo "Invalid selection. Please try again."
            continue
        fi
        if [ "$choice" -lt 1 ] || [ "$choice" -gt ${#ANALYSIS_DIRS[@]} ]; then
            echo "Invalid selection. Please try again."
            continue
        fi
        ANALYSIS_DIR_CHOOSEN="${ANALYSIS_DIRS[$((choice-1))]}"
        valid_choice=true
    done
fi

echo
echo "You have selected the following analysis directory for fixed effects:"
echo "  $ANALYSIS_DIR_CHOOSEN"
echo

analysis_basename="$(basename "$ANALYSIS_DIR_CHOOSEN")"
LEVEL_2_ANALYSIS_DIR="${BASE_DIR}/${LEVEL_2_BASE_DIR}/${analysis_basename}"

###############################################################################
# 2) Gather subject/session/FEAT
###############################################################################
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

subject_dirs=($(find "$ANALYSIS_DIR_CHOOSEN" -mindepth 1 -maxdepth 1 -type d \( "${FIND_SUBJECT_EXPR[@]}" \) 2>/dev/null | sort))
if [ ${#subject_dirs[@]} -eq 0 ]; then
    echo "No subject directories found in $ANALYSIS_DIR_CHOOSEN."
    exit 1
fi

LISTING_OUTPUT="=== Listing First-Level Feat Directories ===\n\n"

for subject_dir in "${subject_dirs[@]}"; do
    subject=$(basename "$subject_dir")
    add_unique_item ALL_SUBJECTS "$subject"

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

    session_dirs=($(find "$subject_dir" -mindepth 1 -maxdepth 1 -type d \( "${FIND_SESSION_EXPR[@]}" \) 2>/dev/null | sort))
    if [ ${#session_dirs[@]} -eq 0 ] && [ -d "$subject_dir/func" ]; then
        session_dirs=("$subject_dir")
    fi

    for session_dir in "${session_dirs[@]}"; do
        if [ "$session_dir" = "$subject_dir" ]; then
            session=""
        else
            session=$(basename "$session_dir")
            add_unique_item ALL_SESSIONS "$session"
            add_unique_item SUBJECT_SESSION_LIST "${subject}|${session}"
        fi

        key="$subject:$session"
        available_subject_sessions+=("$key")

        feat_dirs=()
        if [ -d "$session_dir/func" ]; then
            feat_dirs=($(find "$session_dir/func" -mindepth 1 -maxdepth 1 -type d -name "*.feat" 2>/dev/null | sort))
        fi

        if [ -z "$session" ]; then
            LISTING_OUTPUT+="--- Subject: $subject | Session: None ---\n\n"
        else
            LISTING_OUTPUT+="--- Subject: $subject | Session: $session ---\n\n"
        fi
        if [ ${#feat_dirs[@]} -eq 0 ]; then
            LISTING_OUTPUT+="No feat directories found.\n\n"
            continue
        fi

        # Check cope counts
        check_result=()
        while IFS= read -r line; do
            check_result+=("$line")
        done < <(check_common_cope_count "${feat_dirs[@]}")

        common_cope_count=""
        valid_feat_dirs=()
        warnings=()
        parsing_warnings=false
        unequal_copes=false
        unequal_copes_tie=false

        for line in "${check_result[@]}"; do
            if [ "$parsing_warnings" = false ]; then
                case "$line" in
                    "UNEQUAL_COPES")
                        unequal_copes=true
                        parsing_warnings=true
                        ;;
                    "UNEQUAL_COPES_TIE")
                        unequal_copes_tie=true
                        parsing_warnings=true
                        ;;
                    "WARNINGS_START")
                        parsing_warnings=true
                        ;;
                    *)
                        if [ -z "$common_cope_count" ]; then
                            common_cope_count="$line"
                        else
                            valid_feat_dirs+=("$line")
                        fi
                        ;;
                esac
            else
                warnings+=("$line")
            fi
        done

        if [ "$unequal_copes" = true ] || [ "$unequal_copes_tie" = true ]; then
            LISTING_OUTPUT+="Warnings:\n"
            for warning in "${warnings[@]}"; do
                LISTING_OUTPUT+="  [Warning] $warning\n"
            done
            if [ "$unequal_copes_tie" = true ]; then
                LISTING_OUTPUT+="\nExcluding subject-session $subject:$session due to tie in cope counts.\n\n"
            else
                LISTING_OUTPUT+="\nExcluding subject-session $subject:$session due to insufficient runs with the same cope count.\n\n"
            fi
            continue
        fi

        if [ ${#valid_feat_dirs[@]} -gt 0 ]; then
            LISTING_OUTPUT+="Valid Feat Directories:\n"
            for feat_dir in "${valid_feat_dirs[@]}"; do
                trimmed="${feat_dir#$ANALYSIS_DIR_CHOOSEN/}"
                LISTING_OUTPUT+="  • $trimmed\n"
            done

            subject_session_keys+=("$key")
            subject_session_cope_counts+=("$common_cope_count")
            all_valid_feat_dirs+=("${valid_feat_dirs[@]}")

            if [ ${#warnings[@]} -gt 0 ]; then
                LISTING_OUTPUT+="\nWarnings:\n"
                for w in "${warnings[@]}"; do
                    LISTING_OUTPUT+="  [Warning] $w\n"
                done
            fi
            LISTING_OUTPUT+="\n"
        else
            LISTING_OUTPUT+="  - No valid feat directories after cope count check.\n\n"
        fi
    done
done

all_valid_feat_dirs=($(printf "%s\n" "${all_valid_feat_dirs[@]}" | sort))

# Print the listing to console
echo -e "$LISTING_OUTPUT"


###############################################################################
# Validation helpers
###############################################################################
is_valid_subject() {
    local subj="$1"
    array_contains "$subj" "${ALL_SUBJECTS[@]}"
    return $?
}
is_valid_session() {
    local sess="$1"
    array_contains "$sess" "${ALL_SESSIONS[@]}"
    return $?
}
subject_has_sessions() {
    local subj="$1"
    for pair in "${SUBJECT_SESSION_LIST[@]}"; do
        if [[ "$pair" == "${subj}|"* ]]; then
            return 0
        fi
    done
    return 1
}
is_valid_subject_session() {
    local subj="$1"
    local sess="$2"
    local pair="${subj}|${sess}"
    array_contains "$pair" "${SUBJECT_SESSION_LIST[@]}"
    return $?
}
is_valid_run() {
    local subj="$1"
    local sess="$2"
    local run_input="$3"
    local run_stripped="${run_input#0}"
    local rgx
    if [ -n "$sess" ]; then
        rgx=".*$subj/$sess/func/.*run-0*$run_stripped\.feat$"
    else
        rgx=".*$subj/func/.*run-0*$run_stripped\.feat$"
    fi
    for fdir in "${all_valid_feat_dirs[@]}"; do
        if [[ "$fdir" =~ $rgx ]]; then
            return 0
        fi
    done
    return 1
}

###############################################################################
# 3) Subject/Session/Run selection
###############################################################################
declare -a inclusion_map_keys=()
declare -a inclusion_map_values=()
declare -a exclusion_map_keys=()
declare -a exclusion_map_values=()

if [ ${#subject_inclusion_args[@]} -eq 0 ] && [ ${#subject_exclusion_args[@]} -eq 0 ]; then
    # Interactive prompt for includes/excludes
    echo "=== Subject, Session, and Run Selection ==="
    echo "Enter your selections (or press Enter for all)."
    echo
    echo "  Examples (for inclusion):  sub-01[:ses-02[:01,02]]"
    echo "  Use '-' to exclude. E.g.: -sub-02[:ses-03[:01,02]]"
    echo
    echo "Enter 'help' for usage info, or press Enter for no filters."
    echo
    echo -n "> "

    while true; do
        read selection_input
        if [ -z "$selection_input" ]; then
            break
        fi
        if [ "$selection_input" = "help" ]; then
            echo ""
            usage no-exit  # Prints usage and returns without exiting
            echo -n "> "
            continue
        fi

        IFS=' ' read -ra entries <<< "$selection_input"
        invalid_selections=()
        temp_incl_keys=()
        temp_incl_vals=()
        temp_excl_keys=()
        temp_excl_vals=()

        for selection in "${entries[@]}"; do
            exclude=false
            if [[ "$selection" == -* ]]; then
                exclude=true
                selection="${selection#-}"
            fi

            IFS=':' read -ra parts <<< "$selection"
            sel_subj=""
            sel_sess=""
            sel_runs=""

            case ${#parts[@]} in
                1)
                    # Could be just 'sub-01' or just 'ses-02'
                    if is_valid_subject "${parts[0]}"; then
                        sel_subj="${parts[0]}"
                    elif is_valid_session "${parts[0]}"; then
                        sel_sess="${parts[0]}"
                    else
                        invalid_selections+=("${parts[0]}")
                        continue
                    fi
                    ;;
                2)
                    # sub-01:ses-02 OR ses-02:01,02 OR sub-01:01,02 (no sessions)
                    if is_valid_subject "${parts[0]}"; then
                        sel_subj="${parts[0]}"
                        if is_valid_subject_session "$sel_subj" "${parts[1]}"; then
                            sel_sess="${parts[1]}"
                        else
                            if subject_has_sessions "$sel_subj"; then
                                invalid_selections+=("$selection")
                                continue
                            else
                                sel_runs="${parts[1]}"
                            fi
                        fi
                    elif is_valid_session "${parts[0]}"; then
                        sel_sess="${parts[0]}"
                        sel_runs="${parts[1]}"
                    else
                        invalid_selections+=("$selection")
                        continue
                    fi
                    ;;
                3)
                    # sub-01:ses-02:01,02
                    sel_subj="${parts[0]}"
                    sel_sess="${parts[1]}"
                    sel_runs="${parts[2]}"
                    if ! is_valid_subject_session "$sel_subj" "$sel_sess"; then
                        invalid_selections+=("$selection")
                        continue
                    fi
                    ;;
                *)
                    invalid_selections+=("$selection")
                    continue
                    ;;
            esac

            # Validate runs if specified
            if [ -n "$sel_runs" ] && [ -n "$sel_subj" ]; then
                IFS=',' read -ra runs_list <<< "$sel_runs"
                for run_val in "${runs_list[@]}"; do
                    if ! is_valid_run "$sel_subj" "$sel_sess" "$run_val"; then
                        invalid_selections+=("run-$run_val")
                    fi
                done
            fi

            if $exclude; then
                temp_excl_keys+=("${sel_subj}:${sel_sess}")
                temp_excl_vals+=("$sel_runs")
            else
                temp_incl_keys+=("${sel_subj}:${sel_sess}")
                temp_incl_vals+=("$sel_runs")
            fi
        done

        if [ ${#invalid_selections[@]} -gt 0 ]; then
            joined_invalid=$(printf ", %s" "${invalid_selections[@]}")
            joined_invalid="${joined_invalid:2}"
            echo "Invalid selections: $joined_invalid. Try again."
            echo -n "> "
        else
            inclusion_map_keys=("${temp_incl_keys[@]}")
            inclusion_map_values=("${temp_incl_vals[@]}")
            exclusion_map_keys=("${temp_excl_keys[@]}")
            exclusion_map_values=("${temp_excl_vals[@]}")
            break
        fi
    done
else
    # Non-interactive. Parse the arrays from CLI
    parse_selection_pattern() {
        local selection="$1"
        local exclude="$2"

        IFS=':' read -ra parts <<< "$selection"
        local sel_subj=""
        local sel_sess=""
        local sel_runs=""

        case ${#parts[@]} in
            1)
                if is_valid_subject "${parts[0]}"; then
                    sel_subj="${parts[0]}"
                elif is_valid_session "${parts[0]}"; then
                    sel_sess="${parts[0]}"
                else
                    echo "Warning: Invalid pattern '$selection' (not recognized as subject or session). Skipping."
                    return
                fi
                ;;
            2)
                if is_valid_subject "${parts[0]}"; then
                    sel_subj="${parts[0]}"
                    if is_valid_subject_session "$sel_subj" "${parts[1]}"; then
                        sel_sess="${parts[1]}"
                    else
                        if subject_has_sessions "$sel_subj"; then
                            echo "Warning: Invalid pattern '$selection'. Skipping."
                            return
                        else
                            sel_runs="${parts[1]}"
                        fi
                    fi
                elif is_valid_session "${parts[0]}"; then
                    sel_sess="${parts[0]}"
                    sel_runs="${parts[1]}"
                else
                    echo "Warning: Invalid pattern '$selection'. Skipping."
                    return
                fi
                ;;
            3)
                sel_subj="${parts[0]}"
                sel_sess="${parts[1]}"
                sel_runs="${parts[2]}"
                if ! is_valid_subject_session "$sel_subj" "$sel_sess"; then
                    echo "Warning: Invalid pattern '$selection' (no matching subject-session). Skipping."
                    return
                fi
                ;;
            *)
                echo "Warning: Invalid pattern '$selection'. Skipping."
                return
                ;;
        esac

        if [ -n "$sel_runs" ] && [ -n "$sel_subj" ]; then
            IFS=',' read -ra runs_list <<< "$sel_runs"
            for run_val in "${runs_list[@]}"; do
                if ! is_valid_run "$sel_subj" "$sel_sess" "$run_val"; then
                    echo "Warning: run '$run_val' not found for $sel_subj:$sel_sess. Skipping."
                fi
            done
        fi

        if [ "$exclude" = true ]; then
            exclusion_map_keys+=("${sel_subj}:${sel_sess}")
            exclusion_map_values+=("$sel_runs")
        else
            inclusion_map_keys+=("${sel_subj}:${sel_sess}")
            inclusion_map_values+=("$sel_runs")
        fi
    }

    for inc in "${subject_inclusion_args[@]}"; do
        parse_selection_pattern "$inc" false
    done
    for exc in "${subject_exclusion_args[@]}"; do
        parse_selection_pattern "$exc" true
    done
fi


###############################################################################
# 4) Task name (optional)
###############################################################################
final_task_name=""
if [ -n "$task_name_arg" ]; then
    final_task_name="$task_name_arg"
else
    # If purely non-interactive, skip prompting. If interactive, prompt:
    if [ "$used_cli_flags" = false ]; then
        # Means no CLI flags were used at all -> full interactive mode
        echo
        echo "=== Customize Output Filename (Optional) ==="
        echo "Enter a task name to include in the output directories (e.g., 'taskname')."
        echo -e "If left blank, output will use 'desc-fixed-effects.gfeat'.\n"
        echo -n "> "
        read user_input
        if [[ "$user_input" =~ ^[A-Za-z0-9_-]+$ ]]; then
            final_task_name="$user_input"
        else
            if [ -n "$user_input" ]; then
                echo "Invalid name. Will use default naming pattern (desc-fixed-effects)."
            fi
            final_task_name=""
        fi
    else
        # Non-interactive but no --task-name => just use default (no prompt)
        final_task_name=""
    fi
fi

###############################################################################
# 5) Z / cluster threshold
###############################################################################
use_z_thresh="$z_threshold_arg"
use_cluster_thresh="$cluster_p_threshold_arg"

if [ -z "$use_z_thresh" ] && [ "$used_cli_flags" = false ]; then
    # Interactive only if no CLI flags at all
    default_z=2.3
    echo
    echo "=== FEAT Thresholding Options ==="
    echo "Enter Z threshold (default $default_z):"
    echo -n "> "
    read z_threshold_input
    while [ -n "$z_threshold_input" ] && ! [[ "$z_threshold_input" =~ ^[0-9]*\.?[0-9]+$ ]]; do
        echo "Invalid numeric value. Try again."
        echo -n "> "
        read z_threshold_input
    done
    if [ -z "$z_threshold_input" ]; then
        use_z_thresh=$default_z
    else
        use_z_thresh="$z_threshold_input"
    fi
fi

# If still empty, set a default
[ -z "$use_z_thresh" ] && use_z_thresh=2.3

if [ -z "$use_cluster_thresh" ] && [ "$used_cli_flags" = false ]; then
    default_p=0.05
    echo
    echo "Enter Cluster P threshold (default $default_p):"
    echo -n "> "
    read cluster_p_threshold_input
    while [ -n "$cluster_p_threshold_input" ] && ! [[ "$cluster_p_threshold_input" =~ ^[0-9]*\.?[0-9]+$ ]]; do
        echo "Invalid numeric value. Try again."
        echo -n "> "
        read cluster_p_threshold_input
    done
    if [ -z "$cluster_p_threshold_input" ]; then
        use_cluster_thresh=$default_p
    else
        use_cluster_thresh="$cluster_p_threshold_input"
    fi
fi

# If still empty, set a default
[ -z "$use_cluster_thresh" ] && use_cluster_thresh=0.05

echo
echo "Using Z threshold: $use_z_thresh"
echo "Using Cluster P threshold: $use_cluster_thresh"


###############################################################################
# 6) Inclusion/exclusion logic
###############################################################################
should_include_subject_session() {
    local subject="$1"
    local session="$2"

    # Check exclusions
    for idx in "${!exclusion_map_keys[@]}"; do
        local excl_key="${exclusion_map_keys[$idx]}"
        local excl_runs="${exclusion_map_values[$idx]}"

        IFS=':' read -ra eparts <<< "$excl_key"
        local excl_subj="${eparts[0]}"
        local excl_sess="${eparts[1]}"

        # If matches subject or session with no runs => exclude entire session
        if [ -n "$excl_subj" ] && [ "$excl_subj" = "$subject" ]; then
            if [ -z "$excl_sess" ] || [ "$excl_sess" = "$session" ]; then
                if [ -z "$excl_runs" ]; then
                    return 1
                else
                    return 0
                fi
            fi
        fi

        if [ -z "$excl_subj" ] && [ -n "$excl_sess" ] && [ "$excl_sess" = "$session" ]; then
            if [ -z "$excl_runs" ]; then
                return 1
            else
                return 0
            fi
        fi
    done

    # If inclusion rules, must match at least one
    if [ ${#inclusion_map_keys[@]} -gt 0 ]; then
        local found_inclusion=false
        for idx in "${!inclusion_map_keys[@]}"; do
            local incl_key="${inclusion_map_keys[$idx]}"
            IFS=':' read -ra iparts <<< "$incl_key"
            local incl_subj="${iparts[0]}"
            local incl_sess="${iparts[1]}"

            if [ -n "$incl_subj" ] && [ "$incl_subj" != "$subject" ]; then
                continue
            fi
            if [ -n "$incl_sess" ] && [ "$incl_sess" != "$session" ]; then
                continue
            fi
            found_inclusion=true
            break
        done

        if ! $found_inclusion; then
            return 1
        fi
    fi

    return 0
}


###############################################################################
# 7) Confirm & run
###############################################################################
clear
echo
echo "=== Selections for Fixed Effects Analysis ==="

generated_design_files=()

for subject_dir in "${subject_dirs[@]}"; do
    subject=$(basename "$subject_dir")

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

    session_dirs=($(find "$subject_dir" -mindepth 1 -maxdepth 1 -type d \( "${FIND_SESSION_EXPR[@]}" \) 2>/dev/null | sort))
    if [ ${#session_dirs[@]} -eq 0 ] && [ -d "$subject_dir/func" ]; then
        session_dirs=("$subject_dir")
    fi

    for session_dir in "${session_dirs[@]}"; do
        if [ "$session_dir" = "$subject_dir" ]; then
            session=""
        else
            session=$(basename "$session_dir")
        fi

        if ! should_include_subject_session "$subject" "$session"; then
            echo
            if [ -z "$session" ]; then
                echo "Subject: $subject | Session: None => Excluded based on selections."
            else
                echo "Subject: $subject | Session: $session => Excluded based on selections."
            fi
            continue
        fi

        sel_key="$subject:$session"

        # Pull specific included runs
        specific_runs=""
        for idx in "${!inclusion_map_keys[@]}"; do
            if [ "${inclusion_map_keys[$idx]}" = "$sel_key" ]; then
                specific_runs="${inclusion_map_values[$idx]}"
                break
            fi
        done

        # Pull excluded runs
        exclude_runs=""
        for idx in "${!exclusion_map_keys[@]}"; do
            if [ "${exclusion_map_keys[$idx]}" = "$sel_key" ]; then
                exclude_runs="${exclusion_map_values[$idx]}"
                break
            fi
        done

        feat_dirs=()
        for d in "${all_valid_feat_dirs[@]}"; do
            if [ -n "$session" ]; then
                if [[ "$d" == *"/$subject/$session/"* ]]; then
                    feat_dirs+=("$d")
                fi
            else
                if [[ "$d" == *"/$subject/func/"* ]] && [[ "$d" != *"/$subject/ses-"* ]]; then
                    feat_dirs+=("$d")
                fi
            fi
        done

        if [ -n "$specific_runs" ]; then
            selected_feat_dirs=()
            IFS=',' read -ra sruns <<< "$specific_runs"
            for r in "${sruns[@]}"; do
                r_no0=$(echo "$r" | sed 's/^0*//')
                rgx=".*run-0*${r_no0}\.feat$"
                for fdir in "${feat_dirs[@]}"; do
                    [[ "$fdir" =~ $rgx ]] && selected_feat_dirs+=("$fdir")
                done
            done
            feat_dirs=("${selected_feat_dirs[@]}")
        fi

        if [ -n "$exclude_runs" ]; then
            IFS=',' read -ra eruns <<< "$exclude_runs"
            for r in "${eruns[@]}"; do
                r_no0=$(echo "$r" | sed 's/^0*//')
                rgx=".*run-0*${r_no0}\.feat$"
                for i2 in "${!feat_dirs[@]}"; do
                    if [[ "${feat_dirs[$i2]}" =~ $rgx ]]; then
                        unset 'feat_dirs[$i2]'
                    fi
                done
            done
            feat_dirs=("${feat_dirs[@]}")
        fi

        feat_dirs=($(printf "%s\n" "${feat_dirs[@]}" | sort))
        echo
        if [ -z "$session" ]; then
            echo "Subject: $subject | Session: None"
        else
            echo "Subject: $subject | Session: $session"
        fi
        echo "----------------------------------------"

        if [ ${#feat_dirs[@]} -eq 0 ]; then
            echo "  - No matching directories found after filtering."
            continue
        elif [ ${#feat_dirs[@]} -lt 2 ]; then
            echo "  - Only one run found; need >= 2 for fixed effects. Skipping."
            continue
        fi

        echo "Selected Feat Directories:"
        for f in "${feat_dirs[@]}"; do
            echo "  • ${f#$ANALYSIS_DIR_CHOOSEN/}"
        done

        subject_session_key="${subject}:${session}"
        common_cope_count=""
        array_length=${#subject_session_keys[@]}
        idx=0
        while [ $idx -lt $array_length ]; do
            if [ "${subject_session_keys[$idx]}" = "$subject_session_key" ]; then
                common_cope_count="${subject_session_cope_counts[$idx]}"
                break
            fi
            idx=$((idx+1))
        done

        if [ -z "$common_cope_count" ]; then
            echo "No common cope count found for $subject_session_key. Skipping."
            continue
        fi

        # Output filename
        if [ -n "$final_task_name" ]; then
            if [ -n "$session" ]; then
                output_filename="${subject}_${session}_task-${final_task_name}_desc-fixed-effects"
            else
                output_filename="${subject}_task-${final_task_name}_desc-fixed-effects"
            fi
        else
            if [ -n "$session" ]; then
                output_filename="${subject}_${session}_desc-fixed-effects"
            else
                output_filename="${subject}_desc-fixed-effects"
            fi
        fi

        if [ -n "$session" ]; then
            output_path="$LEVEL_2_ANALYSIS_DIR/$subject/$session/$output_filename"
        else
            output_path="$LEVEL_2_ANALYSIS_DIR/$subject/$output_filename"
        fi

        echo -e "\nOutput Directory:"
        echo "  ${output_path}.gfeat"

        if [ -d "${output_path}.gfeat" ]; then
            echo "  - [Notice] Output directory already exists. Skipping."
            continue
        fi

        # Generate design file
        "$GENERATE_DESIGN_SCRIPT" \
            "$output_path" \
            "$common_cope_count" \
            "$use_z_thresh" \
            "$use_cluster_thresh" \
            "${feat_dirs[@]}"

        echo -e "\nGenerated FEAT design file at:" >> $LOGFILE
        echo "  $output_path/modified_desc-fixedEffects_design.fsf" >> $LOGFILE
        echo "" >> $LOGFILE

        generated_design_files+=("$output_path/modified_desc-fixedEffects_design.fsf")
    done
done

if [ ${#generated_design_files[@]} -eq 0 ]; then
    echo
    echo "=== No new analyses to run. All specified outputs already exist or were excluded. ==="
    echo
    exit 0
fi

# --------------------------------------------------------------------------
# Press Enter to proceed or skip if non-interactive
# --------------------------------------------------------------------------
trap_ctrl_c() {
    echo
    echo "Interrupted. Removing partial design dirs..."
    dirs_to_remove=()
    for design_file in "${generated_design_files[@]}"; do
        design_dir="$(dirname "$design_file")"
        [ -d "$design_dir" ] && dirs_to_remove+=("$design_dir")
    done
    for d in "${dirs_to_remove[@]}"; do
        rm -rf "$d"
    done
    if [ ${#dirs_to_remove[@]} -gt 0 ]; then
        echo "Removed these incomplete directories:"
        for d in "${dirs_to_remove[@]}"; do
            echo "- ${d#$ANALYSIS_DIR_CHOOSEN/}"
        done
    fi
    exit 1
}
trap 'trap_ctrl_c' SIGINT

if [ "$used_cli_flags" = false ]; then
    echo
    echo "Press Enter/Return to proceed with second-level FEAT, or Ctrl+C to cancel."
    read -r
    trap - SIGINT
else
    echo
    echo "[Non-interactive mode] Starting second-level FEAT analysis without prompt." >> $LOGFILE
fi

echo
echo "=== Running Fixed Effects ==="

for design_file in "${generated_design_files[@]}"; do
    echo
    echo "--- Processing Design File ---"
    echo "Temporary design file: "
    echo "  ${design_file#$ANALYSIS_DIR_CHOOSEN/}"
    feat "$design_file"

    design_dir="$(dirname "$design_file")"
    echo -e "\nFinished FEAT. Removing temporary design directory."
    echo "  ${design_dir#$ANALYSIS_DIR_CHOOSEN/}" >> $LOGFILE
    rm -rf "$design_dir"
    echo "Complete."
done

echo -e "\n=== All processing complete. Please check $LEVEL_2_ANALYSIS_DIR for outputs. ==="
echo


###############################################################################
# 8) Create/Update dataset_description.json
###############################################################################
if [ ! -f "$CREATE_DS_DESC_SCRIPT" ]; then
    echo "[Notice] create_dataset_description.sh not found at $CREATE_DS_DESC_SCRIPT." >> $LOGFILE
    echo "Skipping dataset_description.json creation." >> $LOGFILE
    exit 0
fi

FSL_VERSION="Unknown"
if [ -n "$FSLDIR" ] && [ -f "$FSLDIR/etc/fslversion" ]; then
    FSL_VERSION=$(cat "$FSLDIR/etc/fslversion" | cut -d'%' -f1)
fi

# Fix or append "Name=FSL,Version=..." if missing, reorder with parse_generatedby
for i in "${!L2_GENERATEDBY[@]}"; do
  entry="${L2_GENERATEDBY[$i]}"

  # Calls parse_generatedby() function to split out Name, Version, Description
  parsed="$(parse_generatedby "$entry")"
  IFS='|' read -r name_val version_val desc_val <<< "$parsed"

  # If the name is "FSL" but version is empty, fill it in
  if [[ "$name_val" == "FSL" && -z "$version_val" ]]; then
    version_val="$FSL_VERSION"
  fi

  # Rebuild in the correct order: Name=...,Version=...,Description=...
  new_entry="Name=$name_val"
  [[ -n "$version_val" ]] && new_entry="$new_entry,Version=$version_val"
  [[ -n "$desc_val" ]]    && new_entry="$new_entry,Description=$desc_val"

  L2_GENERATEDBY[$i]="$new_entry"
done

# Convert array to multiple --generatedby flags
generatedby_args=()
for entry in "${L2_GENERATEDBY[@]}"; do
    generatedby_args+=( "--generatedby" "$entry" )
done

# Call create_dataset_description.sh
# Create dataset_description.json in top-level
"$CREATE_DS_DESC_SCRIPT" \
    --analysis-dir "$LEVEL_2_ANALYSIS_DIR" \
    --ds-name "$L2_NAME" \
    --dataset-type "$L2_DATASET_TYPE" \
    --description "$L2_DESCRIPTION" \
    --bids-version "$BIDS_VERSION" \
    "${generatedby_args[@]}"

exit 0
