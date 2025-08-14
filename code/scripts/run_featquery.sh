#!/usr/bin/env bash
###############################################################################
# run_featquery.sh
#
# Purpose:
#   Run FSL featquery on given FEAT directories and ROI masks and collect
#   CSV outputs in a structured derivatives folder.
#
# Usage:
#   run_featquery.sh FEAT_DIRS... :: ROI_MASKS...
#
# Usage Examples:
#   run_featquery.sh dir1.feat dir2.feat :: roi1.nii.gz roi2.nii.gz
#
# Options:
#   None (positional arguments before and after ::)
#
# Requirements:
#   FSL featquery
#
# Notes:
#   Writes logs to code/logs and organizes outputs under derivatives/fsl/featquery.
#
###############################################################################

script_dir="$(cd "$(dirname "$0")" && pwd)"

BASE_DIR="$(dirname "$(dirname "$script_dir")")"
LOG_DIR="$BASE_DIR/code/logs"
mkdir -p "$LOG_DIR"
LOGFILE="$LOG_DIR/run_featquery_$(date +'%Y%m%d_%H%M%S').log"
exec > >(tee -a "$LOGFILE") 2>&1

echo
echo "=== Initializing run_featquery.sh ===" >> "$LOGFILE"
echo "Log file: $LOGFILE" >> "$LOGFILE"
echo >> "$LOGFILE"

###############################################################################
# 1) Locate 'featquery' in PATH
###############################################################################
FEATQ="$(command -v featquery)"
if [ -z "$FEATQ" ]; then
    echo "[ERROR] Could not find 'featquery' in PATH. Please ensure FSL is loaded."
    exit 1
fi

echo "featquery found at: $FEATQ" >> "$LOGFILE"
echo >> "$LOGFILE"

###############################################################################
# 2) Separate FEAT_DIRS (before "::") from ROI_MASKS (after "::")
###############################################################################
FEAT_DIRS=()
ROI_MASKS=()

