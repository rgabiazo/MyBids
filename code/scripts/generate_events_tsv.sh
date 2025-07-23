#!/bin/bash
###############################################################################
# generate_events_tsv.sh
#
# Purpose:
#   Build BIDS events.tsv files from raw timing text files for each subject.
#
# Usage:
#   generate_events_tsv.sh [--base-dir DIR] [--session SESSION] 
#                          [--conditions LIST] [--tasks LIST] SUBJECTS...
#
# Usage Examples:
#   generate_events_tsv.sh --session ses-01 sub-01
#   generate_events_tsv.sh --base-dir /proj --conditions cond1,cond2 sub-02 sub-03
#   generate_events_tsv.sh --session ses-02 --tasks task1,task2 sub-001
#
# Options:
#   --base-dir DIR      Base project directory
#   --session SESSION   Session name (default ses-01)
#   --conditions LIST   Comma-separated conditions
#   --tasks LIST        Comma-separated tasks
#   -h, --help          Show help
#
# Requirements:
#   bash
#
# Notes:
#   Prompts for a custom task name and logs actions under code/logs.
#   How it works:
#   - Prompts for a custom output task name (for the TSV filenames).
#   - It detects multiple directories under sourcedata/ and prompts to choose
#     one if more than one is present (excluding dicom, nifti, code).
#   - It reads raw timing text files named like: <task>_response_data_<cond>_run<N>.txt
#     and merges them into sorted TSV files with columns: onset, duration, trial_type, weight.
#   - Each subject can have zero or multiple runs per session. The script auto-detects run numbers
#     by matching *_run[0-9]*.txt file patterns.
#   - Subject IDs can be anything like sub-01, sub-007, sub-XYZ. The script simply treats them
#     as folder names.
#   - A log file is created in <base_dir>/code/logs/, and the script copies itself to
#     <base_dir>/code/scripts.
#
###############################################################################

# ------------------------------------------------------------------------------
# usage() function
# ------------------------------------------------------------------------------
usage() {
    echo "
Usage: $(basename "$0") [--base-dir <project_directory>] [--session <session_name>] [--conditions <cond1,cond2,...>] [--tasks <task1,task2,...>] <subject_id1> [<subject_id2> ...]

Options:
  --base-dir <dir>      Base project directory (defaults to two levels up from script).
  --session <name>      Session name (e.g. ses-01). Defaults to 'ses-01'.
  --conditions <list>   Comma-separated conditions (e.g., cond1,cond2,cond3).
  --tasks <list>        Comma-separated tasks (e.g., task1,task2).
  -h, --help            Show usage and exit.

Examples:
  $(basename "$0") --session ses-01 sub-02 sub-03
  $(basename "$0") --base-dir /path/to/project --conditions cond1,cond2,cond3 sub-01
"
}

# ------------------------------------------------------------------------------
# Parse command-line arguments
# ------------------------------------------------------------------------------
BASE_DIR=""
SESSION=""
CONDITIONS=""
TASKS=""
SUBJECT_IDS=()

while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -h|--help)
            usage
            exit 0
            ;;
        --base-dir)
            BASE_DIR="$2"
            shift
            shift
            ;;
        --session)
            SESSION="$2"
            shift
            shift
            ;;
        --conditions)
            CONDITIONS="$2"
            shift
            shift
            ;;
        --tasks)
            TASKS="$2"
            shift
            shift
            ;;
        *)
            # Assume the rest are subject IDs
            SUBJECT_IDS+=("$1")
            shift
            ;;
    esac
done

# ------------------------------------------------------------------------------
# Script directory and defaults
# ------------------------------------------------------------------------------
SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd -P)/$(basename "$0")"
SCRIPT_DIR="$(dirname "$SCRIPT_PATH")"

# If BASE_DIR is not set, set it two levels up from script directory
if [ -z "$BASE_DIR" ]; then
    BASE_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
