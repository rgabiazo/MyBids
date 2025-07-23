#!/bin/bash
#
###############################################################################
# create_event_files.sh
#
# Purpose:
#   Convert BIDS events.tsv files into 3-column text files (onset, duration,
#   amplitude=1) for use with FSL FEAT.
#
# Usage:
#   create_event_files.sh --base-dir DIR --num-runs N --trial-type TYPE [options] [SUBJECTS...]
#
# Usage Examples:
#   1) create_event_files.sh --base-dir /myproj --num-runs 2 --trial-type encoding_pair sub-01 sub-02
#   2) create_event_files.sh --base-dir /myproj --num-runs 3 --trial-type face --trial-type place
#   3) create_event_files.sh --base-dir /myproj --session ses-01 --num-runs 1 --trial-type recog_pair
#
# Options:
#   --base-dir DIR         Base directory of the project (required)
#   --num-runs N           Number of runs to process
#   --trial-type TYPE      Trial type(s) to extract
#   --session NAME         Session(s) to process
#   -h, --help             Show help
#
# Requirements:
#   bash
#
# Notes:
#   Outputs .txt files under <base-dir>/derivatives/custom_events/<sub>/<ses>.
#   If no subjects are provided, directories named sub-* or pilot-* are detected.
#
###############################################################################

BASE_DIR=""
NUM_RUNS=""
TRIAL_TYPES=()
SESSIONS=()
SUBJECTS=()
SUBJECT_PREFIXES=("sub" "pilot")

usage() {
    echo "Usage: $0 --base-dir <dir> --num-runs <N> --trial-type <type> [options] [SUBJECTS...]"
    echo ""
    echo "Options:"
    echo "  --base-dir <dir>     Base directory of the project (required)"
    echo "  --num-runs <N>       Number of runs (required)"
    echo "  --trial-type <type>  One or more trial types"
    echo "  --session <name>     Session(s) (e.g., ses-01)"
    echo "  -h, --help           Show usage info and exit"
    exit 1
}

POSITIONAL=()
while [[ "$1" != "" ]]; do
    case $1 in
        --base-dir )
            shift
            BASE_DIR="$1"
            ;;
        --num-runs )
            shift
            NUM_RUNS="$1"
            ;;
        --trial-type )
            shift
            TRIAL_TYPES+=("$1")
            ;;
        --session )
            shift
            SESSIONS+=("$1")
            ;;
        -h|--help )
            usage
            ;;
        -- )
            shift
            while [[ "$1" != "" ]]; do
                POSITIONAL+=("$1")
                shift
            done
            ;;
        -* )
            echo "Unknown option: $1"
            usage
            ;;
        * )
            POSITIONAL+=("$1")
            ;;
    esac
    shift
done

SUBJECTS=("${POSITIONAL[@]}")

if [ -z "$BASE_DIR" ]; then
    echo "Error: --base-dir is required"
    usage
fi
if [ -z "$NUM_RUNS" ]; then
    echo "Error: --num-runs is required"
    usage