while [ $# -gt 0 ]; do
    if [ "$1" = "::" ]; then
        shift
        break
    fi
    FEAT_DIRS+=( "$1" )
    shift
done

while [ $# -gt 0 ]; do
    ROI_MASKS+=( "$1" )
    shift
done

###############################################################################
# 3) Print a short summary
###############################################################################
echo "=== Featquery input directories and ROI mask(s) ==="
echo
echo "FEAT directories (${#FEAT_DIRS[@]}):"
for fdir in "${FEAT_DIRS[@]}"; do
    echo "  $fdir"
done
echo
echo "ROI masks (${#ROI_MASKS[@]}):"
for rmask in "${ROI_MASKS[@]}"; do
    echo "  $rmask"
done
echo "----------------------------------------------------"
echo

###############################################################################
# 4) Quick checks
###############################################################################
if [ ${#FEAT_DIRS[@]} -eq 0 ]; then
    echo "[WARNING] No FEAT directories were passed. Exiting..."
    exit 1
fi
if [ ${#ROI_MASKS[@]} -eq 0 ]; then
    echo "[WARNING] No ROI masks were passed. Exiting..."
    exit 1
fi

###############################################################################
# 5) Helpers
###############################################################################
function log_only() {
    echo "$@" >> "$LOGFILE"
}

# Extract group name from ROI path if it includes "level-3/<GROUP>/roi"
function get_group_name_from_roi() {
    local roi_path="$1"
    if [[ "$roi_path" =~ (level-3/([^/]+)/roi/) ]]; then
        echo "${BASH_REMATCH[2]}"
    else
        echo "group-level_featquery"
    fi
}

# CHANGED: No longer need an "analysis_name" in the final path
# so skip that function or just ignore it.

###############################################################################
# For each ROI mask, run featquery, parse the outputs, and save TSVs
###############################################################################

CSV_DATA_DIR="$BASE_DIR/derivatives/fsl/featquery/data"
mkdir -p "$CSV_DATA_DIR"

for mask_path in "${ROI_MASKS[@]}"; do

    GROUP_NAME="$(get_group_name_from_roi "$mask_path")"
    roi_parent="$(dirname "$mask_path")"
    cope_name="$(basename "$roi_parent")"        # e.g. "cope10"
    roi_file="$(basename "$mask_path")"          # e.g. "ROI-Intracalcarine_space-MNI152_desc-sphere5mm.nii.gz"
    roi_noext="${roi_file%.nii*}"               # strip .nii or .nii.gz

    # Strip any trailing "_binarized_mask" from the name if present
    roi_noext="$(echo "$roi_noext" | sed -E 's/(_binarized_mask)?$//I')"

    # Turn "cope10" into "cope-10"
    #  (just remove the word "cope" and prepend "cope-")
    cope_num="${cope_name#cope}"                 # e.g. "10"
    cope_label="cope-${cope_num}"                # e.g. "cope-10"

    # Turn "ROI-Intracalcarine_space-MNI152_desc-sphere5mm" into "roi-intracalcarine"
    #   1) Remove leading "ROI-"
    #   2) Cut off everything at the first underscore (e.g. "_space-...")
    #   3) Prepend "roi-"
    #   4) Lowercase it
    roi_cleaned="$(
      echo "$roi_noext" \
      | sed -E 's/^ROI-//I; s/_.*//;' \
      | sed 's/^/roi-/; y/ABCDEFGHIJKLMNOPQRSTUVWXYZ/abcdefghijklmnopqrstuvwxyz/'
    )"

    # This label is what featquery uses inside the .feat folder, e.g. "cope10_ROI-..."
    # Still need it for the ephemeral subfolder name:
    label="${cope_name}_ROI-${roi_noext}_featquery"

    # Keep track of subject/session outputs in an associative array
    declare -A PERROI_SESSIONS_DATA=()

    # Identify which FEAT dirs still need featquery (skip if already present)
    MISSING_FEAT_DIRS=()
    for fdir in "${FEAT_DIRS[@]}"; do
        localdir="${fdir%/}"

        dir_cope=""
        if [[ "$localdir" =~ \.gfeat$ ]]; then
            dir_cope="$cope_name"
            localdir="$localdir/${cope_name}.feat"
        elif [[ "$localdir" =~ (cope[0-9]+)\.feat$ ]]; then
            dir_cope="${BASH_REMATCH[1]}"
        fi

        if [ -n "$dir_cope" ] && [ "$dir_cope" != "$cope_name" ]; then
            continue
        fi

        subject="$(echo "$localdir" | sed -nE 's@.*(sub-[^_/]+).*@\1@p')"
        [ -z "$subject" ] && subject="sub-unknown"

        session_name="$(echo "$localdir" | sed -nE 's@.*(ses-[^_/]+).*@\1@p')"
        [ -z "$session_name" ] && session_name="ses-unknown"

        if [ "$session_name" = "ses-unknown" ]; then
            final_out_dir="$BASE_DIR/derivatives/fsl/featquery/$GROUP_NAME/$subject/$label"
        else
            final_out_dir="$BASE_DIR/derivatives/fsl/featquery/$GROUP_NAME/$subject/$session_name/$label"
        fi

        if [ ! -d "$final_out_dir" ]; then
            MISSING_FEAT_DIRS+=( "$localdir" )
        fi
    done

    # If none are missing, skip re-running featquery
    if [ ${#MISSING_FEAT_DIRS[@]} -eq 0 ]; then
        echo "[INFO] All FEAT directories already have outputs for $label in $GROUP_NAME"
        echo
    else
        # Remove any old partial subfolder
        for fdir in "${MISSING_FEAT_DIRS[@]}"; do
            old_subfolder="$fdir/$label"
            [ -d "$old_subfolder" ] && rm -rf "$old_subfolder"
        done

        # Build and run featquery command
        num_missing=${#MISSING_FEAT_DIRS[@]}
        CMD=( "$FEATQ" "$num_missing" )
        for missing_dir in "${MISSING_FEAT_DIRS[@]}"; do
            CMD+=( "$missing_dir" )
        done
        CMD+=( "1" "stats/pe1" "$label" "-p" "-s" "-b" "$mask_path" )

        echo ">>> ${CMD[@]}"
        "${CMD[@]}"

        # Move ephemeral outputs + parse "report.txt"
        for fdir in "${MISSING_FEAT_DIRS[@]}"; do
            subject="$(echo "$fdir" | sed -nE 's@.*(sub-[^_/]+).*@\1@p')"
            [ -z "$subject" ] && subject="sub-unknown"

            session_name="$(echo "$fdir" | sed -nE 's@.*(ses-[^_/]+).*@\1@p')"
            [ -z "$session_name" ] && session_name="ses-unknown"

            source_dir="$fdir/$label"
            if [ "$session_name" = "ses-unknown" ]; then
                final_out_dir="$BASE_DIR/derivatives/fsl/featquery/$GROUP_NAME/$subject/$label"
            else
                final_out_dir="$BASE_DIR/derivatives/fsl/featquery/$GROUP_NAME/$subject/$session_name/$label"
            fi
            mkdir -p "$(dirname "$final_out_dir")"

            if [ -d "$source_dir" ]; then
                mv "$source_dir" "$final_out_dir"
            else
                echo "[WARNING] No featquery folder found at $source_dir"
                continue
            fi

            report_file="$final_out_dir/report.txt"
            if [ ! -f "$report_file" ]; then
                echo "[WARNING] No report.txt in $final_out_dir"
                continue
            fi

            # Parse 'Mean' from the first line of report.txt
            mapfile -t lines < "$report_file"
            if [ ${#lines[@]} -gt 0 ]; then
                fields=(${lines[0]})
                mean_val="${fields[5]:-0.0}"
            else
                mean_val="NaN"
            fi

            # Use an associative array storing lines by session
            # Write them to a TSV after handling all subjects
            if [ -z "${PERROI_SESSIONS_DATA[$session_name]+exists}" ]; then
                # Header row in tab-delimited format:
                PERROI_SESSIONS_DATA["$session_name"]=$'participant_id\tmean_intensity'
            fi
            # Append new row, again with real tab
            PERROI_SESSIONS_DATA["$session_name"]+=$'\n'"$subject"$'\t'"$mean_val"
        done
    fi

    # ----------------------------------------------------------------------
    # One TSV per session, using the format:
    #   <featquery>/data/<GROUP_NAME>/cope-10_roi-intracalcarine_ses-01.tsv
    # ----------------------------------------------------------------------
    for s in "${!PERROI_SESSIONS_DATA[@]}"; do

        # Final output directory for these TSVs
        final_data_dir="$CSV_DATA_DIR/$GROUP_NAME"
        mkdir -p "$final_data_dir"

        # Construct the filename, e.g.: cope-10_roi-intracalcarine_ses-01.tsv
        if [ "$s" = "ses-unknown" ]; then
            tsv_name="${cope_label}_${roi_cleaned}.tsv"
        else
            tsv_name="${cope_label}_${roi_cleaned}_${s}.tsv"
        fi
        tsv_path="$final_data_dir/$tsv_name"

        printf "%s\n" "${PERROI_SESSIONS_DATA["$s"]}" > "$tsv_path"
        echo "TSV created at: $tsv_path"
    done

done

echo
echo "Featquery Complete."
echo "========================================"
echo "=== Finished run_featquery.sh ==="
