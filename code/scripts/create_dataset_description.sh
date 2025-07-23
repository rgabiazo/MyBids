#!/bin/bash

###############################################################################
# create_dataset_description.sh
#
# Purpose:
#   Create or update a BIDS dataset_description.json within a derivatives
#   directory. Existing files are left untouched so repeated runs are safe.
#
# Usage:
#   create_dataset_description.sh --analysis-dir DIR [options]
#
# Usage Examples:
#   create_dataset_description.sh --analysis-dir derivatives/fsl/level-1 \
#       --ds-name "My Derivative" --dataset-type derivative
#
# Options:
#   --analysis-dir DIR           Output directory for dataset_description.json
#   --ds-name STRING             BIDS "Name" field
#   --dataset-type STRING        BIDS "DatasetType" field
#   --description STRING         Free‑text description
#   --bids-version STRING        BIDS version string
#   --generatedby "Name=...,Version=...,Description=..."  May be repeated
#   --help, -h                   Show help
#
# Requirements:
#   bash
#
# Notes:
#   Handles commas in the --generatedby description field by parsing Name,
#   Version and Description separately. Existing dataset_description.json will
#   not be overwritten.

###############################################################################

usage() {
  cat <<EOM
Usage: $(basename "$0") --analysis-dir <dir> [--ds-name <str>] [--dataset-type <str>]
                        [--description <str>] [--bids-version <str>]
                        [--generatedby "Name=...,Version=...,Description=..."] [...]
                        [--help]

Creates or updates a BIDS dataset_description.json in the specified directory,
skipping if a dataset_description.json is already present.

Required arguments:
  --analysis-dir <dir>        : Directory for dataset_description.json

Optional arguments:
  --ds-name <str>             : The "Name" field (default "Unnamed_Derivative")
  --dataset-type <str>        : The "DatasetType" (default "derivative")
  --description <str>         : The "Description" field (default "No description provided.")
  --bids-version <str>        : The BIDSVersion (default "No version provided")
  --generatedby <key=val,...> : Zero or more times; each describes a "GeneratedBy" entry
                                (Name=...,Version=...,Description=...)
  --help, -h                  : Show this help and exit
EOM
  exit 1
}

###############################################################################
# Default values
###############################################################################
ANALYSIS_DIR=""
DS_NAME="Unnamed_Derivative"
DATASET_TYPE="derivative"
DESCRIPTION="No description provided."
BIDS_VERSION="No version provided"

declare -a GENERATED_BY_ITEMS=()

###############################################################################
# Parse command-line arguments
###############################################################################
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    --help|-h)
      usage
      ;;
    --analysis-dir)
      ANALYSIS_DIR="$2"
      shift; shift
      ;;
    --ds-name)
      DS_NAME="$2"
      shift; shift
      ;;
    --dataset-type)
      DATASET_TYPE="$2"
      shift; shift
      ;;
    --description)
      DESCRIPTION="$2"
      shift; shift
      ;;
    --bids-version)
      BIDS_VERSION="$2"
      shift; shift
      ;;
    --generatedby)
      GENERATED_BY_ITEMS+=("$2")
      shift; shift
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      ;;
  esac
done

###############################################################################
# Validate that --analysis-dir was provided
###############################################################################
if [ -z "$ANALYSIS_DIR" ]; then
  echo "Error: --analysis-dir <dir> is required."
  usage
fi

###############################################################################
# Create the target directory if needed
###############################################################################
mkdir -p "$ANALYSIS_DIR"
JSON_FILE="${ANALYSIS_DIR}/dataset_description.json"

###############################################################################
# If dataset_description.json already exists, skip
###############################################################################
if [ -f "$JSON_FILE" ]; then
  exit 0
fi

###############################################################################
# Build the JSON in a temp file, then move it
###############################################################################
TMPFILE=$(mktemp)

# Start the JSON
cat <<EOF > "$TMPFILE"
{
  "Name": "${DS_NAME}",
  "DatasetType": "${DATASET_TYPE}",
  "BIDSVersion": "${BIDS_VERSION}",
  "Description": "${DESCRIPTION}",
  "GeneratedBy": [
EOF

###############################################################################
# Helper function to parse a "generatedby" string
# Expects the string to have the pattern:
#   Name=...,Version=...,Description=...
# The "Description" field can include commas; everything after "Description=" is captured.
###############################################################################
parse_generatedby() {
  local entry="$1"

  # Extract Name (stops at the next comma, which is fine for Name=FSL)
  local name
  name="$(echo "$entry" | sed -nE 's/.*Name=([^,]+).*/\1/p')"

  # Extract Version (again stops at next comma)
  local version
  version="$(echo "$entry" | sed -nE 's/.*Version=([^,]+).*/\1/p')"

  # Extract EVERYTHING after "Description=" (including commas)
  local description
  description="$(echo "$entry" | sed -nE 's/.*Description=(.*)/\1/p')"

  # Escape quotes inside the strings
  name="${name//\"/\\\"}"
  version="${version//\"/\\\"}"
  description="${description//\"/\\\"}"

  # Output them in a single line, separated by |
  echo "$name|$version|$description"
}

###############################################################################
# Populate "GeneratedBy" array
###############################################################################
COUNT=${#GENERATED_BY_ITEMS[@]}
if [ "$COUNT" -gt 0 ]; then
  for ((i=0; i<COUNT; i++)); do
    entry="${GENERATED_BY_ITEMS[$i]}"
    parsed="$(parse_generatedby "$entry")"
    IFS='|' read -r p_name p_version p_desc <<< "$parsed"

    printf '    {\n' >> "$TMPFILE"

    # Build a small array of lines to print
    lines=()
    if [ -n "$p_name" ]; then
      lines+=("      \"Name\": \"$p_name\"")
    fi
    if [ -n "$p_version" ]; then
      lines+=("      \"Version\": \"$p_version\"")
    fi
    if [ -n "$p_desc" ]; then
      lines+=("      \"Description\": \"$p_desc\"")
    fi

    # Print them, comma-separated
    for ((j=0; j<${#lines[@]}; j++)); do
      if [ $((j+1)) -lt ${#lines[@]} ]; then
        printf '%s,\n' "${lines[$j]}" >> "$TMPFILE"
      else
        printf '%s\n' "${lines[$j]}" >> "$TMPFILE"
      fi
    done

    if [ $((i+1)) -lt $COUNT ]; then
      printf '    },\n' >> "$TMPFILE"
    else
      printf '    }\n' >> "$TMPFILE"
    fi
  done
fi

# Finish the JSON
cat <<EOF >> "$TMPFILE"
  ]
}
EOF

mv "$TMPFILE" "$JSON_FILE"
exit 0
