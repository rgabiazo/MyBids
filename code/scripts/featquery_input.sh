#!/usr/bin/env bash
###############################################################################
# featquery_input.sh
#
# Purpose:
#   Interactively choose FEAT directories and ROI masks then call
#   run_featquery.sh with the selections.
#
# Usage:
#   featquery_input.sh
#
# Usage Examples:
#   ./featquery_input.sh
#
# Options:
#   None (interactive script)
#
# Requirements:
#   bash and FSL installed
#
# Notes:
#   Logs choices to code/logs and supports lower- and higher-level FEAT
#   directories.
#
###############################################################################

# ------------------------------------------------------------------------------
# Set up environment and logging
# ------------------------------------------------------------------------------
script_dir="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(dirname "$(dirname "$script_dir")")"


LOG_DIR="$BASE_DIR/code/logs"
mkdir -p "$LOG_DIR"
LOGFILE="$LOG_DIR/$(basename "$0" .sh)_$(date +'%Y%m%d_%H%M%S').log"

# Redirect stdout & stderr to both the console AND the log file
exec > >(tee -a "$LOGFILE") 2>&1

# Define paths to analysis directories
LEVEL_1_ANALYSIS_BASE_DIR="$BASE_DIR/derivatives/fsl/level-1"
LEVEL_2_ANALYSIS_BASE_DIR="$BASE_DIR/derivatives/fsl/level-2"
LEVEL_3_ANALYSIS_BASE_DIR="$BASE_DIR/derivatives/fsl/level-3"

# ------------------------------------------------------------------------------
# Global arrays and variables
# ------------------------------------------------------------------------------
ANALYSIS_DIRS=()
SUBJECTS=()
DIRECTORIES=()
SESSIONS=()
DIR_TYPES=()

SELECTED_ANALYSIS_DIR=""
SELECTED_SESSION=""
CURRENT_INPUT_TYPE=""

FINAL_DIRS=()

# Arrays for ROI selection
ROI_SELECTIONS=()
ROI_MASK_SELECTIONS=()

# ------------------------------------------------------------------------------
# Functions
# ------------------------------------------------------------------------------

# ----------------------------------------------------------------------
# find_lower_level_analysis_dirs
# ----------------------------------------------------------------------
find_lower_level_analysis_dirs() {
    local base_dir="$1"
    ANALYSIS_DIRS=()

    while IFS= read -r -d $'\0' dir; do
        if find "$dir" -type d -name "*.feat" -print -quit | grep -q .; then
            ANALYSIS_DIRS+=("$dir")
        fi
    done < <(find "$base_dir" -mindepth 1 -maxdepth 1 -type d -iname "*analysis*" -print0 2>/dev/null)
}

# ----------------------------------------------------------------------
# find_higher_level_analysis_dirs
# ----------------------------------------------------------------------
find_higher_level_analysis_dirs() {
    local base_dir="$1"
    ANALYSIS_DIRS=()

    while IFS= read -r -d $'\0' dir; do
        if find "$dir" -type d -name "*.gfeat" -print -quit | grep -q .; then
            ANALYSIS_DIRS+=("$dir")
        elif [[ "$(basename "$dir")" == *"fixed-effects"* ]]; then
            ANALYSIS_DIRS+=("$dir")
        fi
    done < <(find "$base_dir" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)
}

# ----------------------------------------------------------------------
# find_sessions_in_dir
# ----------------------------------------------------------------------
find_sessions_in_dir() {
    local analysis_dir="$1"
    local session_dirs=()
    local session_names=()

    local SESSION_NAME_PATTERNS=("ses-*" "session-*" "ses_*" "session_*" "baseline" "endpoint")
    local FIND_SESSION_EXPR=()
    local first_session_pattern=true
    for pattern in "${SESSION_NAME_PATTERNS[@]}"; do
        if $first_session_pattern; then
            FIND_SESSION_EXPR+=( -name "$pattern" )
            first_session_pattern=false
        else
            FIND_SESSION_EXPR+=( -o -name "$pattern" )
        fi
    done

    while IFS= read -r -d $'\0' sdir; do
        session_dirs+=("$sdir")
    done < <(find "$analysis_dir" -type d \( "${FIND_SESSION_EXPR[@]}" \) -print0 2>/dev/null)

    IFS=$'\n' session_dirs=($(printf "%s\n" "${session_dirs[@]}" | sort -u))
    unset IFS

    for sdir in "${session_dirs[@]}"; do
        local bname
        bname=$(basename "$sdir")
        if [[ ! " ${session_names[*]} " =~ " ${bname} " ]]; then
            session_names+=("$bname")
        fi
    done

    for s in "${session_names[@]}"; do
        echo "$s"
    done
}

