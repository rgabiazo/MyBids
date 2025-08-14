#!/bin/bash
###############################################################################
# run_fieldmap_correction.sh
#
# Purpose:
#   Apply TOPUP-based distortion correction to BOLD data using AP/PA images.
#
# Usage:
#   run_fieldmap_correction.sh --base-dir DIR --preproc-type task|rest [--session SES...] [SUBJECTS...]
#
# Usage Examples:
#   run_fieldmap_correction.sh --base-dir /path/to/BIDS --preproc-type task
#   run_fieldmap_correction.sh --base-dir /path/to/BIDS --preproc-type rest --session ses-01 sub-01 sub-02
#
# Options:
#   --base-dir DIR      Base BIDS directory (required)
#   --preproc-type TYPE task or rest
#   --session SES       Sessions to process
#   -h, --help          Show help
#
# Requirements:
#   FSL tools (topup, fslroi, fslmerge, applytopup) and jq
#
# Notes:
#   Outputs are stored in derivatives/fsl/topup and intermediate files are removed.
#
###############################################################################

BASE_DIR=""
SESSIONS=()
SUBJECTS=()
PREPROCESSING_TYPE=""
SUBJECT_PREFIXES=("sub" "pilot")

# Map PhaseEncodingDirection to a human readable label (AP/PA)
map_phase_dir_to_label() {
    case "$1" in
        j) echo "AP" ;;
        j-) echo "PA" ;;
        *) echo "" ;;
    esac
}

usage() {
    echo "Usage: $0 --base-dir BASE_DIR [options] [--session SESSIONS...] [--preproc-type task|rest] [SUBJECTS...]"
    exit 1
}

# Parse arguments
while [[ "$1" != "" ]]; do
    case $1 in
        -- )
            shift
            break
            ;;
        --base-dir )
            shift
            BASE_DIR="$1"
            ;;
        --session )
            shift
            if [[ "$1" == "" || "$1" == --* ]]; then
                echo "Error: --session requires an argument"
                usage
            fi
            SESSIONS+=("$1")
            ;;
        --preproc-type )
            shift
            if [[ "$1" != "task" && "$1" != "rest" ]]; then
                echo "Error: --preproc-type must be 'task' or 'rest'"
                usage
            fi
            PREPROCESSING_TYPE="$1"
            ;;
        -h | --help )
            usage
            ;;
        --* )
            echo "Unknown option: $1"
            usage
            ;;
        * )
            SUBJECTS+=("$1")
            ;;
    esac
    shift
done

while [[ "$1" != "" ]]; do
    SUBJECTS+=("$1")
    shift
done

if [ -z "$BASE_DIR" ]; then
    echo "Error: --base-dir is required"
    usage
fi

if [ -z "$PREPROCESSING_TYPE" ]; then
    echo "Error: --preproc-type is required and must be 'task' or 'rest'"
    usage
fi

while [ ! -d "$BASE_DIR" ]; do
    echo "Error: Base directory '$BASE_DIR' does not exist."
    read -p "Please enter a valid base directory: " BASE_DIR
done

LOG_DIR="${BASE_DIR}/code/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/run_fieldmap_correction_$(date '+%Y-%m-%d_%H-%M-%S').log"

# Verify required commands are available
REQUIRED_CMDS=(fslroi fslmerge topup applytopup jq)
for cmd in "${REQUIRED_CMDS[@]}"; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "Error: '$cmd' command not found. Please install it before running this script." | tee -a "$LOG_FILE"
        exit 1
    fi
done

shopt -s extglob

