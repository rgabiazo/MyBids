#!/usr/bin/env bash
###############################################################################
# create_tsv.sh
#
# Purpose:
#   Create or overwrite a tab-separated values file using the provided column
#   names and row data.
#
# Usage:
#   create_tsv.sh <TSV_PATH> <NUM_COLUMNS> <COLUMN1> [COLUMN2 ...] [ROW1 ...]
#
# Usage Examples:
#   create_tsv.sh participants.tsv 1 participant_id sub-01 sub-02 sub-03
#   create_tsv.sh sessions.tsv 2 participant_id session_id \
#       "sub-01  ses-01" \
#       "sub-01  ses-02" \
#       "sub-02  ses-01"
#
# Options:
#   None
#
# Requirements:
#   bash
#
# Notes:
#   Rows are passed as space-separated strings corresponding to the columns.
#
###############################################################################

# Prints usage information
usage() {
  echo "Usage: $(basename "$0") <TSV_PATH> <NUM_COLUMNS> <COLUMN1> [COLUMN2 ... COLUMNn] [ROW1] [ROW2] ..."
  echo ""
  echo "Example (1 column):"
  echo "  $(basename "$0") participants.tsv 1 participant_id sub-01 sub-02 sub-03"
  echo ""
  echo "Example (2 columns):"
  echo "  $(basename "$0") sessions.tsv 2 participant_id session_id \\"
  echo "      \"sub-01  ses-01\" \\"
  echo "      \"sub-01  ses-02\" \\"
  echo "      \"sub-02  ses-01\""
  echo ""
}

# If fewer than 3 arguments are provided, show usage and exit
if [ $# -lt 3 ]; then
  usage
  exit 1
fi

TSV_FILE="$1"
shift
NUM_COLS="$1"
shift

# If not enough arguments remain for the columns themselves, show usage
if [ $# -lt "$NUM_COLS" ]; then
  echo "Error: Not enough column names specified."
  usage
  exit 1
fi

# Gather the column names in an array
COL_NAMES=()
for (( i=1; i<=NUM_COLS; i++ )); do
  COL_NAMES+=( "$1" )
  shift
done

# The rest of the arguments are the individual row strings
ROWS=("$@")

# Overwrite the TSV file
{
  # Print the header line (columns separated by tabs)
  IFS=$'\t'
  echo "${COL_NAMES[*]}"

  # Print each row. For multi-column rows, separate columns by space or tab
  for row in "${ROWS[@]}"; do
    echo -e "$row"
  done
} > "$TSV_FILE"

echo "Created/updated TSV at: $TSV_FILE"
