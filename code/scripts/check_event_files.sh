#!/bin/bash

###############################################################################
# check_event_files.sh
#
# Purpose:
#   Compare derivative event text files with the raw source text files to
#   identify any mismatches for specified conditions, runs, subjects and
#   sessions.
#
# Usage:
#   check_event_files.sh --base-dir BASE_DIR --conditions LIST --runs LIST [options]
#
# Usage Examples:
#   ./check_event_files.sh --base-dir /proj --conditions encoding recog \
#                          --runs run-01 run-02
#
# Options:
#   --base-dir BASE_DIR       Base directory of the project (required)
#   --conditions CONDITIONS   One or more conditions/trial types
#   --runs RUNS               Runs to check (e.g., run-01 run-02)
#   --subjects SUBJECTS       Subjects to include
#   --sessions SESSIONS       Sessions to include
#   --help                    Display help
#
# Requirements:
#   bash, diff and standard UNIX utilities
#
# Notes:
#   Creates a timestamped log under code/logs and prints differences between
#   derivative and raw files.
#
###############################################################################

# Default values
BASE_DIR=""
CONDITIONS=()
RUNS=()
SUBJECTS=()
SESSIONS=()
LOG_DIR=""
LOG_FILE=""

# Function to display help
usage() {
    echo "Usage: $0 --base-dir BASE_DIR --conditions CONDITIONS --runs RUNS [options]"
    echo ""
    echo "Options:"
    echo "  --base-dir BASE_DIR       Base directory of the project (required)"
    echo "  --conditions CONDITIONS   Conditions/trial types to check (required, multiple allowed)"
    echo "  --runs RUNS               Runs to check (e.g., run-01 run-02 run-03)"
    echo "  --subjects SUBJECTS       Subjects to process (e.g., sub-01 sub-02)"
    echo "  --sessions SESSIONS       Sessions to process (e.g., ses-01 ses-02)"
    echo "  --help                    Display this help message"
    exit 1
}

# Parse arguments
if [ "$#" -eq 0 ]; then
    usage
fi

while [[ "$1" != "" ]]; do
    case $1 in
        --base-dir )
            shift
            BASE_DIR="$1"
            shift
            ;;
        --conditions )
            shift
            while [[ "$1" != "" && "$1" != --* ]]; do
                CONDITIONS+=("$1")
                shift
            done
            ;;
        --runs )
            shift
            while [[ "$1" != "" && "$1" != --* ]]; do
                RUNS+=("$1")
                shift
            done
            ;;
        --subjects )
            shift
            while [[ "$1" != "" && "$1" != --* ]]; do
                SUBJECTS+=("$1")
                shift
            done
            ;;
        --sessions )
            shift
            while [[ "$1" != "" && "$1" != --* ]]; do
                SESSIONS+=("$1")
                shift
            done
            ;;
        --help )
            usage
            ;;
        * )
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

# Check required arguments
if [ -z "$BASE_DIR" ]; then
    echo "Error: --base-dir is required"
    usage
fi

if [ ${#CONDITIONS[@]} -eq 0 ]; then
    echo "Error: --conditions is required"
    usage
fi

if [ ${#RUNS[@]} -eq 0 ]; then
    echo "Error: --runs is required"
    usage
fi

# Set default subjects and sessions if not specified
if [ ${#SUBJECTS[@]} -eq 0 ]; then
    # Find all subjects in the base directory
    SUBJECTS=($(find "$BASE_DIR" -maxdepth 1 -type d -name "sub-*" -exec basename {} \;))
fi

if [ ${#SESSIONS[@]} -eq 0 ]; then
    # Default to ses-01
    SESSIONS=("ses-01")
fi

# Set up logging
LOG_DIR="${BASE_DIR}/code/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/check_event_files_$(date '+%Y-%m-%d_%H-%M-%S').log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "Starting event file comparison at $(date)"
echo "Base directory: $BASE_DIR"
echo "Conditions: ${CONDITIONS[@]}"
echo "Runs: ${RUNS[@]}"
echo "Subjects: ${SUBJECTS[@]}"
echo "Sessions: ${SESSIONS[@]}"
echo "Log file: $LOG_FILE"
echo "--------------------------------------------"

# Function to compare two files
compare_files() {
    local file1="$1"
    local file2="$2"
    local subj="$3"
    local sess="$4"
    local run="$5"
    local condition="$6"

    echo "Comparing files for subject $subj, session $sess, run $run, condition $condition:"
    echo "Derivative file: $file1"
    echo "Raw file:        $file2"

    if [ ! -f "$file1" ]; then
        echo "Derivative file not found: $file1"
        echo "Result: Files do not match (Derivative file missing)"
        echo ""
        return
    fi

    if [ ! -f "$file2" ]; then
        echo "Raw file not found: $file2"
        echo "Result: Files do not match (Raw file missing)"
        echo ""
        return
    fi

    # Compare the files
    diff_output=$(diff -y --suppress-common-lines "$file1" "$file2")
    if [ -z "$diff_output" ]; then
        echo "Result: Files match"
        echo ""
    else
        echo "Result: Files do not match"
        echo "Differences:"
        echo "$diff_output"
        echo ""
    fi
}

# Main comparison loop
for subj in "${SUBJECTS[@]}"; do
    for sess in "${SESSIONS[@]}"; do
        for run in "${RUNS[@]}"; do
            for condition in "${CONDITIONS[@]}"; do
                # Construct derivative file path
                derivative_dir="${BASE_DIR}/derivatives/custom_events/${subj}/${sess}"
                derivative_file="${derivative_dir}/${subj}_${sess}_${run}_desc-${condition}_events.txt"

                # Extract run number without leading zeros
                run_number=$(echo "$run" | grep -o '[0-9]\+' | sed 's/^0*//')

                # Extract task and condition name
                if [[ "$condition" == encoding_* ]]; then
                    task="encoding"
                    cond_name="${condition#encoding_}"
                elif [[ "$condition" == recog_* ]]; then
                    task="recog"
                    cond_name="${condition#recog_}"
                else
                    task=""
                    cond_name="$condition"
                fi

                # Assume session code is BASELINE
                session_code="BASELINE"

                # Construct raw file pattern
                raw_dir="${BASE_DIR}/sourcedata/custom_txt/${subj}/${sess}"
                raw_file_pattern="${raw_dir}/${task}_response_data_${cond_name}_run${run_number}_*.txt"

                # Find raw file(s) matching the pattern
                raw_files=( $raw_file_pattern )
                if [ ${#raw_files[@]} -eq 0 ]; then
                    echo "Raw file not found matching pattern: $raw_file_pattern"
                    echo "Result: Files do not match (Raw file missing)"
                    echo ""
                    continue
                fi

                # Use the first matching raw file
                raw_file="${raw_files[0]}"

                # Compare the files
                compare_files "$derivative_file" "$raw_file" "$subj" "$sess" "$run" "$condition"
            done
        done
    done
done

echo "Event file comparison completed at $(date)"