fi

# If SESSION is not set, default to 'ses-01'
if [ -z "$SESSION" ]; then
    SESSION="ses-01"
fi

# Ensure at least one subject ID is provided
if [ "${#SUBJECT_IDS[@]}" -lt 1 ]; then
    usage
    exit 1
fi

# Convert conditions and tasks to arrays if provided
conditions=()
if [ -n "$CONDITIONS" ]; then
    IFS=',' read -r -a conditions <<< "$CONDITIONS"
fi

tasks=()
if [ -n "$TASKS" ]; then
    IFS=',' read -r -a tasks <<< "$TASKS"
fi

# ------------------------------------------------------------------------------
# Prompt for output task name (for TSV filenames)
# ------------------------------------------------------------------------------
while true; do
    echo ""
    read -p "Enter a valid task output name (no spaces or special characters): " OUTPUT_TASK_NAME
    # Trim leading/trailing whitespace
    OUTPUT_TASK_NAME="$(echo -e "${OUTPUT_TASK_NAME}" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    if [[ "$OUTPUT_TASK_NAME" =~ ^[A-Za-z0-9_-]+$ ]]; then
        break
    else
        echo "Invalid task name. It must contain only letters, numbers, underscores, or hyphens, and no spaces."
    fi
done

# ------------------------------------------------------------------------------
# Determine which subdirectory under sourcedata/ will hold the raw text files
# ------------------------------------------------------------------------------
AVAIL_DIRS=()
for d in "$BASE_DIR/sourcedata/"*/; do
    dir_name=$(basename "$d")
    # Exclude certain directories
    if [[ "$dir_name" != "dicom" && "$dir_name" != "nifti" && "$dir_name" != "code" && "$dir_name" != "" && ! "$dir_name" =~ ^\. ]]; then
        AVAIL_DIRS+=("$dir_name")
    fi
done