fi
if [ ${#TRIAL_TYPES[@]} -eq 0 ]; then
    echo "Error: At least one --trial-type is required"
    usage
fi

while [ ! -d "$BASE_DIR" ]; do
    echo "Base dir '$BASE_DIR' does not exist."
    read -p "Enter valid base dir: " BASE_DIR
done

LOG_DIR="${BASE_DIR}/code/logs"
mkdir -p "$LOG_DIR"
SCRIPT_NAME=$(basename "$0")
LOG_FILE="${LOG_DIR}/${SCRIPT_NAME%.*}_$(date '+%Y-%m-%d_%H-%M-%S').log"

exec > >(tee -i "$LOG_FILE") 2>&1

EVENTS_DIR="${BASE_DIR}/derivatives/custom_events"

# If no subjects provided, find all
if [ ${#SUBJECTS[@]} -eq 0 ]; then
    # sub-*
    SUBJECTS=($(find "$BASE_DIR" -maxdepth 1 -type d -name "sub-*" -exec basename {} \;))
    # pilot-*
    PILOT_SUBJS=($(find "$BASE_DIR" -maxdepth 1 -type d -name "pilot-*" -exec basename {} \;))
    SUBJECTS+=("${PILOT_SUBJS[@]}")
    IFS=$'\n' SUBJECTS=($(printf "%s\n" "${SUBJECTS[@]}" | sort -uV))
fi

echo -e "\nFound ${#SUBJECTS[@]} subject directories.\n"

for subj in "${SUBJECTS[@]}"; do
    echo "=== Processing subject: $subj ==="

    SESSION_DIRS=()
    if [ ${#SESSIONS[@]} -gt 0 ]; then
        for ses in "${SESSIONS[@]}"; do
            [ -d "$BASE_DIR/$subj/$ses" ] && SESSION_DIRS+=("$BASE_DIR/$subj/$ses") || echo "Warning: $subj/$ses not found"
        done
    else
        for ses_dir in "$BASE_DIR/$subj"/ses-*; do
            [ -d "$ses_dir" ] && SESSION_DIRS+=("$ses_dir")
        done
        IFS=$'\n' SESSION_DIRS=($(printf "%s\n" "${SESSION_DIRS[@]}" | sort -V))
    fi

    if [ ${#SESSION_DIRS[@]} -eq 0 ]; then
        # allow subjects without sessions
        SESSION_DIRS=("$BASE_DIR/$subj")
    fi

    for ses_dir in "${SESSION_DIRS[@]}"; do
        if [ "$ses_dir" = "$BASE_DIR/$subj" ]; then
            ses=""
            func_dir="$ses_dir/func"
        else
            ses=$(basename "$ses_dir")
            func_dir="$ses_dir/func"
        fi
        [ ! -d "$func_dir" ] && continue

        EVENT_FILES=()
        for (( run=1; run<=$NUM_RUNS; run++ )); do
            run_str=$(printf "%02d" $run)
            found_events=($(find "$func_dir" -type f -name "${subj}_${ses}_*run-${run_str}_*events.tsv" | sort -V))
            if [ ${#found_events[@]} -gt 0 ]; then
                EVENT_FILES+=("${found_events[0]}")
            fi
        done

        if [ ${#EVENT_FILES[@]} -eq 0 ]; then
            echo "No event TSV files found for $subj $ses."
            echo ""
            continue
        fi

        for events_file in "${EVENT_FILES[@]}"; do
            run_str=$(echo "$events_file" | sed -E 's/.*_run-([0-9]+)_events\.tsv/\1/')
            if [ -z "$ses" ]; then
                echo "--- Session: none | Run: run-$run_str ---"
            else
                echo "--- Session: $ses | Run: run-$run_str ---"
            fi
            echo "TSV file: $events_file"
            echo ""
            if [ -z "$ses" ]; then
                output_dir="${EVENTS_DIR}/${subj}"
            else
                output_dir="${EVENTS_DIR}/${subj}/${ses}"
            fi
            mkdir -p "$output_dir"

            for trial_type in "${TRIAL_TYPES[@]}"; do
                if [ -z "$ses" ]; then
                    output_file="${output_dir}/${subj}_run-${run_str}_desc-${trial_type}_events.txt"
                else
                    output_file="${output_dir}/${subj}_${ses}_run-${run_str}_desc-${trial_type}_events.txt"
                fi

                echo "Creating events for $trial_type:"
                echo "  - Input: $events_file"
                echo "  - Output: $output_file"

                if [ -f "$output_file" ]; then
                    echo "  File already exists, skipping."
                    echo ""
                    continue
                fi

                awk -F '\t' -v tt="$trial_type" '
                    BEGIN {oncol=0;durcol=0;typecol=0}
                    NR==1 {
                        for (i=1;i<=NF;i++){
                            if($i=="trial_type") typecol=i
                            if($i=="onset") oncol=i
                            if($i=="duration") durcol=i
                        }
                    }
                    NR>1 && typecol>0 && $typecol==tt {
                        printf "%.1f %.3f %.3f\n", $oncol, $durcol, 1.000
                    }' "$events_file" > "$output_file"

                echo ""
            done
        done
    done
done

echo "Event file creation completed."
echo "------------------------------------------------------------------------------"
