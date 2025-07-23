#!/bin/bash
###############################################################################
# run_bet_extraction.sh
#
# Purpose:
#   Apply FSL BET to T1w images with optional reorientation.
#
# Usage:
#   run_bet_extraction.sh --base-dir DIR [options] [SUBJECTS...]
#
# Usage Examples:
#   run_bet_extraction.sh --base-dir /proj sub-01 sub-02
#   run_bet_extraction.sh --base-dir /proj --reorient
#
# Options:
#   --base-dir DIR     Base project directory (required)
#   --reorient         Reorient images with fslreorient2std
#   --bet-option FLAG  BET flag (e.g., -R, -S, -B)
#   --frac VALUE       Fractional intensity threshold
#   --session SES      Session(s) to process
#   -h, --help         Show help
#
# Requirements:
#   FSL (bet, fslreorient2std)
#
# Notes:
#   Output skull-stripped images are placed under derivatives/fsl.
#
###############################################################################

# ------------------------------------------------------------------------------
BASE_DIR=""
REORIENT="no"
BET_OPTION=""
FRAC_INTENSITY="0.5"
SESSIONS=()
SUBJECTS=()
SUBJECT_PREFIXES=("sub" "subj" "participant" "P" "pilot" "pilsub")

usage() {
    echo "Usage: $0 --base-dir <BASE_DIR> [options] [SUBJECTS...]"
    echo ""
    echo "Options:"
    echo "  --base-dir <dir>     Base directory of the project (required)"
    echo "  --reorient           Apply fslreorient2std to T1w images"
    echo "  --bet-option <flag>  BET option (e.g. -R, -S, -B)"
    echo "  --frac <value>       Fractional intensity threshold (default: 0.5)"
    echo "  --session <name>     Session(s), e.g., --session ses-01"
    echo "  SUBJECTS             e.g., sub-01 sub-02"
    echo "  -h, --help           Show this help message"
    exit 1
}

# ------------------------------------------------------------------------------
# Parse CLI Arguments
# ------------------------------------------------------------------------------
POSITIONAL_ARGS=()
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
        --reorient )
            REORIENT="yes"
            ;;
        --bet-option )
            shift
            BET_OPTION="$1"
            ;;
        --frac )
            shift
            FRAC_INTENSITY="$1"
            ;;
        --session )
            shift
            if [[ "$1" == "" || "$1" == --* ]]; then
                echo "Error: --session requires an argument"
                usage
            fi
            SESSIONS+=("$1")
            ;;
        -h|--help )
            usage
            ;;
        -* )
            echo "Unknown option: $1"
            usage
            ;;
        * )
            break
            ;;
    esac
    shift
done

while [[ "$1" != "" ]]; do
    POSITIONAL_ARGS+=("$1")
    shift
done
SUBJECTS=("${POSITIONAL_ARGS[@]}")

if [ -z "$BASE_DIR" ]; then
    echo "Error: --base-dir is required"
    usage
fi

while [ ! -d "$BASE_DIR" ]; do
    echo -e "\nError: Base directory '$BASE_DIR' does not exist."
    read -p "Please enter a valid base directory: " BASE_DIR
done

LOG_DIR="${BASE_DIR}/code/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/run_bet_extraction_$(date '+%Y-%m-%d_%H-%M-%S').log"

