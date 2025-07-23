#!/usr/bin/env bash
###############################################################################
# select_group_roi.sh
#
# Purpose:
#   Helper script to choose group-level FEAT directories and create spherical ROIs.
#
# Usage:
#   select_group_roi.sh
#
# Usage Examples:
#   ./select_group_roi.sh
#
# Options:
#   None (interactive)
#
# Requirements:
#   FSL environment variables set
#
# Notes:
#   Logs actions to code/logs and calls generate_cluster_tables.sh and create_spherical_rois.sh.
#
################################################################################
set -e

###############################################################################
# Step 0: Setup Logging, etc.
###############################################################################
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOP_LEVEL="$(dirname "$(dirname "$SCRIPT_DIR")")"

LOG_DIR="$TOP_LEVEL/code/logs"
mkdir -p "$LOG_DIR"

SCRIPT_BASENAME="$(basename "${BASH_SOURCE[0]}")"
CURRENT_DATETIME="$(date '+%Y%m%d_%H%M%S')"
LOG_FILE="${LOG_DIR}/${SCRIPT_BASENAME}_${CURRENT_DATETIME}.log"
touch "$LOG_FILE"

log_debug() {
  echo "[DEBUG] $*" >> "$LOG_FILE"
}
log_info() {
  echo "$*"
  echo "[INFO] $*" >> "$LOG_FILE"
}
log_error() {
  echo "$*" >&2
  echo "[ERROR] $*" >> "$LOG_FILE"
}

log_debug "SCRIPT_DIR: $SCRIPT_DIR"
log_debug "TOP_LEVEL:  $TOP_LEVEL"
log_debug "LOG_FILE:   $LOG_FILE"

LEVEL3_DIR="$TOP_LEVEL/derivatives/fsl/level-3"
if [ ! -d "$LEVEL3_DIR" ]; then
  log_error "Cannot find: $LEVEL3_DIR"
  exit 1
fi

###############################################################################
# Step 1: Collect and display possible group-analysis directories
###############################################################################
echo -e "\n=== Spherical ROI Group Analysis Directory Selection ===\n"

log_debug "LEVEL3_DIR: $LEVEL3_DIR"

possible_dirs=()
shopt -s nullglob
for d in "$LEVEL3_DIR"/*desc*group*; do
  if [ -d "$d" ]; then
    possible_dirs+=("$d")
  fi
done
shopt -u nullglob

if [ ${#possible_dirs[@]} -eq 0 ]; then
  log_error "No directories found in $LEVEL3_DIR that match '*desc*group*'"
  exit 1
fi

echo "Available Group Analysis Directories:"
echo ""
i=1
for p in "${possible_dirs[@]}"; do
  printf "%d) %s\n" "$i" "$(basename "$p")"
  ((i++))
done
echo ""

echo "Please select the group analysis directory for spherical ROI creation by entering the number:"
group_choice=-1

while true; do
  # Show just the prompt arrow
  echo -n "> "
  read -r choice

  # Validate
  if [[ "$choice" =~ ^[0-9]+$ ]]; then
    idx="$choice"
    if [ "$idx" -ge 1 ] && [ "$idx" -le "${#possible_dirs[@]}" ]; then
      group_choice=$idx
      break
    else
      echo "Please enter a number in the range 1..${#possible_dirs[@]}."
    fi
  else
    echo "Please enter a single integer (no commas/spaces)."
  fi
done

SELECTED_GROUP_DIR="${possible_dirs[$((group_choice-1))]}"

###############################################################################
# Step 2: Collect and display possible .gfeat directories
###############################################################################
echo ""
echo "=== .gfeat Selection ==="
echo "Directory: $(basename "$SELECTED_GROUP_DIR")"
echo ""

shopt -s nullglob
possible_gfeats=( $(ls -d "$SELECTED_GROUP_DIR"/cope*.gfeat 2>/dev/null | sort -V) )
shopt -u nullglob

if [ ${#possible_gfeats[@]} -eq 0 ]; then
  log_error "No .gfeat directories found in $SELECTED_GROUP_DIR"
  exit 1
fi

echo "Available .gfeat directories:"
echo ""
i=1
for gf in "${possible_gfeats[@]}"; do
  printf "%2d)  %s\n" "$i" "$(basename "$gf")"
  ((i++))
done
echo ""

echo "Please select a .gfeat directory by entering the number:"
gfeat_choice=-1

while true; do
  # Show just the prompt arrow
  echo -n "> "
  read -r choice

  # Validate
  if [[ "$choice" =~ ^[0-9]+$ ]]; then
    idx="$choice"
    if [ "$idx" -ge 1 ] && [ "$idx" -le "${#possible_gfeats[@]}" ]; then
      gfeat_choice=$idx
      break
    else
      echo "Please enter a number in the range 1..${#possible_gfeats[@]}."
    fi
  else
    echo "Please enter a single integer (no commas/spaces)."
  fi
done

SELECTED_GFEAT="${possible_gfeats[$((gfeat_choice-1))]}"
SELECTED_GFEAT_BASENAME="$(basename "$SELECTED_GFEAT")"

# Clean up any trailing \r or whitespace
STRIPPED_NAME="$(echo "$SELECTED_GFEAT_BASENAME" | tr -d '\r' | xargs)"
log_debug "STRIPPED_NAME='$STRIPPED_NAME' (length ${#STRIPPED_NAME})"

PARSED_BEFORE_GFEAT="${STRIPPED_NAME%.gfeat}"
if [ "$PARSED_BEFORE_GFEAT" = "$STRIPPED_NAME" ]; then
  log_debug "No .gfeat suffix found, defaulting to COPE??"
  COPE_NAME="COPE??"
else
  COPE_NAME="$PARSED_BEFORE_GFEAT"
fi

###############################################################################
# Step 3: Setup FEAT_DIR & OUTDIR_BASE, export, call next script
###############################################################################
FEAT_DIR="${SELECTED_GFEAT}/cope1.feat"
OUTDIR_BASE="$SELECTED_GROUP_DIR"

if [ ! -d "$FEAT_DIR" ]; then
  log_error "Could not find $FEAT_DIR"
  exit 1
fi

export FEAT_DIR
export COPE_NAME
export OUTDIR_BASE

echo "" >> "$LOG_FILE"
echo "---------------------------------------------------------------"  >> "$LOG_FILE"
echo "Selected Group Folder: $SELECTED_GROUP_DIR"  >> "$LOG_FILE"
echo "Selected .gfeat:        $SELECTED_GFEAT_BASENAME"  >> "$LOG_FILE"
echo "---------------------------------------------------------------" >> "$LOG_FILE"
echo ""  >> "$LOG_FILE"

SCRIPT_TO_RUN="$SCRIPT_DIR/generate_cluster_tables.sh"
if [ ! -f "$SCRIPT_TO_RUN" ]; then
  log_error "Cannot find $SCRIPT_TO_RUN. Make sure it exists in $SCRIPT_DIR"
  exit 1
fi

bash "$SCRIPT_TO_RUN"

###############################################################################
# Step 4: Prompt to create additional ROIs (Minimal re-print)
###############################################################################
echo ""
echo "Would you like to select another group & cope for spherical ROI creation? (y/n)"

while true; do
  # Show just the prompt arrow
  echo -n "> "
  read -r answer

  case "$answer" in
    [Yy]* )
      clear            # Clears the terminal output
      exec "$0"        # Re-run this script from the top
      ;;
    [Nn]* )
      exit 0
      ;;
    * )
      echo "Please answer y or n."
      ;;
  esac
done