{
    if [ ${#SUBJECTS[@]} -eq 0 ]; then
        SUBJECTS=()
        for prefix in "${SUBJECT_PREFIXES[@]}"; do
            for subj_dir in "$BASE_DIR"/${prefix}-*; do
                [ -d "$subj_dir" ] && SUBJECTS+=("$(basename "$subj_dir")")
            done
        done
        IFS=$'\n' SUBJECTS=($(printf "%s\n" "${SUBJECTS[@]}" | sort -uV))
    fi

    SUBJECT_COUNT=${#SUBJECTS[@]}
    echo "Found $SUBJECT_COUNT subject directories."
    echo ""

    for SUBJ_ID in "${SUBJECTS[@]}"; do
        echo "=== Processing subject: $SUBJ_ID ==="

        SESSION_DIRS=()
        if [ ${#SESSIONS[@]} -gt 0 ]; then
            for ses in "${SESSIONS[@]}"; do
                if [ -d "$BASE_DIR/$SUBJ_ID/$ses" ]; then
                    SESSION_DIRS+=("$BASE_DIR/$SUBJ_ID/$ses")
                fi
            done
        else
            for ses_dir in "$BASE_DIR/$SUBJ_ID"/ses-*; do
                [ -d "$ses_dir" ] && SESSION_DIRS+=("$ses_dir")
            done
            IFS=$'\n' SESSION_DIRS=($(printf "%s\n" "${SESSION_DIRS[@]}" | sort -V))
        fi

        if [ ${#SESSION_DIRS[@]} -eq 0 ]; then
            # allow processing subject without sessions
            SESSION_DIRS=("$BASE_DIR/$SUBJ_ID")
        fi

        for SES_DIR in "${SESSION_DIRS[@]}"; do
            if [ "$SES_DIR" = "$BASE_DIR/$SUBJ_ID" ]; then
                SES_ID=""
                FUNC_DIR="$SES_DIR/func"
            else
                SES_ID="$(basename "$SES_DIR")"
                FUNC_DIR="$SES_DIR/func"
            fi
            [ ! -d "$FUNC_DIR" ] && continue

            BOLD_FILES=()
            if [ "$PREPROCESSING_TYPE" == "task" ]; then
                while IFS= read -r line; do
                    BOLD_FILES+=("$line")
                done < <(find "$FUNC_DIR" -type f -name "*_task-*_bold.nii.gz" ! -name "*_task-rest_bold.nii.gz" | sort -V)
            else
                while IFS= read -r line; do
                    BOLD_FILES+=("$line")
                done < <(find "$FUNC_DIR" -type f -name "*_task-rest_bold.nii.gz" | sort -V)
            fi

            if [ -z "$SES_ID" ]; then
                DERIV_TOPUP_DIR="$BASE_DIR/derivatives/fsl/topup/$SUBJ_ID"
            else
                DERIV_TOPUP_DIR="$BASE_DIR/derivatives/fsl/topup/$SUBJ_ID/$SES_ID"
            fi
            FUNC_DERIV_DIR="$DERIV_TOPUP_DIR/func"
            FMAP_DERIV_DIR="$DERIV_TOPUP_DIR/fmap"
            mkdir -p "$FUNC_DERIV_DIR" "$FMAP_DERIV_DIR"

            for BOLD_FILE in "${BOLD_FILES[@]}"; do
                BOLD_BASENAME="$(basename "$BOLD_FILE" .nii.gz)"
                # Determine run number only if task-based and not rest
                if [ "$PREPROCESSING_TYPE" == "task" ]; then
                    RUN_NUMBER=$(echo "$BOLD_BASENAME" | grep -o 'run-[0-9]\+')
                    [ -z "$RUN_NUMBER" ] && RUN_NUMBER="run-01"
                    RUN_NUMBER_ENTITY="_${RUN_NUMBER}"
                else
                    RUN_NUMBER=""
                    RUN_NUMBER_ENTITY=""
                fi

                TASK_NAME=$(echo "$BOLD_BASENAME" | grep -o 'task-[^_]\+' | sed 's/task-//')
                if [ "$PREPROCESSING_TYPE" == "rest" ]; then
                    DISPLAY_LINE="--- Session: $SES_ID (rest) ---"
                else
                    DISPLAY_LINE="--- Session: $SES_ID | ${RUN_NUMBER:-run-01} ---"
                fi

                echo "$DISPLAY_LINE"
                echo "BOLD file: $BOLD_FILE"
                echo ""

                CORRECTED_BOLD="$FUNC_DERIV_DIR/${BOLD_BASENAME/_bold/_desc-topupcorrected_bold}.nii.gz"
                if [ -f "$CORRECTED_BOLD" ]; then
                    echo "Topup correction already applied for $SUBJ_ID $SES_ID $RUN_NUMBER. Skipping."
                    echo ""
                    continue
                fi

                echo "Correcting BOLD data for susceptibility distortions using topup for $SUBJ_ID $SES_ID $RUN_NUMBER."

                if [ -n "$TASK_NAME" ]; then
                    TASK_ENTITY="_task-${TASK_NAME}"
                else
                    TASK_ENTITY=""
                fi

                if [ -z "$SES_ID" ]; then
                    prefix="${SUBJ_ID}"
                else
                    prefix="${SUBJ_ID}_${SES_ID}"
                fi

                BOLD_JSON="${BOLD_FILE%.nii.gz}.json"
                PHASE_DIR=$(jq -r '.PhaseEncodingDirection' "$BOLD_JSON")
                READOUT_TIME=$(jq -r '.TotalReadoutTime' "$BOLD_JSON")

                if [[ "$BOLD_BASENAME" == *"_dir-AP_"* ]]; then
                    DIR_LABEL="AP"
                elif [[ "$BOLD_BASENAME" == *"_dir-PA_"* ]]; then
                    DIR_LABEL="PA"
                else
                    DIR_LABEL=$(map_phase_dir_to_label "$PHASE_DIR")
                    if [ -z "$DIR_LABEL" ]; then
                        echo ""
                        echo "Unsupported PhaseEncodingDirection: $PHASE_DIR. Skipping."
                        echo ""
                        continue
                    fi
                fi
                if [ "$DIR_LABEL" = "AP" ]; then
                    OPP_LABEL="PA"
                else
                    OPP_LABEL="AP"
                fi

                AP_IMAGE="$FMAP_DERIV_DIR/${prefix}${TASK_ENTITY}${RUN_NUMBER_ENTITY}_acq-${DIR_LABEL}_epi.nii.gz"
                ACQ_PARAMS_FILE="$FMAP_DERIV_DIR/${prefix}${TASK_ENTITY}${RUN_NUMBER_ENTITY}_acq-params.txt"
                MERGED_AP_PA="$FMAP_DERIV_DIR/${prefix}${TASK_ENTITY}${RUN_NUMBER_ENTITY}_acq-${DIR_LABEL}_${OPP_LABEL}_merged.nii.gz"
                TOPUP_OUTPUT_BASE="$FMAP_DERIV_DIR/${prefix}${TASK_ENTITY}${RUN_NUMBER_ENTITY}_topup"

                echo ""
                echo "[Step 1] Extracting first volume of BOLD (${DIR_LABEL}):"
                echo ""
                echo "  - Input BOLD file: $BOLD_FILE"
                echo "  - Output ${DIR_LABEL} image: $AP_IMAGE"
                fslroi "$BOLD_FILE" "$AP_IMAGE" 0 1
                echo ""

                SEARCH_LABEL="$OPP_LABEL"
                if [ "$PREPROCESSING_TYPE" == "task" ] && [ -n "$TASK_NAME" ]; then
                    PREFIX="*task-${TASK_NAME}_"
                elif [ "$PREPROCESSING_TYPE" == "rest" ]; then
                    PREFIX="*task-rest_"
                else
                    PREFIX="*"
                fi

                # Search order: first try explicit fieldmap images in fmap/
                # (supports *.nii.gz and *.nii), then fall back to matching
                # BOLD runs or files located in the func/ directory
                PA_FILE=$(find "$SES_DIR/fmap" -type f -name "*_dir-${SEARCH_LABEL}_epi.nii.gz" -print -quit)
                if [ -z "$PA_FILE" ]; then
                    PA_FILE=$(find "$SES_DIR/fmap" -type f -name "*_dir-${SEARCH_LABEL}_epi.nii" -print -quit)
                fi

                # If not found, look for matching BOLD runs or fallback to func/
                if [ -z "$PA_FILE" ]; then
                    PA_FILE=$(find "$SES_DIR/fmap" -type f -name "${PREFIX}dir-${SEARCH_LABEL}_bold.nii.gz" -print -quit)
                fi
                if [ -z "$PA_FILE" ]; then
                    PA_FILE=$(find "$SES_DIR/fmap" -type f -name "${PREFIX}dir-${SEARCH_LABEL}_bold.nii" -print -quit)
                fi
                if [ -z "$PA_FILE" ]; then
                    PA_FILE=$(find "$FUNC_DIR" -type f -name "${PREFIX}dir-${SEARCH_LABEL}_epi.nii.gz" -print -quit)
                fi
                if [ -z "$PA_FILE" ]; then
                    PA_FILE=$(find "$FUNC_DIR" -type f -name "${PREFIX}dir-${SEARCH_LABEL}_epi.nii" -print -quit)
                fi
                if [ -z "$PA_FILE" ]; then
                    PA_FILE=$(find "$FUNC_DIR" -type f -name "${PREFIX}dir-${SEARCH_LABEL}_bold.nii.gz" -print -quit)
                fi
                if [ -z "$PA_FILE" ]; then
                    PA_FILE=$(find "$FUNC_DIR" -type f -name "${PREFIX}dir-${SEARCH_LABEL}_bold.nii" -print -quit)
                fi
                # --------------------------------------------------

                echo ""
                if [ -z "$PA_FILE" ]; then
                    echo ""
                    echo "  - No PA image found. Skipping topup for this run."
                    echo ""
                    continue
                fi

                PA_JSON="${PA_FILE%.nii.gz}.json"
                PA_PHASE_DIR=$(jq -r '.PhaseEncodingDirection' "$PA_JSON")
                PA_READOUT_TIME=$(jq -r '.TotalReadoutTime' "$PA_JSON")

                if [[ "$PA_FILE" == *"_dir-AP_"* ]]; then
                    FMAP_LABEL="AP"
                elif [[ "$PA_FILE" == *"_dir-PA_"* ]]; then
                    FMAP_LABEL="PA"
                else
                    FMAP_LABEL=$(map_phase_dir_to_label "$PA_PHASE_DIR")
                fi
                [ -z "$FMAP_LABEL" ] && FMAP_LABEL="$OPP_LABEL"

                PA_IMAGE="$FMAP_DERIV_DIR/${prefix}${TASK_ENTITY}${RUN_NUMBER_ENTITY}_acq-${FMAP_LABEL}_epi.nii.gz"
                MERGED_AP_PA="$FMAP_DERIV_DIR/${prefix}${TASK_ENTITY}${RUN_NUMBER_ENTITY}_acq-${DIR_LABEL}_${FMAP_LABEL}_merged.nii.gz"

                echo "[Step 2] Extracting first volume of ${FMAP_LABEL}:"
                echo ""
                echo "  - Input ${FMAP_LABEL} image: $PA_FILE"
                echo "  - Output ${FMAP_LABEL} image: $PA_IMAGE"
                fslroi "$PA_FILE" "$PA_IMAGE" 0 1
                echo ""

                if [ "$DIR_LABEL" = "AP" ]; then
                    echo "0 1 0 $READOUT_TIME" > "$ACQ_PARAMS_FILE"
                else
                    echo "0 -1 0 $READOUT_TIME" > "$ACQ_PARAMS_FILE"
                fi

                if [ "$FMAP_LABEL" = "AP" ]; then
                    echo "0 1 0 $PA_READOUT_TIME" >> "$ACQ_PARAMS_FILE"
                else
                    echo "0 -1 0 $PA_READOUT_TIME" >> "$ACQ_PARAMS_FILE"
                fi

                echo ""
                echo "[Step 3] Merging ${DIR_LABEL} and ${FMAP_LABEL} images:"
                echo ""
                echo "  - Input ${DIR_LABEL}: $AP_IMAGE"
                echo "  - Input ${FMAP_LABEL}: $PA_IMAGE"
                echo "  - Output: $MERGED_AP_PA"
                fslmerge -t "$MERGED_AP_PA" "$AP_IMAGE" "$PA_IMAGE"
                echo ""

                echo ""
                echo "[Step 4] Estimating susceptibility (topup):"
                echo ""
                echo "  - Input (merged ${DIR_LABEL} and ${FMAP_LABEL}): $MERGED_AP_PA"
                echo "  - Acquisition parameters file: $ACQ_PARAMS_FILE"
                echo "  - Output base: ${TOPUP_OUTPUT_BASE}_results"
                echo "  - Fieldmap output: ${TOPUP_OUTPUT_BASE}_fieldmap.nii.gz"
                topup --imain="$MERGED_AP_PA" --datain="$ACQ_PARAMS_FILE" --config=b02b0.cnf \
                      --out="${TOPUP_OUTPUT_BASE}_results" --fout="${TOPUP_OUTPUT_BASE}_fieldmap.nii.gz"
                echo ""

                echo ""
                echo "[Step 5] Applying topup to BOLD data:"
                echo ""
                echo "  - Input: $BOLD_FILE"
                echo "  - Output: $CORRECTED_BOLD"
                applytopup --imain="$BOLD_FILE" --topup="${TOPUP_OUTPUT_BASE}_results" \
                           --datain="$ACQ_PARAMS_FILE" --inindex=1 --method=jac --out="$CORRECTED_BOLD"
                echo ""

                if [ "$PREPROCESSING_TYPE" == "task" ]; then
                    if [ -n "$TASK_NAME" ]; then
                        if [ -z "$SES_ID" ]; then
                            FIELD_MAP="$FMAP_DERIV_DIR/${SUBJ_ID}_task-${TASK_NAME}${RUN_NUMBER_ENTITY}_fieldmap.nii.gz"
                        else
                            FIELD_MAP="$FMAP_DERIV_DIR/${SUBJ_ID}_${SES_ID}_task-${TASK_NAME}${RUN_NUMBER_ENTITY}_fieldmap.nii.gz"
                        fi
                    else
                        if [ -z "$SES_ID" ]; then
                            FIELD_MAP="$FMAP_DERIV_DIR/${SUBJ_ID}${RUN_NUMBER_ENTITY}_fieldmap.nii.gz"
                        else
                            FIELD_MAP="$FMAP_DERIV_DIR/${SUBJ_ID}_${SES_ID}${RUN_NUMBER_ENTITY}_fieldmap.nii.gz"
                        fi
                    fi
                else
                    if [ -z "$SES_ID" ]; then
                        FIELD_MAP="$FMAP_DERIV_DIR/${SUBJ_ID}_task-rest_fieldmap.nii.gz"
                    else
                        FIELD_MAP="$FMAP_DERIV_DIR/${SUBJ_ID}_${SES_ID}_task-rest_fieldmap.nii.gz"
                    fi
                fi
                mv "${TOPUP_OUTPUT_BASE}_fieldmap.nii.gz" "$FIELD_MAP"

                # Cleanup
                rm -f "$AP_IMAGE" "$PA_IMAGE" "$MERGED_AP_PA" \
                      "${TOPUP_OUTPUT_BASE}_results_fieldcoef.nii.gz" \
                      "${TOPUP_OUTPUT_BASE}_results_movpar.txt"
                echo ""
            done
        done
    done

    echo "Fieldmap correction completed."
    echo "------------------------------------------------------------------------------"
} 2>&1 | tee -a "$LOG_FILE"