# ------------------------------------------------------------------------------
# Start logging
# ------------------------------------------------------------------------------
{
    echo "Base directory: $BASE_DIR" >> "$LOG_FILE"
    echo "Reorient: $REORIENT" >> "$LOG_FILE"
    echo "BET option: $BET_OPTION" >> "$LOG_FILE"
    echo "Fractional intensity threshold: $FRAC_INTENSITY" >> "$LOG_FILE"
    if [ ${#SESSIONS[@]} -gt 0 ]; then
        echo "Sessions: ${SESSIONS[@]}" >> "$LOG_FILE"
    fi
    if [ ${#SUBJECTS[@]} -gt 0 ]; then
        echo "Subjects: ${SUBJECTS[@]}" >> "$LOG_FILE"
    fi
    echo "Logging to: $LOG_FILE" >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"

    # --------------------------------------------------------------------------
    # Verify required external commands
    # --------------------------------------------------------------------------
    REQUIRED_CMDS=("bet")
    if [ "$REORIENT" = "yes" ]; then
        REQUIRED_CMDS+=("fslreorient2std")
    fi
    MISSING_CMDS=()
    for cmd in "${REQUIRED_CMDS[@]}"; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            MISSING_CMDS+=("$cmd")
        fi
    done
    if [ ${#MISSING_CMDS[@]} -ne 0 ]; then
        echo "Error: Required command(s) missing: ${MISSING_CMDS[*]}" | tee -a "$LOG_FILE"
        exit 1
    fi

    # --------------------------------------------------------------------------
    # Identify subjects
    # --------------------------------------------------------------------------
    SUBJECT_DIRS=()
    if [ ${#SUBJECTS[@]} -gt 0 ]; then
        # Use the specified subjects
        for subj in "${SUBJECTS[@]}"; do
            SUBJ_DIR="$BASE_DIR/$subj"
            if [ -d "$SUBJ_DIR" ]; then
                SUBJECT_DIRS+=("$SUBJ_DIR")
            else
                echo -e "Warning: Subject directory not found:\n  - $SUBJ_DIR" | tee -a "$LOG_FILE"
            fi
        done
    else
        # Auto-detect subject directories with known prefixes
        for prefix in "${SUBJECT_PREFIXES[@]}"; do
            for subj_dir in "$BASE_DIR"/${prefix}-*; do
                [ -d "$subj_dir" ] && SUBJECT_DIRS+=("$subj_dir")
            done
        done
        IFS=$'\n' SUBJECT_DIRS=($(printf "%s\n" "${SUBJECT_DIRS[@]}" | sort -uV))
    fi

    if [ ${#SUBJECT_DIRS[@]} -eq 0 ]; then
        echo -e "\nNo subject directories found." | tee -a "$LOG_FILE"
        exit 1
    fi

    echo -e "Found ${#SUBJECT_DIRS[@]} subject directories.\n" | tee -a "$LOG_FILE"

    # --------------------------------------------------------------------------
    # Main loop: Subjects -> Sessions -> BET extraction
    # --------------------------------------------------------------------------
    for SUBJ_DIR in "${SUBJECT_DIRS[@]}"; do
        SUBJ_ID="$(basename "$SUBJ_DIR")"
        echo "=== Processing Subject: $SUBJ_ID ===" | tee -a "$LOG_FILE"

        # Collect session directories
        SESSION_DIRS=()
        if [ ${#SESSIONS[@]} -gt 0 ]; then
            # If specific sessions were requested
            for ses in "${SESSIONS[@]}"; do
                SES_DIR="$SUBJ_DIR/$ses"
                if [ -d "$SES_DIR" ]; then
                    SESSION_DIRS+=("$SES_DIR")
                else
                    echo -e "Warning: Session directory not found:\n  - $SES_DIR" | tee -a "$LOG_FILE"
                fi
            done
        else
            # Otherwise find all ses-* directories
            for ses_dir in "$SUBJ_DIR"/ses-*; do
                [ -d "$ses_dir" ] && SESSION_DIRS+=("$ses_dir")
            done
            IFS=$'\n' SESSION_DIRS=($(printf "%s\n" "${SESSION_DIRS[@]}" | sort -V))
        fi

        if [ ${#SESSION_DIRS[@]} -eq 0 ]; then
            # allow processing subjects without sessions
            SESSION_DIRS=("$SUBJ_DIR")
        fi

        # Process each session
        for SES_DIR in "${SESSION_DIRS[@]}"; do
            if [ "$SES_DIR" = "$SUBJ_DIR" ]; then
                SES_ID=""
                echo "--- No session ---" | tee -a "$LOG_FILE"
                ANAT_DIR="$SES_DIR/anat"
            else
                SES_ID="$(basename "$SES_DIR")"
                echo "--- Session: $SES_ID ---" | tee -a "$LOG_FILE"
                ANAT_DIR="$SES_DIR/anat"
            fi
            if [ ! -d "$ANAT_DIR" ]; then
                echo -e "Anatomical directory not found:\n  - $ANAT_DIR\n" | tee -a "$LOG_FILE"
                continue
            fi

            if [ -z "$SES_ID" ]; then
                T1W_FILE="$ANAT_DIR/${SUBJ_ID}_T1w.nii.gz"
            else
                T1W_FILE="$ANAT_DIR/${SUBJ_ID}_${SES_ID}_T1w.nii.gz"
            fi
            if [ ! -f "$T1W_FILE" ]; then
                echo -e "\nT1w image not found:\n  - $T1W_FILE\n" | tee -a "$LOG_FILE"
                continue
            fi

            echo "T1w Image: $T1W_FILE" | tee -a "$LOG_FILE"

            # ------------------------------------------------------------------
            # Construct the final output path (skip reorient if needed)
            # ------------------------------------------------------------------
            if [ -z "$SES_ID" ]; then
                DERIV_ANAT_DIR="$BASE_DIR/derivatives/fsl/$SUBJ_ID/anat"
            else
                DERIV_ANAT_DIR="$BASE_DIR/derivatives/fsl/$SUBJ_ID/$SES_ID/anat"
            fi
            mkdir -p "$DERIV_ANAT_DIR"

            # Create suffixes for file naming
            BET_SUFFIX=""
            if [ -n "$BET_OPTION" ]; then
                # e.g., -R => "R"
                BET_SUFFIX="${BET_OPTION:1}"
            fi
            FRAC_INT_SUFFIX="f$(echo $FRAC_INTENSITY | sed 's/\.//')"

            if [ -z "$SES_ID" ]; then
                OUTPUT_FILE="$DERIV_ANAT_DIR/${SUBJ_ID}_desc-${BET_SUFFIX}${FRAC_INT_SUFFIX}_T1w_brain.nii.gz"
                REORIENTED_T1W_FILE="${ANAT_DIR}/${SUBJ_ID}_desc-reoriented_T1w.nii.gz"
            else
                OUTPUT_FILE="$DERIV_ANAT_DIR/${SUBJ_ID}_${SES_ID}_desc-${BET_SUFFIX}${FRAC_INT_SUFFIX}_T1w_brain.nii.gz"
                REORIENTED_T1W_FILE="${ANAT_DIR}/${SUBJ_ID}_${SES_ID}_desc-reoriented_T1w.nii.gz"
            fi

            STEP=1

            # ------------------------------------------------------------------
            # [Step] Reorient if requested AND if the final BET file is missing
            # ------------------------------------------------------------------
            if [ "$REORIENT" == "yes" ]; then
                if [ -f "$OUTPUT_FILE" ]; then
                    echo "Skull-stripped T1w image already exists: $OUTPUT_FILE" | tee -a "$LOG_FILE"
                    echo "Skipping reorientation (since final output is already present)." | tee -a "$LOG_FILE"
                    echo ""
                else
                    echo ""
                    echo "[Step $STEP] Applying fslreorient2std:" | tee -a "$LOG_FILE"
                    echo "  - Input: $T1W_FILE" | tee -a "$LOG_FILE"
                    echo "  - Output (Reoriented): $REORIENTED_T1W_FILE" | tee -a "$LOG_FILE"
                    
                    fslreorient2std "$T1W_FILE" "$REORIENTED_T1W_FILE"
                    if [ $? -ne 0 ]; then
                        echo -e "Error applying fslreorient2std for $SUBJ_ID $SES_ID\n" | tee -a "$LOG_FILE"
                        continue
                    fi
                    T1W_FILE="$REORIENTED_T1W_FILE"
                    STEP=$((STEP+1))
                    echo ""
                fi
            fi

            # ------------------------------------------------------------------
            # [Step] Run BET Brain Extraction (only if OUTPUT_FILE is missing)
            # ------------------------------------------------------------------
            echo "[Step $STEP] Running BET Brain Extraction:" | tee -a "$LOG_FILE"
            echo "  - Input: $T1W_FILE" | tee -a "$LOG_FILE"
            echo "  - Command: bet \"$T1W_FILE\" \"$OUTPUT_FILE\" $BET_OPTION -f \"$FRAC_INTENSITY\"" | tee -a "$LOG_FILE"

            # Optionally copy the T1w into derivatives
            if [ ! -f "$DERIV_ANAT_DIR/$(basename "$T1W_FILE")" ]; then
                cp "$T1W_FILE" "$DERIV_ANAT_DIR/"
            fi

            # Check if the final BET output already exists
            if [ -f "$OUTPUT_FILE" ]; then
                echo -e "\nSkull-stripped T1w image already exists:\n  - $OUTPUT_FILE\n" | tee -a "$LOG_FILE"
            else
                bet "$T1W_FILE" "$OUTPUT_FILE" $BET_OPTION -f "$FRAC_INTENSITY"
                if [ $? -ne 0 ]; then
                    echo -e "Error during BET skull stripping for $SUBJ_ID $SES_ID\n" | tee -a "$LOG_FILE"
                    continue
                fi

                STEP=$((STEP+1))
                echo "" | tee -a "$LOG_FILE"
                echo "[Step $STEP] Cleaning Up Temporary Files:" | tee -a "$LOG_FILE"

                # If reorientation, remove the reoriented file from derivatives
                if [ "$REORIENT" == "yes" ]; then
                    # Decide which file to remove from derivatives:
                    #   - Copied T1W_FILE to derivatives (the reoriented one).
                    #   - That file might be named `_desc-reoriented_T1w.nii.gz`.
                    # Just remove it to avoid clutter.
                    FILE_TO_REMOVE="$DERIV_ANAT_DIR/$(basename "$T1W_FILE")"
                    echo "  - Removed: $FILE_TO_REMOVE" | tee -a "$LOG_FILE"
                    rm "$FILE_TO_REMOVE"
                else
                    # If not reoriented, remove the original T1 that was copied
                    if [ -z "$SES_ID" ]; then
                        FILE_TO_REMOVE="$DERIV_ANAT_DIR/${SUBJ_ID}_T1w.nii.gz"
                    else
                        FILE_TO_REMOVE="$DERIV_ANAT_DIR/${SUBJ_ID}_${SES_ID}_T1w.nii.gz"
                    fi
                    if [ -f "$FILE_TO_REMOVE" ]; then
                        echo "  - Removed: $FILE_TO_REMOVE" | tee -a "$LOG_FILE"
                        rm "$FILE_TO_REMOVE"
                    fi
                fi

                echo "" | tee -a "$LOG_FILE"
                echo "BET Brain Extraction completed at:" | tee -a "$LOG_FILE"
                echo "  - Output: $OUTPUT_FILE" | tee -a "$LOG_FILE"
                echo "" | tee -a "$LOG_FILE"
            fi

        done  # end session loop
    done      # end subject loop

    echo -e "\nBET skull stripping completed."
    echo "------------------------------------------------------------------------------"

} 2>&1 | tee -a "$LOG_FILE"