# ----------------------------------------------------------------------
# collect_subjects_and_feat
# ----------------------------------------------------------------------
collect_subjects_and_feat() {
    local analysis_dir="$1"
    local session_name="$2"
    local input_type="$3"

    # Re-init arrays each time
    SUBJECTS=()
    DIRECTORIES=()
    SESSIONS=()
    DIR_TYPES=()

    local SUBJECT_NAME_PATTERNS=("sub-*" "subject-*" "pilot-*" "subj-*" "subjpilot-*")
    local FIND_SUBJECT_EXPR=()
    local first_pattern=true
    for pattern in "${SUBJECT_NAME_PATTERNS[@]}"; do
        if $first_pattern; then
            FIND_SUBJECT_EXPR+=( -name "$pattern" )
            first_pattern=false
        else
            FIND_SUBJECT_EXPR+=( -o -name "$pattern" )
        fi
    done

    local subject_dirs=()
    while IFS= read -r -d $'\0' sdir; do
        subject_dirs+=("$sdir")
    done < <(find "$analysis_dir" -mindepth 1 -maxdepth 1 -type d \( "${FIND_SUBJECT_EXPR[@]}" \) -print0 2>/dev/null)

    IFS=$'\n' subject_dirs=($(printf "%s\n" "${subject_dirs[@]}" | sort -u))
    unset IFS

    for sdir in "${subject_dirs[@]}"; do
        local subj
        subj=$(basename "$sdir")

        local search_dir
        local subj_session=""
        if [ -n "$session_name" ] && [ -d "$sdir/$session_name" ]; then
            search_dir="$sdir/$session_name"
            subj_session="$session_name"
        else
            search_dir="$sdir"
        fi

        local dir_list=()
        if [ "$input_type" == "lower" ]; then
            while IFS= read -r -d $'\0' fdir; do
                dir_list+=("$fdir")
            done < <(find "$search_dir" -type d -name "*.feat" -mindepth 1 -maxdepth 2 -print0 2>/dev/null)
        else
            while IFS= read -r -d $'\0' gdir; do
                dir_list+=("$gdir")
            done < <(find "$search_dir" -type d \( -name "*.gfeat" -o -iname "*fixed-effects*" \) -mindepth 1 -maxdepth 2 -print0 2>/dev/null)
        fi

        if [ ${#dir_list[@]} -eq 0 ]; then
            continue
        fi

        IFS=$'\n' dir_list=($(printf "%s\n" "${dir_list[@]}" | sort -u))
        unset IFS

        local dirs_str
        dirs_str=$(printf "::%s" "${dir_list[@]}")
        dirs_str="${dirs_str:2}"

        SUBJECTS+=( "$subj" )
        DIRECTORIES+=( "$dirs_str" )
        SESSIONS+=( "$subj_session" )
        DIR_TYPES+=( "$input_type" )
    done
}

# ----------------------------------------------------------------------
# display_confirmed_selections
# ----------------------------------------------------------------------
display_confirmed_selections() {
    clear
    local session_name="$1"
    echo -e "\n=== Confirm Your Selections for FEATQUERY ==="
    if [ -z "$session_name" ]; then
        echo "Session: None"
    else
        echo "Session: $session_name"
    fi
    echo

    local sorted_subjects
    IFS=$'\n' sorted_subjects=($(printf "%s\n" "${SUBJECTS[@]}" | sort -u))
    unset IFS

    for subj in "${sorted_subjects[@]}"; do
        local directories_str=""
        local subj_session=""
        local dir_type=""

        for idx in "${!SUBJECTS[@]}"; do
            if [ "${SUBJECTS[$idx]}" == "$subj" ]; then
                directories_str="${DIRECTORIES[$idx]}"
                subj_session="${SESSIONS[$idx]}"
                dir_type="${DIR_TYPES[$idx]}"
                break
            fi
        done

        IFS='::' read -ra dir_array <<< "$directories_str"

        local disp_session="${subj_session:-}"
        [ -z "$disp_session" ] && disp_session="None"
        echo "Subject: $subj | Session: $disp_session"
        echo "----------------------------------------"
        if [ "$dir_type" == "higher" ]; then
            echo "Higher-level Feat Directory:"
        else
            echo "Selected Feat Directory:"
        fi
        for dd in "${dir_array[@]}"; do
            [ -n "$dd" ] && echo "  - ${dd#$BASE_DIR/}"
        done
        echo
    done

    echo "============================================"
    echo
}

# ----------------------------------------------------------------------
# remove_subjects
# ----------------------------------------------------------------------
remove_subjects() {
    local removal_string="$1"
    read -ra tokens <<< "$removal_string"

    if [ ${#tokens[@]} -lt 2 ]; then
        echo -e "\nError: No subjects provided to remove. Please try again."
        return
    fi

    local to_remove=("${tokens[@]:1}")
    local invalid_remove=false

    for sub in "${to_remove[@]}"; do
        if ! printf '%s\n' "${SUBJECTS[@]}" | grep -qx "$sub"; then
            echo -e "\nError: Subject '$sub' is not currently selected."
            invalid_remove=true
            break
        fi
    done

    if $invalid_remove; then
        return
    fi

    local new_subjects=()
    local new_directories=()
    local new_sessions=()
    local new_types=()

    for idx in "${!SUBJECTS[@]}"; do
        local keep_subject=true
        for rsub in "${to_remove[@]}"; do
            if [ "${SUBJECTS[$idx]}" == "$rsub" ]; then
                keep_subject=false
                break
            fi
        done
        if $keep_subject; then
            new_subjects+=("${SUBJECTS[$idx]}")
            new_directories+=("${DIRECTORIES[$idx]}")
            new_sessions+=("${SESSIONS[$idx]}")
            new_types+=("${DIR_TYPES[$idx]}")
        fi
    done

    SUBJECTS=("${new_subjects[@]}")
    DIRECTORIES=("${new_directories[@]}")
    SESSIONS=("${new_sessions[@]}")
    DIR_TYPES=("${new_types[@]}")
}

# ----------------------------------------------------------------------
# remove_existing_subject_entries
# ----------------------------------------------------------------------
remove_existing_subject_entries() {
    local subject_to_remove="$1"

    local new_subjects=()
    local new_directories=()
    local new_sessions=()
    local new_types=()

    for idx in "${!SUBJECTS[@]}"; do
        if [ "${SUBJECTS[$idx]}" != "$subject_to_remove" ]; then
            new_subjects+=("${SUBJECTS[$idx]}")
            new_directories+=("${DIRECTORIES[$idx]}")
            new_sessions+=("${SESSIONS[$idx]}")
            new_types+=("${DIR_TYPES[$idx]}")
        fi
    done

    SUBJECTS=("${new_subjects[@]}")
    DIRECTORIES=("${new_directories[@]}")
    SESSIONS=("${new_sessions[@]}")
    DIR_TYPES=("${new_types[@]}")
}

# ----------------------------------------------------------------------
# handle_edit
# ----------------------------------------------------------------------
handle_edit() {
    echo
    echo "Please select analysis level for input directories:"
    echo
    echo "1) Inputs are lower-level FEAT directories"
    echo "2) Inputs are higher-level .gfeat directories"
    echo "3) Cancel"
    echo

    while true; do
        read -p "Please enter your choice [1/2/3]: " edit_choice

        if ! [[ "$edit_choice" =~ ^[0-9]+$ ]]; then
            echo "Invalid input. Please enter 1, 2, or 3."
            continue
        fi
        if (( edit_choice < 1 || edit_choice > 3 )); then
            echo "Invalid selection. Please try again."
            continue
        fi

        case "$edit_choice" in
            1)
                edit_lower_level
                return
                ;;
            2)
                edit_higher_level
                return
                ;;
            3)
                echo "Cancel editing..."
                return
                ;;
        esac
    done
}

# ----------------------------------------------------------------------
# edit_lower_level
# ----------------------------------------------------------------------
edit_lower_level() {
    local ADD_INPUT_TYPE="lower"
    echo -e "\n[INFO] You selected lower-level FEAT directories." >> "$LOGFILE"
    find_lower_level_analysis_dirs "$LEVEL_1_ANALYSIS_BASE_DIR"

    if [ ${#ANALYSIS_DIRS[@]} -eq 0 ]; then
        echo "No analysis directories found. Returning..."
        return
    fi

    echo -e "\nAvailable lower-level directories in level-1:\n"
    for idx in "${!ANALYSIS_DIRS[@]}"; do
        echo "$((idx + 1))) ${ANALYSIS_DIRS[$idx]#$BASE_DIR/}"
    done
    echo

    local analysis_valid=false
    local analysis_choice=""
    while [ "$analysis_valid" = false ]; do
        read -p "Please select an analysis directory by number: " analysis_choice
        if ! [[ "$analysis_choice" =~ ^[0-9]+$ ]]; then
            echo "Invalid input. Please enter a valid number."
            continue
        fi
        if (( analysis_choice < 1 || analysis_choice > ${#ANALYSIS_DIRS[@]} )); then
            echo "Invalid selection. Please try again."
            continue
        fi
        analysis_valid=true
    done

    local ADD_ANALYSIS_DIR="${ANALYSIS_DIRS[$((analysis_choice - 1))]}"
    echo -e "\nAnalysis directory selected:"
    echo "  $ADD_ANALYSIS_DIR"

    mapfile -t session_names < <(find_sessions_in_dir "$ADD_ANALYSIS_DIR")
    if [ ${#session_names[@]} -eq 0 ]; then
        echo "No sessions found. Returning..."
        return
    fi

    local ADD_SESSION
    if [ ${#session_names[@]} -eq 1 ]; then
        ADD_SESSION="${session_names[0]}"
        echo -e "\nOnly one session found: $ADD_SESSION"
    else
        echo -e "\nAvailable sessions:\n"
        for idx in "${!session_names[@]}"; do
            echo "$((idx + 1))) ${session_names[$idx]}"
        done
        echo

        local session_valid=false
        while [ "$session_valid" = false ]; do
            read -p "Please select a session by number: " session_choice
            if ! [[ "$session_choice" =~ ^[0-9]+$ ]]; then
                echo "Invalid input. Please enter a valid number."
                continue
            fi
            if (( session_choice < 1 || session_choice > ${#session_names[@]} )); then
                echo "Invalid selection. Please try again."
                continue
            fi
            session_valid=true
            ADD_SESSION="${session_names[$((session_choice - 1))]}"
        done
        echo -e "\nYou have selected session: $ADD_SESSION" >> "$LOGFILE"
    fi

    # Build an expression to find "sub-" (or similar) directories
    local SUBJECT_NAME_PATTERNS=("sub-*" "subject-*" "pilot-*" "subj-*" "subjpilot-*")
    local FIND_SUBJECT_EXPR=()
    local fp=true
    for pattern in "${SUBJECT_NAME_PATTERNS[@]}"; do
        if $fp; then
            FIND_SUBJECT_EXPR+=( -name "$pattern" )
            fp=false
        else
            FIND_SUBJECT_EXPR+=( -o -name "$pattern" )
        fi
    done

    # Collect only subjects that actually have this session folder
    local ADD_SUBJECT_DIRS=()
    while IFS= read -r -d $'\0' sdir; do
        # Check if sdir/ses-XX is present
        if [ -d "$sdir/$ADD_SESSION" ]; then
            ADD_SUBJECT_DIRS+=("$sdir")
        fi
    done < <(find "$ADD_ANALYSIS_DIR" -mindepth 1 -maxdepth 1 -type d \( "${FIND_SUBJECT_EXPR[@]}" \) -print0 2>/dev/null)

    IFS=$'\n' ADD_SUBJECT_DIRS=($(printf "%s\n" "${ADD_SUBJECT_DIRS[@]}" | sort -u))
    unset IFS

    if [ ${#ADD_SUBJECT_DIRS[@]} -eq 0 ]; then
        echo "No subject directories found (with session $ADD_SESSION). Returning..."
        return
    fi

    echo -e "\nSelect subject to edit:\n"
    local idx_counter=1
    declare -A MAP_INDEX_TO_SUBJECTDIR
    for sdir in "${ADD_SUBJECT_DIRS[@]}"; do
        local sub
        sub=$(basename "$sdir")
        # Align display: e.g. " 1)  sub-02"
        printf " %2d)  %s\n" "$idx_counter" "$sub"
        MAP_INDEX_TO_SUBJECTDIR[$idx_counter]="$sdir"
        idx_counter=$((idx_counter+1))
    done
    echo

    local sub_choice=""
    local valid_sub_choice=false
    while [ "$valid_sub_choice" = false ]; do
        read -p "Please enter your choice: " sub_choice
        if ! [[ "$sub_choice" =~ ^[0-9]+$ ]]; then
            echo "Invalid input. Please enter a valid number."
            continue
        fi
        if (( sub_choice < 1 || sub_choice >= idx_counter )); then
            echo "Invalid selection. Please try again."
            continue
        fi
        valid_sub_choice=true
    done

    local ADD_SUBJECT_DIR="${MAP_INDEX_TO_SUBJECTDIR[$sub_choice]}"
    local ADD_SUBJECT
    ADD_SUBJECT=$(basename "$ADD_SUBJECT_DIR")

    remove_existing_subject_entries "$ADD_SUBJECT"

    echo -e "\nListing directories for $ADD_SUBJECT in session $ADD_SESSION..." >> "$LOGFILE"
    echo
    echo "Select the directory(ies) to add or replace, separated by spaces."
    echo

    local potential_dirs=()
    while IFS= read -r -d $'\0' fdir; do
        potential_dirs+=("$fdir")
    done < <(find "$ADD_SUBJECT_DIR/$ADD_SESSION" -type d -name "*.feat" -mindepth 1 -maxdepth 2 -print0 2>/dev/null)

    if [ ${#potential_dirs[@]} -eq 0 ]; then
        echo "No valid .feat directories found for $ADD_SUBJECT in $ADD_SESSION. Returning..."
        return
    fi

    IFS=$'\n' potential_dirs=($(printf "%s\n" "${potential_dirs[@]}" | sort))
    unset IFS

    local idxp=1
    declare -A MAP_INDEX_TO_FEAT
    for dd in "${potential_dirs[@]}"; do
        printf " %2d)  %s\n" "$idxp" "${dd#$BASE_DIR/}"
        MAP_INDEX_TO_FEAT[$idxp]="$dd"
        idxp=$((idxp+1))
    done

    local user_input=""
    local valid_feat_choice=false
    local chosen_dirs=()

    echo -e "\nPlease enter your choice [e.g. 1 2 3] or press Enter for all: "
    while [ "$valid_feat_choice" = false ]; do
        read -p "> " user_input

        if [ -z "$user_input" ]; then
            chosen_dirs=("${potential_dirs[@]}")
            valid_feat_choice=true
            break
        fi

        read -ra input_tokens <<< "$user_input"
        local invalid_index=false
        local temp_dirs=()

        for token in "${input_tokens[@]}"; do
            if ! [[ "$token" =~ ^[0-9]+$ ]]; then
                echo "Invalid input: '$token' is not a number. Please try again."
                invalid_index=true
                break
            fi
            if (( token < 1 || token >= idxp )); then
                echo "Invalid input: '$token' is out of range. Please try again."
                invalid_index=true
                break
            fi
            temp_dirs+=( "${MAP_INDEX_TO_FEAT[$token]}" )
        done

        if $invalid_index; then
            continue
        else
            chosen_dirs=("${temp_dirs[@]}")
            valid_feat_choice=true
        fi
    done

    local new_dirs_str
    new_dirs_str=$(printf "::%s" "${chosen_dirs[@]}")
    new_dirs_str="${new_dirs_str:2}"

    SUBJECTS+=( "$ADD_SUBJECT" )
    DIRECTORIES+=( "$new_dirs_str" )
    SESSIONS+=( "$ADD_SESSION" )
    DIR_TYPES+=( "$ADD_INPUT_TYPE" )

    echo -e "\n[EDIT] Updated selection for subject $ADD_SUBJECT, session $ADD_SESSION."
}


# ----------------------------------------------------------------------
# edit_higher_level
# ----------------------------------------------------------------------
edit_higher_level() {
    local ADD_INPUT_TYPE="higher"
    echo -e "\n[INFO] You selected higher-level .gfeat directories.\n" >> "$LOGFILE"

    find_higher_level_analysis_dirs "$LEVEL_2_ANALYSIS_BASE_DIR"
    if [ ${#ANALYSIS_DIRS[@]} -eq 0 ]; then
        echo "No higher-level directories found. Returning..."
        return
    fi

    echo -e "\nAvailable higher-level .gfeat/fixed-effects directories in level-2:\n"
    for idx in "${!ANALYSIS_DIRS[@]}"; do
        echo "$((idx + 1))) ${ANALYSIS_DIRS[$idx]#$BASE_DIR/}"
    done
    echo

    local analysis_valid=false
    local analysis_choice=""
    while [ "$analysis_valid" = false ]; do
        read -p "Please select an analysis directory by number: " analysis_choice
        if ! [[ "$analysis_choice" =~ ^[0-9]+$ ]]; then
            echo "Invalid input. Please enter a valid number."
            continue
        fi
        if (( analysis_choice < 1 || analysis_choice > ${#ANALYSIS_DIRS[@]} )); then
            echo "Invalid selection. Please try again."
            continue
        fi
        analysis_valid=true
    done

    local ADD_ANALYSIS_DIR="${ANALYSIS_DIRS[$((analysis_choice - 1))]}"
    echo -e "\nAnalysis directory selected:"
    echo "  $ADD_ANALYSIS_DIR"

    mapfile -t session_names < <(find_sessions_in_dir "$ADD_ANALYSIS_DIR")
    if [ ${#session_names[@]} -eq 0 ]; then
        echo "No sessions found. Returning..."
        return
    fi

    local ADD_SESSION
    if [ ${#session_names[@]} -eq 1 ]; then
        ADD_SESSION="${session_names[0]}"
        echo -e "\nOnly one session found: $ADD_SESSION"
    else
        echo -e "\nAvailable sessions:\n"
        for idx in "${!session_names[@]}"; do
            echo "$((idx + 1))) ${session_names[$idx]}"
        done
        echo

        local session_valid=false
        while [ "$session_valid" = false ]; do
            read -p "Please select a session by number: " session_choice
            if ! [[ "$session_choice" =~ ^[0-9]+$ ]]; then
                echo "Invalid input. Please enter a valid number."
                continue
            fi
            if (( session_choice < 1 || session_choice > ${#session_names[@]} )); then
                echo "Invalid selection. Please try again."
                continue
            fi
            session_valid=true
            ADD_SESSION="${session_names[$((session_choice - 1))]}"
        done
        echo -e "\nYou have selected session: $ADD_SESSION" >> "$LOGFILE"
    fi

    local SUBJECT_NAME_PATTERNS=("sub-*" "subject-*" "pilot-*" "subj-*" "subjpilot-*")
    local FIND_SUBJECT_EXPR=()
    local fp=true
    for pattern in "${SUBJECT_NAME_PATTERNS[@]}"; do
        if $fp; then
            FIND_SUBJECT_EXPR+=( -name "$pattern" )
            fp=false
        else
            FIND_SUBJECT_EXPR+=( -o -name "$pattern" )
        fi
    done

    # Collect only subjects that have this chosen session
    local ADD_SUBJECT_DIRS=()
    while IFS= read -r -d $'\0' sdir; do
        if [ -d "$sdir/$ADD_SESSION" ]; then
            ADD_SUBJECT_DIRS+=("$sdir")
        fi
    done < <(find "$ADD_ANALYSIS_DIR" -mindepth 1 -maxdepth 1 -type d \( "${FIND_SUBJECT_EXPR[@]}" \) -print0 2>/dev/null)

    IFS=$'\n' ADD_SUBJECT_DIRS=($(printf "%s\n" "${ADD_SUBJECT_DIRS[@]}" | sort -u))
    unset IFS

    if [ ${#ADD_SUBJECT_DIRS[@]} -eq 0 ]; then
        echo "No subject directories found (with session $ADD_SESSION). Returning..."
        return
    fi

    echo -e "\nSelect subject to edit:\n"
    local idx_counter=1
    declare -A MAP_INDEX_TO_SUBJECTDIR
    for sdir in "${ADD_SUBJECT_DIRS[@]}"; do
        local sub
        sub=$(basename "$sdir")
        printf " %2d)  %s\n" "$idx_counter" "$sub"
        MAP_INDEX_TO_SUBJECTDIR[$idx_counter]="$sdir"
        idx_counter=$((idx_counter+1))
    done
    echo

    local sub_choice=""
    local valid_sub_choice=false
    while [ "$valid_sub_choice" = false ]; do
        read -p "Please enter your choice: " sub_choice
        if ! [[ "$sub_choice" =~ ^[0-9]+$ ]]; then
            echo "Invalid input. Please enter a valid number."
            continue
        fi
        if (( sub_choice < 1 || sub_choice >= idx_counter )); then
            echo "Invalid selection. Please try again."
            continue
        fi
        valid_sub_choice=true
    done

    local ADD_SUBJECT_DIR="${MAP_INDEX_TO_SUBJECTDIR[$sub_choice]}"
    local ADD_SUBJECT
    ADD_SUBJECT=$(basename "$ADD_SUBJECT_DIR")

    remove_existing_subject_entries "$ADD_SUBJECT"

    echo -e "\nListing directories for $ADD_SUBJECT in session $ADD_SESSION..." >> "$LOGFILE"

    local potential_dirs=()
    while IFS= read -r -d $'\0' gdir; do
        potential_dirs+=("$gdir")
    done < <(find "$ADD_SUBJECT_DIR/$ADD_SESSION" -type d \( -name "*.gfeat" -o -iname "*fixed-effects*" \) -mindepth 1 -maxdepth 2 -print0 2>/dev/null)

    if [ ${#potential_dirs[@]} -eq 0 ]; then
        echo "No valid .gfeat/fixed-effects directories found for $ADD_SUBJECT in $ADD_SESSION. Returning..."
        return
    fi

    IFS=$'\n' potential_dirs=($(printf "%s\n" "${potential_dirs[@]}" | sort))
    unset IFS

    echo -e "\nSelect the directory(ies) to add or replace, separated by spaces.\n"

    local idxp=1
    declare -A MAP_INDEX_TO_GFEAT
    for dd in "${potential_dirs[@]}"; do
        printf " %2d)  %s\n" "$idxp" "${dd#$BASE_DIR/}"
        MAP_INDEX_TO_GFEAT[$idxp]="$dd"
        idxp=$((idxp+1))
    done
    echo

    local user_input=""
    local valid_feat_choice=false
    local chosen_dirs=()
    echo "Please enter your choice [e.g., 1 2 3] or press Enter/Return for ALL."
    while [ "$valid_feat_choice" = false ]; do
        read -p "> " user_input

        if [ -z "$user_input" ]; then
            chosen_dirs=("${potential_dirs[@]}")
            valid_feat_choice=true
            break
        fi

        read -ra input_tokens <<< "$user_input"
        local invalid_index=false
        local temp_dirs=()

        for token in "${input_tokens[@]}"; do
            if ! [[ "$token" =~ ^[0-9]+$ ]]; then
                echo "Invalid input: '$token' is not a number. Please try again."
                invalid_index=true
                break
            fi
            if (( token < 1 || token >= idxp )); then
                echo "Invalid input: '$token' is out of range. Please try again."
                invalid_index=true
                break
            fi
            temp_dirs+=( "${MAP_INDEX_TO_GFEAT[$token]}" )
        done

        if $invalid_index; then
            continue
        else
            chosen_dirs=("${temp_dirs[@]}")
            valid_feat_choice=true
        fi
    done

    local new_dirs_str
    new_dirs_str=$(printf "::%s" "${chosen_dirs[@]}")
    new_dirs_str="${new_dirs_str:2}"

    SUBJECTS+=( "$ADD_SUBJECT" )
    DIRECTORIES+=( "$new_dirs_str" )
    SESSIONS+=( "$ADD_SESSION" )
    DIR_TYPES+=( "$ADD_INPUT_TYPE" )

    echo -e "\n[EDIT] Updated selection for subject $ADD_SUBJECT, session $ADD_SESSION (higher-level)."
}

# ----------------------------------------------------------------------
# confirmation_loop
# ----------------------------------------------------------------------
confirmation_loop() {
    while true; do
        display_confirmed_selections "$SELECTED_SESSION"

        echo "Options:"
        echo "  • To exclude subjects, type '-' followed by subject IDs (e.g., '- sub-01 sub-02')."
        echo "  • To edit (add **new** or replace **existing**) directories for a specific subject, type 'edit'."
        echo "  • Press Enter/Return to confirm and proceed if selections are final."
        echo
        echo -n "> "
        read user_input

        if [ -z "$user_input" ]; then
            break
        fi

        local lower_input
        lower_input=$(echo "$user_input" | tr '[:upper:]' '[:lower:]')

        if [[ "$lower_input" == -* ]]; then
            remove_subjects "$user_input"
            if [ ${#SUBJECTS[@]} -eq 0 ]; then
                echo -e "\nWarning: You removed all subjects!"
            fi
        elif [[ "$lower_input" == "edit" ]]; then
            handle_edit
        else
            echo -e "\nInvalid input. Please try again.\n"
        fi
    done
}

# ----------------------------------------------------------------------
# finalize_selection
# ----------------------------------------------------------------------
finalize_selection() {
    FINAL_DIRS=()

    for idx in "${!SUBJECTS[@]}"; do
        IFS='::' read -ra dir_array <<< "${DIRECTORIES[$idx]}"
        for d in "${dir_array[@]}"; do
            if [ -n "$d" ]; then
                FINAL_DIRS+=( "$d" )
            fi
        done
    done

    IFS=$'\n' FINAL_DIRS=($(printf "%s\n" "${FINAL_DIRS[@]}" | sort))
    unset IFS

    echo -e "\n=== FINAL DIRECTORIES SELECTED ==="
    echo "Total final directories: ${#FINAL_DIRS[@]}"
    echo
    for f in "${FINAL_DIRS[@]}"; do
        echo "  $f"
    done
    echo -e "\n==================================="
    echo
}

# ----------------------------------------------------------------------
# prompt_for_roi
# ----------------------------------------------------------------------
prompt_for_roi() {
    ROI_SELECTIONS=()
    echo "[INFO] Searching level-3 directories that match *desc*group* + contain 'roi'..." >> "$LOGFILE"

    local candidate_roi_dirs=()
    while IFS= read -r -d $'\0' d; do
        if [ -d "$d/roi" ]; then
            candidate_roi_dirs+=( "$d" )
        fi
    done < <(find "$LEVEL_3_ANALYSIS_BASE_DIR" -maxdepth 1 -type d -iname "*desc*group*" -print0 2>/dev/null)

    local all_roi_subdirs=()
    for cand in "${candidate_roi_dirs[@]}"; do
        if [ -d "$cand/roi" ]; then
            while IFS= read -r -d $'\0' sub; do
                all_roi_subdirs+=( "$sub" )
            done < <(find "$cand/roi" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)
        fi
    done

    IFS=$'\n' all_roi_subdirs=($(printf "%s\n" "${all_roi_subdirs[@]}" | sort -u))
    unset IFS

    # If no ROI subdirectories found, prompt for manual directory or exit
    if [ ${#all_roi_subdirs[@]} -eq 0 ]; then
        echo "No ROI directories found in level-3 that match 'desc' and 'group' + contain 'roi/'."
        echo "You can:"
        echo "  1) Manually enter the directory path containing your ROIs"
        echo "  2) Or type 'exit' to stop now and create binarized ROIs before re-running featquery."
        while true; do
            echo
            read -p "Enter ROI directory path or 'exit': " user_path
            if [[ "$user_path" == "exit" ]]; then
                echo "Exiting script. Please create binarized ROIs and re-run."
                exit 0
            elif [ -n "$user_path" ]; then
                if [ -d "$user_path" ]; then
                    ROI_SELECTIONS+=( "$user_path" )
                    break
                else
                    echo "Directory '$user_path' not found. Please try again or type 'exit'."
                fi
            else
                echo "Invalid (empty). Please provide a path or type 'exit'."
            fi
        done
    else
        # ROI subdirectories were found, so prompt for selection
        echo
        echo "Select from the available ROI directories below."
        echo "----------------------------------------------------------------------------------------------"
        local idx=1
        declare -A MAP_ROI_INDEX_TO_DIR
        for roi_d in "${all_roi_subdirs[@]}"; do
            echo "  $idx) $roi_d"
            MAP_ROI_INDEX_TO_DIR[$idx]="$roi_d"
            idx=$((idx+1))
        done

        # Similar prompt style as ROI masks
        local valid_input=false
        echo
        echo "Enter choice(s) by number [e.g., 1 2 3], or type a custom path, or press Enter/Return for ALL."
        while [ "$valid_input" = false ]; do
            read -p "> " user_input

            # If Enter is pressed, select ALL
            if [ -z "$user_input" ]; then
                ROI_SELECTIONS=("${all_roi_subdirs[@]}")
                valid_input=true
                break
            fi

            read -ra tokens <<< "$user_input"
            local numeric_tokens=()
            local custom_paths=()

            for tk in "${tokens[@]}"; do
                # If numeric, map to ROI directory by index
                if [[ "$tk" =~ ^[0-9]+$ ]]; then
                    if (( tk < 1 || tk >= idx )); then
                        # invalid numeric range
                        continue
                    fi
                    numeric_tokens+=( "$tk" )
                else
                    # Otherwise treat as a custom path
                    if [ -d "$tk" ]; then
                        custom_paths+=( "$tk" )
                    fi
                fi
            done

            local temp_roi_dirs=()
            for num in "${numeric_tokens[@]}"; do
                temp_roi_dirs+=( "${MAP_ROI_INDEX_TO_DIR[$num]}" )
            done
            for cpath in "${custom_paths[@]}"; do
                temp_roi_dirs+=( "$cpath" )
            done

            if [ ${#temp_roi_dirs[@]} -eq 0 ]; then
                echo "No valid ROI directory selected. Please try again."
            else
                ROI_SELECTIONS+=( "${temp_roi_dirs[@]}" )
                valid_input=true
            fi
        done
    fi

    IFS=$'\n' ROI_SELECTIONS=($(printf "%s\n" "${ROI_SELECTIONS[@]}" | sort -u))
    unset IFS

    echo
    echo -e "=== FINAL ROI DIRECTORIES SELECTED ===\n"
    for r in "${ROI_SELECTIONS[@]}"; do
        echo "  $r"
    done
    echo -e "\n======================================="
    echo
}

# ----------------------------------------------------------------------
# prompt_for_roi_masks
# ----------------------------------------------------------------------
prompt_for_roi_masks() {
    ROI_MASK_SELECTIONS=()
    echo "Next, let's select the ROI mask image(s) for featquery." >> $LOGFILE

    local candidate_mask_files=()

    for roi_dir in "${ROI_SELECTIONS[@]}"; do
        while IFS= read -r -d $'\0' mf; do
            candidate_mask_files+=( "$mf" )
        done < <(find "$roi_dir" -type f \
                   \( -iname "*binarized*.nii*" \) \
                   -print0 2>/dev/null)
    done

    IFS=$'\n' candidate_mask_files=($(printf "%s\n" "${candidate_mask_files[@]}" | sort -u))
    unset IFS

    if [ ${#candidate_mask_files[@]} -eq 0 ]; then
        echo "No ROI mask files found (with 'binarized' in the name)."
        echo "You can:"
        echo "  1) Type 'exit' to stop now and prepare your masks."
        echo "  2) Or press Enter to skip."
        while true; do
            read -p "Enter 'exit' to quit or just press Enter/Return to skip mask selection: " user_mask
            if [[ "$user_mask" == "exit" ]]; then
                echo "Exiting script. Please prepare your ROI mask(s) and re-run."
                exit 0
            elif [ -z "$user_mask" ]; then
                echo "Skipping mask selection."
                break
            else
                echo "Invalid input. Please type 'exit' or press Enter/Return to skip."
            fi
        done
    else
        echo
        echo "Select from the available ROI masks below."
        echo "--------------------------------------------------------------------------------"
        local idx=1
        declare -A MAP_MASK_INDEX_TO_FILE
        for mask_f in "${candidate_mask_files[@]}"; do
            echo "  $idx) $mask_f"
            MAP_MASK_INDEX_TO_FILE[$idx]="$mask_f"
            idx=$((idx+1))
        done

        echo
        echo "Enter choice(s) by number [e.g., 1 2 3], or press Enter/Return for ALL."
        local user_input
        local valid_input=false

        while [ "$valid_input" = false ]; do
            read -p "> " user_input

            if [ -z "$user_input" ]; then
                ROI_MASK_SELECTIONS=("${candidate_mask_files[@]}")
                valid_input=true
            else
                read -ra tokens <<< "$user_input"
                local numeric_tokens=()
                local invalid_choice=false

                for tk in "${tokens[@]}"; do
                    if ! [[ "$tk" =~ ^[0-9]+$ ]]; then
                        echo "Invalid input: '$tk' is not a number. Please try again."
                        invalid_choice=true
                        break
                    fi
                    if (( tk < 1 || tk >= idx )); then
                        echo "Invalid input: '$tk' is out of range. Please try again."
                        invalid_choice=true
                        break
                    fi
                    numeric_tokens+=( "$tk" )
                done

                if $invalid_choice; then
                    continue
                else
                    for num in "${numeric_tokens[@]}"; do
                        ROI_MASK_SELECTIONS+=( "${MAP_MASK_INDEX_TO_FILE[$num]}" )
                    done
                    valid_input=true
                fi
            fi
        done
    fi

    IFS=$'\n' ROI_MASK_SELECTIONS=($(printf "%s\n" "${ROI_MASK_SELECTIONS[@]}" | sort -u))
    unset IFS

    if [ ${#ROI_MASK_SELECTIONS[@]} -gt 0 ]; then
        echo
        echo -e "=== FINAL ROI MASKS SELECTED ===\n"
        for rmf in "${ROI_MASK_SELECTIONS[@]}"; do
            echo "  $rmf"
        done
        echo -e "\n================================="
        echo
    else
        echo "No masks selected."
    fi
}

###############################################################################
# check_level_3_ready
#   Returns 0 (true) if there's at least one Level-3 directory that meets:
#     1) >=3 lines referencing $BASE_DIR in logs/feat2_pre (summed or per .gfeat)
#     2) For each .gfeat that has an roi/ subfolder, at least one binarized file
#   Otherwise returns 1 (false).
###############################################################################
check_level_3_ready() {
    local level3_dirs=()
    while IFS= read -r -d $'\0' d; do
        level3_dirs+=( "$d" )
    done < <(find "$LEVEL_3_ANALYSIS_BASE_DIR" -maxdepth 1 -type d -iname "*desc*group*" -print0 2>/dev/null)

    [ ${#level3_dirs[@]} -eq 0 ] && return 1

    for l3_dir in "${level3_dirs[@]}"; do
        local cope_gfeats=()
        while IFS= read -r -d $'\0' gf; do
            cope_gfeats+=( "$gf" )
        done < <(find "$l3_dir" -maxdepth 1 -type d -name "cope*.gfeat" -print0 2>/dev/null)

        [ ${#cope_gfeats[@]} -eq 0 ] && continue

        local total_featregapply_count=0
        local all_roi_good=true

        for gf in "${cope_gfeats[@]}"; do
            local feat2_pre="$gf/logs/feat2_pre"
            local matched_count=0

            if [ -f "$feat2_pre" ]; then
                while IFS= read -r line; do
                    local stripped="$(echo "$line" | sed 's/.*featregapply //')"
                    if [[ "$stripped" == "$BASE_DIR"* ]]; then
                        (( matched_count++ ))
                    fi
                done < <(grep featregapply "$feat2_pre" 2>/dev/null)
            fi

            (( total_featregapply_count += matched_count ))

            local roi_dir="$gf/roi"
            if [ -d "$roi_dir" ]; then
                local binarized_files=()
                while IFS= read -r -d $'\0' bf; do
                    binarized_files+=( "$bf" )
                done < <(find "$roi_dir" -type f -iname "*binarized*.nii*" -print0 2>/dev/null)

                if [ ${#binarized_files[@]} -eq 0 ]; then
                    all_roi_good=false
                    break
                fi
            fi
        done

        if (( total_featregapply_count >= 3 )) && $all_roi_good; then
            return 0
        fi
    done

    return 1
}

declare -A COPE_DIRS_MAP=()
declare -A COPE_MASKS_MAP=()

###############################################################################
# scan_l3_dir_qualifies
#   Helper to see if a level-3 directory is "qualified":
###############################################################################
scan_l3_dir_qualifies() {
    local l3_dir="$1"

    local cope_gfeats=()
    while IFS= read -r -d $'\0' gf; do
        cope_gfeats+=( "$gf" )
    done < <(find "$l3_dir" -maxdepth 1 -type d -name "cope*.gfeat" -print0 2>/dev/null)

    if [ ${#cope_gfeats[@]} -eq 0 ]; then
        return 1
    fi

    local total_featregapply_count=0
    local found_any_binarized=false

    for gf in "${cope_gfeats[@]}"; do
        local feat2_pre="$gf/logs/feat2_pre"
        local matched_count=0
        if [ -f "$feat2_pre" ]; then
            while IFS= read -r line; do
                local stripped
                stripped="$(echo "$line" | sed 's/.*featregapply //')"
                if [[ "$stripped" == "$BASE_DIR"* ]]; then
                    (( matched_count++ ))
                fi
            done < <(grep featregapply "$feat2_pre" 2>/dev/null)
        fi
        (( total_featregapply_count += matched_count ))

        local baseName="$(basename "$gf")"
        local copeNum="${baseName%.gfeat}"
        local alt_roi_dir="$l3_dir/roi/$copeNum"

        if [ -d "$alt_roi_dir" ]; then
            local binarized_files=()
            while IFS= read -r -d $'\0' bf; do
                binarized_files+=( "$bf" )
            done < <(find "$alt_roi_dir" -type f -iname "*binarized*.nii*" -print0 2>/dev/null)
            if [ ${#binarized_files[@]} -gt 0 ]; then
                found_any_binarized=true
            fi
        fi
    done

    if (( total_featregapply_count >= 3 )) && $found_any_binarized; then
        return 0
    else
        return 1
    fi
}

###############################################################################
# select_level_3_analysis
#   Gather all level-3 directories, prompt for one, parse them, etc.
###############################################################################
select_level_3_analysis() {

    echo -e "\n[INFO] Checking for valid level-3 directories in: $LEVEL_3_ANALYSIS_BASE_DIR" >> "$LOGFILE"
    echo "Looking for directories named '*desc*group*' with ≥3 'featregapply' references + binarized ROI." >> "$LOGFILE"

    local all_l3=()
    while IFS= read -r -d $'\0' d; do
        all_l3+=( "$d" )
    done < <(find "$LEVEL_3_ANALYSIS_BASE_DIR" -maxdepth 1 -type d -iname "*desc*group*" -print0 2>/dev/null)

    local qualified_l3=()
    for l3_dir in "${all_l3[@]}"; do
        if scan_l3_dir_qualifies "$l3_dir"; then
            qualified_l3+=( "$l3_dir" )
        fi
    done

    if [ ${#qualified_l3[@]} -eq 0 ]; then
        echo
        echo "No Level-3 directories found that meet the requirements:"
        echo "  - At least 3 references to $BASE_DIR in logs/feat2_pre (summation),"
        echo "  - At least one binarized ROI subfolder per copeX.gfeat."
        echo
        echo "Please ensure your logs/feat2_pre references ≥3 .feat directories, and that"
        echo "each copeX.gfeat has a binarized ROI in 'roi/copeX' before re-running."
        echo
        exit 1
    fi

    echo
    echo "Level-3 directories that are eligible for automatic featquery inputs:"
    echo
    local idx=1
    declare -A MAP_INDEX_TO_L3
    for d in "${qualified_l3[@]}"; do
        echo "  $idx) ${d#$BASE_DIR/}"
        MAP_INDEX_TO_L3[$idx]="$d"
        idx=$((idx+1))
    done
    echo

    local chosen_l3_dir=""
    while true; do
        read -p "Please select exactly ONE Level-3 directory by number: " user_input

        if [ -z "$user_input" ]; then
            echo "No input given. Please enter a valid number."
            continue
        fi

        if ! [[ "$user_input" =~ ^[0-9]+$ ]]; then
            echo "Invalid input: '$user_input' is not a number. Please try again."
            continue
        fi

        if (( user_input < 1 || user_input >= idx )); then
            echo "Invalid selection. Please try again."
            continue
        fi

        chosen_l3_dir="${MAP_INDEX_TO_L3[$user_input]}"
        break
    done

    for k in "${!COPE_DIRS_MAP[@]}"; do
        unset 'COPE_DIRS_MAP[$k]'
    done
    for k in "${!COPE_MASKS_MAP[@]}"; do
        unset 'COPE_MASKS_MAP[$k]'
    done

    echo
    echo "=== Checking: $chosen_l3_dir"
    echo

    local cope_gfeats=()
    while IFS= read -r -d $'\0' gf; do
        cope_gfeats+=( "$gf" )
    done < <(find "$chosen_l3_dir" -maxdepth 1 -type d -name "cope*.gfeat" -print0 2>/dev/null)

    IFS=$'\n' cope_gfeats=($(printf "%s\n" "${cope_gfeats[@]}" | sort -V))
    unset IFS

    local qualified_copes=()
    for gf in "${cope_gfeats[@]}"; do
        local baseName="$(basename "$gf")"
        local copeNum="${baseName%.gfeat}"
        local alt_roi_dir="$chosen_l3_dir/roi/$copeNum"

        if [ -d "$alt_roi_dir" ]; then
            local binarized_files=()
            while IFS= read -r -d $'\0' bf; do
                binarized_files+=( "$bf" )
            done < <(find "$alt_roi_dir" -type f -iname "*binarized*.nii*" -print0 2>/dev/null)

            if [ ${#binarized_files[@]} -gt 0 ]; then
                qualified_copes+=( "$gf" )
            fi
        fi
    done

    IFS=$'\n' qualified_copes=($(printf "%s\n" "${qualified_copes[@]}" | sort -V))
    unset IFS

    if [ ${#qualified_copes[@]} -eq 0 ]; then
        echo "No 'copeX.gfeat' subdirectories in $chosen_l3_dir have binarized ROI(s)."
        echo "Cannot proceed with Level-3 automatic selection."
        echo
        exit 1
    fi

    echo "copeX.gfeat subdirectories that contain binarized ROIs in:"
    echo "  $chosen_l3_dir"
    echo
    local cidx=1
    declare -A MAP_INDEX_TO_COPE
    for cg in "${qualified_copes[@]}"; do
        echo "  $cidx) ${cg#$BASE_DIR/}"
        MAP_INDEX_TO_COPE[$cidx]="$cg"
        cidx=$((cidx+1))
    done
    echo

    echo "Select one or more cope.gfeat subdirectories by number, or press Enter/Return to select ALL."
    local user_cope_input
    local valid_cope=false
    local chosen_cope_dirs=()

    while [ "$valid_cope" = false ]; do
        read -p "> " user_cope_input

        if [ -z "$user_cope_input" ]; then
            chosen_cope_dirs=("${qualified_copes[@]}")
            valid_cope=true
            break
        fi

        read -ra tokens <<< "$user_cope_input"
        local invalid=false
        local temp_cope=()

        for tk in "${tokens[@]}"; do
            if ! [[ "$tk" =~ ^[0-9]+$ ]]; then
                echo "Invalid input: '$tk' is not a number. Please try again."
                invalid=true
                break
            fi
            if (( tk < 1 || tk >= cidx )); then
                echo "Invalid input: '$tk' is out of range. Please try again."
                invalid=true
                break
            fi
            temp_cope+=( "${MAP_INDEX_TO_COPE[$tk]}" )
        done

        if $invalid; then
            continue
        else
            chosen_cope_dirs=("${temp_cope[@]}")
            valid_cope=true
        fi
    done

    for cope_dir in "${chosen_cope_dirs[@]}"; do
        local baseName="$(basename "$cope_dir")"
        local copeNum="${baseName%.gfeat}"
        local feat2_pre_file="$cope_dir/logs/feat2_pre"

        echo "-----> Parsing: $feat2_pre_file" >> "$LOGFILE"
        echo >> "$LOGFILE"
        echo "[The lines below contain 'featregapply':]" >> "$LOGFILE"
        echo "---------------------------------------------------" >> "$LOGFILE"

        local matched_lines=()
        if [ -f "$feat2_pre_file" ]; then
            while IFS= read -r line; do
                local stripped
                stripped="$(echo "$line" | sed 's/.*featregapply //')"
                if [[ "$stripped" == "$BASE_DIR"* ]]; then
                    matched_lines+=( "$stripped" )
                fi
            done < <(grep featregapply "$feat2_pre_file" 2>/dev/null)
        else
            echo "  [WARNING] No logs/feat2_pre found in $cope_dir." >> "$LOGFILE"
        fi

        if [ ${#matched_lines[@]} -eq 0 ]; then
            echo "(No lines found matching 'featregapply' under $BASE_DIR.)" >> "$LOGFILE"
        else
            for ml in "${matched_lines[@]}"; do
                echo "$ml" >> "$LOGFILE"
                COPE_DIRS_MAP["$copeNum"]+=$'\n'"$ml"
            done
            echo >> "$LOGFILE"
            echo "[INFO] Found ${#matched_lines[@]} directories in logs/feat2_pre that used 'featregapply' under this project." >> "$LOGFILE"
        fi
        echo "---------------------------------------------------" >> "$LOGFILE"
        echo >> "$LOGFILE"

        local alt_roi_dir="$chosen_l3_dir/roi/$copeNum"
        echo "-----> Checking for binarized masks in: $alt_roi_dir" >> "$LOGFILE"

        local binarized_files=()
        while IFS= read -r -d $'\0' bf; do
            binarized_files+=( "$bf" )
        done < <(find "$alt_roi_dir" -type f -iname "*binarized*.nii*" -print0 2>/dev/null)

        if [ ${#binarized_files[@]} -eq 0 ]; then
            echo "  [WARNING] No binarized masks found in $alt_roi_dir (unexpected?)." >> "$LOGFILE"
        else
            echo "  Found ${#binarized_files[@]} binarized mask(s)." >> "$LOGFILE"
            for bf in "${binarized_files[@]}"; do
                echo "    $bf" >> "$LOGFILE"
                COPE_MASKS_MAP["$copeNum"]+=$'\n'"$bf"
            done
        fi
    done

    for c in "${!COPE_DIRS_MAP[@]}"; do
        IFS=$'\n' read -r -d '' -a per_cope_dirs <<< "$(printf "%s\n" "${COPE_DIRS_MAP[$c]}" | sed '/^$/d' | sort)" || true
        IFS=$'\n' read -r -d '' -a per_cope_masks <<< "$(printf "%s\n" "${COPE_MASKS_MAP[$c]}" | sed '/^$/d' | sort)" || true

        echo -e "\n=== FINAL DIRECTORIES SELECTED for $c ==="
        echo "Total final directories: ${#per_cope_dirs[@]}"
        echo
        for d in "${per_cope_dirs[@]}"; do
            echo "  $d"
        done
        echo -e "\n==================================="

        if [ ${#per_cope_masks[@]} -gt 0 ]; then
            echo
            echo "=== FINAL ROI MASKS SELECTED for $c ==="
            echo
            for m in "${per_cope_masks[@]}"; do
                echo "  $m"
            done
            echo -e "\n================================="
            echo
        else
            echo
            echo "[INFO] No binarized mask(s) found for $c (unexpected?)."
            echo
        fi
    done

    echo "[Level-3 selection complete. Returning to main script flow...]"
}



###############################################################################
# Main Script
###############################################################################

echo
echo "=== FEATQUERY INPUT SELECTION ==="
echo "Please select analysis level for input directories:"
echo
echo "1) Inputs are lower-level FEAT directories"
echo "2) Inputs are higher-level .gfeat directories"
echo "3) Cancel"
echo

while true; do
    read -p "Please enter your choice [1/2/3]: " choice

    if ! [[ "$choice" =~ ^[0-9]+$ ]]; then
        echo "Invalid input. Please enter 1, 2, or 3."
        continue
    fi

    if (( choice < 1 || choice > 3 )); then
        echo "Invalid selection. Please try again."
        continue
    fi

    case "$choice" in
        1)
            # -------------------------------------------------------
            # LOWER-LEVEL (level-1) FEAT .feat directories
            # -------------------------------------------------------
            CURRENT_INPUT_TYPE="lower"
            echo -e "\n[INFO] You selected lower-level FEAT directories." >> "$LOGFILE"

            find_lower_level_analysis_dirs "$LEVEL_1_ANALYSIS_BASE_DIR"
            if [ ${#ANALYSIS_DIRS[@]} -eq 0 ]; then
                echo "No 'analysis' directories found under $LEVEL_1_ANALYSIS_BASE_DIR containing .feat."
                echo "Exiting..."
                exit 1
            fi

            echo -e "\nAvailable analysis directories in level-1:\n"
            for idx in "${!ANALYSIS_DIRS[@]}"; do
                echo "$((idx + 1))) ${ANALYSIS_DIRS[$idx]#$BASE_DIR/}"
            done
            echo

            valid_analysis_choice=false
            analysis_choice_num=""
            while [ "$valid_analysis_choice" = false ]; do
                read -p "Please select an analysis directory by number: " analysis_choice_num
                if ! [[ "$analysis_choice_num" =~ ^[0-9]+$ ]]; then
                    echo "Invalid input. Please enter a valid number."
                    continue
                fi
                if (( analysis_choice_num < 1 || analysis_choice_num > ${#ANALYSIS_DIRS[@]} )); then
                    echo "Invalid selection. Please try again."
                    continue
                fi
                valid_analysis_choice=true
            done

            SELECTED_ANALYSIS_DIR="${ANALYSIS_DIRS[$((analysis_choice_num - 1))]}"
            echo -e "\nAnalysis directory selected:"
            echo "  $SELECTED_ANALYSIS_DIR"

            # Find sessions
            mapfile -t session_names < <(find_sessions_in_dir "$SELECTED_ANALYSIS_DIR")
            if [ ${#session_names[@]} -eq 0 ]; then
                echo "No sessions found under $SELECTED_ANALYSIS_DIR. Proceeding without sessions."
                SELECTED_SESSION=""
            elif [ ${#session_names[@]} -eq 1 ]; then
                SELECTED_SESSION="${session_names[0]}"
                echo -e "\nOnly one session found: $SELECTED_SESSION"
            else
                echo -e "\nAvailable sessions:\n"
                for idx in "${!session_names[@]}"; do
                    echo "$((idx + 1))) ${session_names[$idx]}"
                done
                echo

                valid_session_choice=false
                session_choice_num=""
                while [ "$valid_session_choice" = false ]; do
                    read -p "Please select a session by number: " session_choice_num
                    if ! [[ "$session_choice_num" =~ ^[0-9]+$ ]]; then
                        echo "Invalid input. Please enter a valid number."
                        continue
                    fi
                    if (( session_choice_num < 1 || session_choice_num > ${#session_names[@]} )); then
                        echo "Invalid selection. Please try again."
                        continue
                    fi
                    valid_session_choice=true
                    SELECTED_SESSION="${session_names[$((session_choice_num - 1))]}"
                done
                echo -e "\nYou have selected session: $SELECTED_SESSION" >> "$LOGFILE"
            fi

            # Collect subjects + .feat dirs
            collect_subjects_and_feat "$SELECTED_ANALYSIS_DIR" "$SELECTED_SESSION" "$CURRENT_INPUT_TYPE"

            # Prompt to confirm or remove
            confirmation_loop
            echo -e "\nFinalizing selection and continuing (lower-level)..."

            # Finalize => populates FINAL_DIRS
            finalize_selection

            # Prompt for ROI directories, then ROI masks => populates ROI_MASK_SELECTIONS
            prompt_for_roi
            prompt_for_roi_masks

            # Now call run_featquery.sh with final directories & ROI masks
            if [ ${#FINAL_DIRS[@]} -gt 0 ] && [ ${#ROI_MASK_SELECTIONS[@]} -gt 0 ]; then
                echo "[INFO] Now calling run_featquery.sh with the selected directories and ROI masks..."  >> "$LOGFILE"
                echo
                "$script_dir/run_featquery.sh" "${FINAL_DIRS[@]}" "::" "${ROI_MASK_SELECTIONS[@]}"
            fi

            exit 0
            ;;

        2)
            # -------------------------------------------------------
            # HIGHER-LEVEL .gfeat (level-2 or level-3)
            # -------------------------------------------------------
            CURRENT_INPUT_TYPE="higher"
            echo -e "\n[INFO] You selected higher-level .gfeat directories.\n" >> "$LOGFILE"

            if check_level_3_ready; then
                echo -e "\nAvailable options:\n"
                echo "1) level-2"
                echo "2) level-3 (automatic detection of .feat + ROI for featquery)"
                echo

                read -p "Please enter your choice [1/2]: " gfeat_choice_num
                if ! [[ "$gfeat_choice_num" =~ ^[0-9]+$ ]]; then
                    echo "Invalid input. Please enter 1 or 2."
                    exit 1
                fi

                if [ "$gfeat_choice_num" == "2" ]; then
                    # -------------- LEVEL-3 PATH --------------
                    select_level_3_analysis

                    # Flatten them into arrays to pass to run_featquery
                    ALL_L3_FEAT_DIRS=()
                    ALL_L3_ROI_MASKS=()

                    for cope_nm in "${!COPE_DIRS_MAP[@]}"; do
                        mapfile -t cdirs < <( printf "%s\n" "${COPE_DIRS_MAP[$cope_nm]}" | sed '/^$/d' )
                        mapfile -t cmasks < <( printf "%s\n" "${COPE_MASKS_MAP[$cope_nm]}" | sed '/^$/d' )
                        ALL_L3_FEAT_DIRS+=( "${cdirs[@]}" )
                        ALL_L3_ROI_MASKS+=( "${cmasks[@]}" )
                    done

                    IFS=$'\n' ALL_L3_FEAT_DIRS=($(printf "%s\n" "${ALL_L3_FEAT_DIRS[@]}" | sort -u))
                    IFS=$'\n' ALL_L3_ROI_MASKS=($(printf "%s\n" "${ALL_L3_ROI_MASKS[@]}" | sort -u))
                    unset IFS

                    if [ ${#ALL_L3_FEAT_DIRS[@]} -gt 0 ] && [ ${#ALL_L3_ROI_MASKS[@]} -gt 0 ]; then
                        echo "[INFO] Now calling run_featquery.sh with the level-3-based directories and ROI masks..."  >> "$LOGFILE"
                        echo
                        "$script_dir/run_featquery.sh" "${ALL_L3_FEAT_DIRS[@]}" "::" "${ALL_L3_ROI_MASKS[@]}"
                    fi

                    exit 0

                else
                    # -------------- LEVEL-2 PATH --------------
                    echo -e "\n[INFO] Searching for level-2 .gfeat or 'fixed-effects' directories."  >> "$LOGFILE"
                    find_higher_level_analysis_dirs "$LEVEL_2_ANALYSIS_BASE_DIR"

                    if [ ${#ANALYSIS_DIRS[@]} -eq 0 ]; then
                        echo "No higher-level gfeat/fixed-effects directories found under $LEVEL_2_ANALYSIS_BASE_DIR."
                        echo "Exiting..."
                        exit 1
                    fi

                    echo -e "\nAvailable higher-level .gfeat/fixed-effects directories in level-2:\n"
                    for idx in "${!ANALYSIS_DIRS[@]}"; do
                        echo "$((idx + 1))) ${ANALYSIS_DIRS[$idx]#$BASE_DIR/}"
                    done
                    echo

                    valid_analysis_choice=false
                    analysis_choice_num=""
                    while [ "$valid_analysis_choice" = false ]; do
                        read -p "Please select an analysis directory by number: " analysis_choice_num
                        if ! [[ "$analysis_choice_num" =~ ^[0-9]+$ ]]; then
                            echo "Invalid input. Please enter a valid number."
                            continue
                        fi
                        if (( analysis_choice_num < 1 || analysis_choice_num > ${#ANALYSIS_DIRS[@]} )); then
                            echo "Invalid selection. Please try again."
                            continue
                        fi
                        valid_analysis_choice=true
                    done

                    SELECTED_ANALYSIS_DIR="${ANALYSIS_DIRS[$((analysis_choice_num - 1))]}"
                    echo -e "\nAnalysis directory selected:"
                    echo "  $SELECTED_ANALYSIS_DIR"

                    mapfile -t session_names < <(find_sessions_in_dir "$SELECTED_ANALYSIS_DIR")
                    if [ ${#session_names[@]} -eq 0 ]; then
                        echo "No sessions found under $SELECTED_ANALYSIS_DIR. Proceeding without sessions."
                        SELECTED_SESSION=""
                    elif [ ${#session_names[@]} -eq 1 ]; then
                        SELECTED_SESSION="${session_names[0]}"
                        echo -e "\nOnly one session found: $SELECTED_SESSION"
                    else
                        echo -e "\nAvailable sessions:\n"
                        for idx in "${!session_names[@]}"; do
                            echo "$((idx + 1))) ${session_names[$idx]}"
                        done
                        echo

                        valid_session_choice=false
                        session_choice_num=""
                        while [ "$valid_session_choice" = false ]; do
                            read -p "Please select a session by number: " session_choice_num
                            if ! [[ "$session_choice_num" =~ ^[0-9]+$ ]]; then
                                echo "Invalid input. Please enter a valid number."
                                continue
                            fi
                            if (( session_choice_num < 1 || session_choice_num > ${#session_names[@]} )); then
                                echo "Invalid selection. Please try again."
                                continue
                            fi
                            valid_session_choice=true
                            SELECTED_SESSION="${session_names[$((session_choice_num - 1))]}"
                        done
                        echo -e "\nYou have selected session: $SELECTED_SESSION" >> "$LOGFILE"
                    fi

                    # Gather subject-level .gfeat directories
                    collect_subjects_and_feat "$SELECTED_ANALYSIS_DIR" "$SELECTED_SESSION" "$CURRENT_INPUT_TYPE"

                    # Prompt to confirm or remove
                    confirmation_loop
                    echo -e "\nFinalizing selection and continuing (higher-level, level-2)..." >> "$LOGFILE"

                    # Finalize => populates FINAL_DIRS
                    finalize_selection

                    # Prompt for ROI directories => ROI_SELECTIONS
                    prompt_for_roi
                    # Then ROI masks => ROI_MASK_SELECTIONS
                    prompt_for_roi_masks

                    # Now call run_featquery.sh
                    if [ ${#FINAL_DIRS[@]} -gt 0 ] && [ ${#ROI_MASK_SELECTIONS[@]} -gt 0 ]; then
                        echo "[INFO] Now calling run_featquery.sh with the selected directories and ROI masks..."  >> "$LOGFILE"
                        echo
                        "$script_dir/run_featquery.sh" "${FINAL_DIRS[@]}" "::" "${ROI_MASK_SELECTIONS[@]}"
                    fi

                    exit 0
                fi

            else
                # If no valid level-3 found, only do level-2
                echo "[INFO] Sorry, no level-3 directories meet the threshold. Offering only level-2..." >> "$LOGFILE"
                echo

                echo "[INFO] Searching for level-2 .gfeat or 'fixed-effects' directories." >> "$LOGFILE"
                find_higher_level_analysis_dirs "$LEVEL_2_ANALYSIS_BASE_DIR"

                if [ ${#ANALYSIS_DIRS[@]} -eq 0 ]; then
                    echo "No higher-level gfeat/fixed-effects directories found under $LEVEL_2_ANALYSIS_BASE_DIR."
                    echo "Exiting..."
                    exit 1
                fi

                echo -e "\nAvailable higher-level .gfeat/fixed-effects directories in level-2:\n"
                for idx in "${!ANALYSIS_DIRS[@]}"; do
                    echo "$((idx + 1))) ${ANALYSIS_DIRS[$idx]#$BASE_DIR/}"
                done
                echo

                valid_analysis_choice=false
                analysis_choice_num=""
                while [ "$valid_analysis_choice" = false ]; do
                    read -p "Please select an analysis directory by number: " analysis_choice_num
                    if ! [[ "$analysis_choice_num" =~ ^[0-9]+$ ]]; then
                        echo "Invalid input. Please enter a valid number."
                        continue
                    fi
                    if (( analysis_choice_num < 1 || analysis_choice_num > ${#ANALYSIS_DIRS[@]} )); then
                        echo "Invalid selection. Please try again."
                        continue
                    fi
                    valid_analysis_choice=true
                done

                SELECTED_ANALYSIS_DIR="${ANALYSIS_DIRS[$((analysis_choice_num - 1))]}"
                echo -e "\nAnalysis directory selected:"
                echo "  $SELECTED_ANALYSIS_DIR"

                mapfile -t session_names < <(find_sessions_in_dir "$SELECTED_ANALYSIS_DIR")
                if [ ${#session_names[@]} -eq 0 ]; then
                    echo "No sessions found under $SELECTED_ANALYSIS_DIR. Proceeding without sessions."
                    SELECTED_SESSION=""
                elif [ ${#session_names[@]} -eq 1 ]; then
                    SELECTED_SESSION="${session_names[0]}"
                    echo -e "\nOnly one session found: $SELECTED_SESSION"
                else
                    echo -e "\nAvailable sessions:\n"
                    for idx in "${!session_names[@]}"; do
                        echo "$((idx + 1))) ${session_names[$idx]}"
                    done
                    echo

                    valid_session_choice=false
                    session_choice_num=""
                    while [ "$valid_session_choice" = false ]; do
                        read -p "Please select a session by number: " session_choice_num
                        if ! [[ "$session_choice_num" =~ ^[0-9]+$ ]]; then
                            echo "Invalid input. Please enter a valid number."
                            continue
                        fi
                        if (( session_choice_num < 1 || session_choice_num > ${#session_names[@]} )); then
                            echo "Invalid selection. Please try again."
                            continue
                        fi
                        valid_session_choice=true
                        SELECTED_SESSION="${session_names[$((session_choice_num - 1))]}"
                    done
                    echo -e "\nYou have selected session: $SELECTED_SESSION" >> "$LOGFILE"
                fi

                # Gather subject-level .gfeat directories
                collect_subjects_and_feat "$SELECTED_ANALYSIS_DIR" "$SELECTED_SESSION" "$CURRENT_INPUT_TYPE"

                # Prompt to confirm or remove
                confirmation_loop
                echo -e "\nFinalizing selection and continuing (higher-level, level-2)..."

                # Finalize => populates FINAL_DIRS
                finalize_selection

                # ROI selection
                prompt_for_roi
                prompt_for_roi_masks

                # Call run_featquery.sh
                if [ ${#FINAL_DIRS[@]} -gt 0 ] && [ ${#ROI_MASK_SELECTIONS[@]} -gt 0 ]; then
                    echo "[INFO] Now calling run_featquery.sh with the selected directories and ROI masks..."  >> "$LOGFILE"
                    echo
                    "$script_dir/run_featquery.sh" "${FINAL_DIRS[@]}" "::" "${ROI_MASK_SELECTIONS[@]}"
                fi

                exit 0
            fi
            ;;

        3)
            # -------------------------------------------------------
            # CANCEL
            # -------------------------------------------------------
            echo "Cancelled."
            exit 0
            ;;
    esac
done