if [ ${#AVAIL_DIRS[@]} -eq 0 ]; then
    echo "No directories found under sourcedata (other than dicom/nifti/code/hidden) to process raw text files."
    exit 1
elif [ ${#AVAIL_DIRS[@]} -eq 1 ]; then
    CHOSEN_DIR="${AVAIL_DIRS[0]}"
    echo "Using directory: $CHOSEN_DIR"
else
    echo -e "\nMultiple directories found under sourcedata:"
    # Print the directories with numbers
    for i in "${!AVAIL_DIRS[@]}"; do
        echo "$((i+1))) ${AVAIL_DIRS[$i]}"
    done

    # Prompt until a valid choice is made
    while true; do
        echo ""
        read -p "Select a directory by number: " choice
        if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#AVAIL_DIRS[@]}" ]; then
            CHOSEN_DIR="${AVAIL_DIRS[$((choice-1))]}"
            break
        else
            echo "Invalid selection. Please enter a number corresponding to the directory."
        fi
    done
    echo "Using directory: $CHOSEN_DIR"
fi

# ------------------------------------------------------------------------------
# Setup logging
# ------------------------------------------------------------------------------
LOG_DIR="${BASE_DIR}/code/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/$(basename $0)_$(date +%Y-%m-%d_%H-%M-%S).log"
echo "Log file created at $LOG_FILE" > "$LOG_FILE"

# ------------------------------------------------------------------------------
# Function: process_and_combine_conditions
#   For a given subject, run number, merges all *_runN*.txt files into one
#   BIDS-compliant events TSV
# ------------------------------------------------------------------------------
process_and_combine_conditions() {
    local subject_id=$1
    local run_num=$2
    local txt_dir="${BASE_DIR}/sourcedata/${CHOSEN_DIR}/${subject_id}/${SESSION}"
    local output_dir="${BASE_DIR}/${subject_id}/${SESSION}/func"

    if [ ! -d "$txt_dir" ]; then
        echo -e "Text directory not found for $subject_id: $txt_dir\n" | tee -a "$LOG_FILE"
        return
    fi

    mkdir -p "$output_dir"

    local combined_file
    combined_file=$(mktemp)
    local tsv_file="$output_dir/${subject_id}_${SESSION}_task-${OUTPUT_TASK_NAME}_run-$(printf "%02d" $run_num)_events.tsv"

    # Check if TSV file already exists
    if [ -f "$tsv_file" ]; then
        echo "TSV file already exists for run $run_num of $subject_id: $tsv_file" | tee -a "$LOG_FILE"
        return
    fi

    echo -e "onset\tduration\ttrial_type\tweight" > "$tsv_file"

    local condition_found=false

    # Find all files for this run
    files=$(find "$txt_dir" -type f -name "*_run${run_num}*.txt")
    if [ -z "$files" ]; then
        echo "No files found for run $run_num of $subject_id." | tee -a "$LOG_FILE"
        return
    fi

    echo -e "\n[Run $run_num]" | tee -a "$LOG_FILE"

    for file in $files; do
        filename=$(basename "$file")
        # Parse task and condition from filename
        if [[ $filename =~ ^(.*)_response_data_(.*)_run${run_num}.*\.txt$ ]]; then
            local parsed_task="${BASH_REMATCH[1]}"
            local parsed_condition="${BASH_REMATCH[2]}"
            echo "Processing file: $filename" | tee -a "$LOG_FILE"

            # Append onset, duration, weight to combined file
            awk 'NF==3 {print $1 "\t" $2 "\t" "'"$parsed_task"'_'"$parsed_condition"'" "\t" $3}' "$file" >> "$combined_file"
            condition_found=true
        else
            echo "File $filename does not match expected pattern." | tee -a "$LOG_FILE"
        fi
    done

    if [ "$condition_found" = true ]; then
        # Sort by onset time and write to the final TSV file
        sort -k1,1n "$combined_file" >> "$tsv_file"
        echo -e "\nCreated TSV:\n$tsv_file" | tee -a "$LOG_FILE"
    else
        echo "No valid conditions found for run $run_num of $subject_id. No TSV file created." | tee -a "$LOG_FILE"
    fi

    rm "$combined_file"
}

# ------------------------------------------------------------------------------
# Main processing loop: each subject, find runs, create events TSVs
# ------------------------------------------------------------------------------
for subject_id in "${SUBJECT_IDS[@]}"; do
    echo -e "\n=== Processing subject: $subject_id ===" | tee -a "$LOG_FILE"

    txt_dir="${BASE_DIR}/sourcedata/${CHOSEN_DIR}/${subject_id}/${SESSION}"
    if [ ! -d "$txt_dir" ]; then
        echo -e "Text directory not found for $subject_id: $txt_dir\n" | tee -a "$LOG_FILE"
        continue
    fi

    # Detect run numbers by filename pattern
    run_nums=$(find "$txt_dir" -type f -name "*_run[0-9]*.txt" | sed -E 's/.*_run([0-9]+).*/\1/' | sort -n | uniq)

    if [ -z "$run_nums" ]; then
        echo "No run numbers detected for $subject_id. Skipping subject." | tee -a "$LOG_FILE"
        continue
    fi

    for run_num in $run_nums; do
        process_and_combine_conditions "$subject_id" "$run_num"
    done

    echo -e "\n----------------------------------------" | tee -a "$LOG_FILE"
done

# ------------------------------------------------------------------------------
# Move the script to BASE_DIR/code/scripts after execution if not already there
# ------------------------------------------------------------------------------
DEST_DIR="${BASE_DIR}/code/scripts"
if [ "$SCRIPT_DIR" != "$DEST_DIR" ]; then
    mkdir -p "$DEST_DIR"
    echo "Moving script to $DEST_DIR" | tee -a "$LOG_FILE"
    cp "$SCRIPT_PATH" "$DEST_DIR/"
fi
