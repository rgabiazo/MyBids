#!/usr/bin/env bash
###############################################################################
# create_spherical_rois.sh
#
# Purpose:
#   Generate a spherical ROI mask around a specified voxel in MNI space.
#   Typically called by higher-level scripts after coordinates are chosen.
#
# Usage:
#   create_spherical_rois.sh --region NAME --mni X,Y,Z --vox "X Y Z" \
#                            --cope COPE --radius MM --outdir DIR
#
# Usage Examples:
#   create_spherical_rois.sh --region "Hippocampus" --mni "30,-20,-20" \
#                            --vox "45 65 35" --cope "cope01" --radius 5mm \
#                            --outdir /project/fsl
#
# Options:
#   --region NAME         ROI region label
#   --mni X,Y,Z           MNI coordinate
#   --vox "X Y Z"         Voxel coordinate in reference image
#   --cope COPE           Cope label/name
#   --radius MM           Sphere radius in mm
#   --outdir DIR          Output directory base
#
# Requirements:
#   FSL installed (fslmaths) and FEAT_DIR environment variable set
#
# Notes:
#   ROI masks are written to <outdir>/roi/<COPE_LABEL> with abbreviated region
#   names via an internal lookup table.
#
###############################################################################

set -e

##############################################################################
# Check for required environment variable
##############################################################################
: "${FEAT_DIR:?Error: FEAT_DIR environment variable not set. Please export FEAT_DIR=/path/to/copeX.feat}"

##############################################################################
# Logging Setup
##############################################################################
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

##############################################################################
# Parse Arguments
##############################################################################
while [[ $# -gt 0 ]]; do
  case "$1" in
    --region)
      REGION="$2"
      shift 2
      ;;
    --mni)
      MNI_COORD="$2"
      shift 2
      ;;
    --vox)
      VOX_COORD="$2"
      shift 2
      ;;
    --cope)
      COPE_LABEL="$2"
      shift 2
      ;;
    --radius)
      RADIUS="$2"
      shift 2
      ;;
    --outdir)
      OUTDIR_BASE="$2"
      shift 2
      ;;
    *)
      log_error "Unknown argument: $1"
      exit 1
      ;;
  esac
done

# Ensure required arguments are present
if [ -z "$REGION" ] || [ -z "$MNI_COORD" ] || [ -z "$VOX_COORD" ] || [ -z "$COPE_LABEL" ] || [ -z "$OUTDIR_BASE" ]; then
  log_error "Missing required arguments."
  echo "Usage: create_spherical_rois.sh --region <RegionName> --mni <x,y,z> --vox <x y z> --cope <COPE##> --radius <mm> --outdir <basepath>"
  exit 1
fi

##############################################################################
# Region Abbreviation Logic
##############################################################################
declare -A ABBREV
ABBREV["Frontal Pole"]="FrontalPole"
ABBREV["Insular Cortex"]="Insula"
ABBREV["Superior Frontal Gyrus"]="SFG"
ABBREV["Middle Frontal Gyrus"]="MFG"
ABBREV["Inferior Frontal Gyrus, pars triangularis"]="IFGtriang"
ABBREV["Inferior Frontal Gyrus, pars opercularis"]="IFGoperc"
ABBREV["Precentral Gyrus"]="Precentral"
ABBREV["Temporal Pole"]="TemporalPole"
ABBREV["Superior Temporal Gyrus, anterior division"]="STGanterior"
ABBREV["Superior Temporal Gyrus, posterior division"]="STGposterior"
ABBREV["Middle Temporal Gyrus, anterior division"]="MTGanterior"
ABBREV["Middle Temporal Gyrus, posterior division"]="MTGposterior"
ABBREV["Middle Temporal Gyrus, temporooccipital part"]="MTGtemporooccipital"
ABBREV["Inferior Temporal Gyrus, anterior division"]="ITGanterior"
ABBREV["Inferior Temporal Gyrus, posterior division"]="ITGposterior"
ABBREV["Inferior Temporal Gyrus, temporooccipital part"]="ITGtemporooccipital"
ABBREV["Postcentral Gyrus"]="Postcentral"
ABBREV["Superior Parietal Lobule"]="SPL"
ABBREV["Supramarginal Gyrus, anterior division"]="SMGanterior"
ABBREV["Supramarginal Gyrus, posterior division"]="SMGposterior"
ABBREV["Angular Gyrus"]="Angular"
ABBREV["Lateral Occipital Cortex, superior division"]="LOcsuperior"
ABBREV["Lateral Occipital Cortex, inferior division"]="LOcinferior"
ABBREV["Intracalcarine Cortex"]="Intracalcarine"
ABBREV["Frontal Medial Cortex"]="FrontalMedial"
ABBREV["Juxtapositional Lobule Cortex (formerly Supplementary Motor Cortex)"]="Juxtapositional"
ABBREV["Subcallosal Cortex"]="Subcallosal"
ABBREV["Paracingulate Gyrus"]="Paracingulate"
ABBREV["Cingulate Gyrus, anterior division"]="CingulateAnterior"
ABBREV["Cingulate Gyrus, posterior division"]="CingulatePosterior"
ABBREV["Precuneous Cortex"]="Precuneous"
ABBREV["Cuneal Cortex"]="Cuneal"
ABBREV["Frontal Orbital Cortex"]="FrontalOrbital"
ABBREV["Parahippocampal Gyrus, anterior division"]="PHGanterior"
ABBREV["Parahippocampal Gyrus, posterior division"]="PHGposterior"
ABBREV["Lingual Gyrus"]="Lingual"
ABBREV["Temporal Fusiform Cortex, anterior division"]="TFCanterior"
ABBREV["Temporal Fusiform Cortex, posterior division"]="TFCposterior"
ABBREV["Temporal Occipital Fusiform Cortex"]="TOFusiform"
ABBREV["Occipital Fusiform Gyrus"]="OccFusiform"
ABBREV["Frontal Operculum Cortex"]="FrontalOperculum"
ABBREV["Central Operculum Cortex"]="CentralOperculum"
ABBREV["Parietal Operculum Cortex"]="ParietalOperculum"
ABBREV["Planum Polare"]="PlanumPolare"
ABBREV["Heschl’s Gyrus (includes H1 and H2)"]="Heschl"
ABBREV["Planum Temporale"]="PlanumTemporale"
ABBREV["Supracalcarine Cortex"]="Supracalcarine"
ABBREV["Occipital Pole"]="OccipitalPole"

REGION_CLEAN="$(echo "$REGION" | sed 's/([^)]*)//g' | sed 's/[ \t]*$//')"
REGION_ABBREV="${ABBREV[$REGION_CLEAN]}"
if [ -z "$REGION_ABBREV" ]; then
  # Fallback: replace spaces with underscores, remove commas
  REGION_ABBREV="$(echo "$REGION_CLEAN" | tr ' ' '_' | tr -d ',')"
fi

##############################################################################
# Prepare Output Folder
##############################################################################
OUTDIR="${OUTDIR_BASE}/roi/${COPE_LABEL}"
mkdir -p "$OUTDIR"

##############################################################################
# Derive File Paths
##############################################################################
read -r vx vy vz <<< "$VOX_COORD"

# Filenames keep the exact "mm" portion for clarity, e.g. "sphere5mm_mask"
centerfile="${REGION_ABBREV}_space-MNI152_desc-center_mask.nii.gz"
spherefile="${REGION_ABBREV}_space-MNI152_desc-sphere${RADIUS}mm_mask.nii.gz"
binfile="${REGION_ABBREV}_space-MNI152_desc-sphere${RADIUS}mm_binarized_mask.nii.gz"

mask1vox="${OUTDIR}/${centerfile}"
sphere_vox="${OUTDIR}/${spherefile}"
sphere_bin="${OUTDIR}/${binfile}"

##############################################################################
# Print Header
##############################################################################

# Cleanly parse MNI_COORD to parentheses with spacing
formatted_mni="$(echo "$MNI_COORD" | sed 's/,\s*/,\ /g' | sed 's/^/(/;s/$/)/')"
# Similarly parse VOX_COORD to parentheses with spacing
formatted_vox="$(echo "$VOX_COORD" | sed 's/\s\+/, /g' | sed 's/^/(/;s/$/)/')"

echo ""
echo "================================================================================="
printf "                Generating Spherical ROI: %s\n" "$REGION_CLEAN"
echo "================================================================================="
printf "MNI Coordinate:            %-25s\n" "$formatted_mni"
printf "Voxel Coordinate:          %-25s\n" "$formatted_vox"
printf "COPE Label:                %s\n" "$COPE_LABEL"
printf "Output Directory:          roi/%s\n" "$COPE_LABEL"
echo ""

##############################################################################
# Check if final binarized ROI already exists
##############################################################################
if [ -f "$sphere_bin" ]; then
  #
  # If the final ROI already exists, skip creation but maintain the new style output
  #
  echo "--- ROI Already Exists ---"
  echo "The final mask file already exists at:"
  echo "  $sphere_bin"
  echo
  echo "--- Completion Summary ---"
  printf "Region:                    %s\n" "$REGION_CLEAN"
  printf "Final Mask File:           %s\n" "$(basename "$sphere_bin")"
  printf "Output Directory:          %s\n" "$OUTDIR"
  echo ""
  log_info "Skipping existing ROI: $sphere_bin"
  exit 0
fi

##############################################################################
# STEP 1: Create Single-Voxel Mask
##############################################################################
echo "--- Step 1: Create Single-Voxel Mask ---"
echo "Command:"
cat <<EOF
  fslmaths \$FSLDIR/data/standard/MNI152_T1_2mm_brain.nii.gz \\
    -mul 0 -add 1 \\
    -roi $vx 1 $vy 1 $vz 1 0 1 \\
    ${mask1vox} \\
    -odt float
EOF
echo "Output:"
echo "  $(basename "$mask1vox")"
echo ""

fslmaths "$FSLDIR/data/standard/MNI152_T1_2mm_brain.nii.gz" \
  -mul 0 -add 1 \
  -roi "$vx" 1 "$vy" 1 "$vz" 1 0 1 \
  "$mask1vox" \
  -odt float

##############################################################################
# STEP 2: Grow Spherical ROI
##############################################################################
echo "--- Step 2: Grow Spherical ROI (Radius: $RADIUS) ---"
echo "Command:"

# Stripping "mm" from the numeric part for the actual kernel radius (e.g., "5mm" -> "5"):
kernel_radius="${RADIUS//mm/}"
[ -z "$kernel_radius" ] && kernel_radius=5  # default if empty

cat <<EOF
  fslmaths ${mask1vox} \\
    -kernel sphere $kernel_radius -fmean \\
    ${sphere_vox} \\
    -odt float
EOF

echo "Output:"
echo "  $(basename "$sphere_vox")"
echo ""

fslmaths "$mask1vox" -kernel sphere "$kernel_radius" -fmean "$sphere_vox" -odt float

##############################################################################
# STEP 3: Binarize the Spherical Mask
##############################################################################
echo "--- Step 3: Binarize the Spherical Mask ---"
echo "Command:"
cat <<EOF
  fslmaths ${sphere_vox} \\
    -bin \\
    ${sphere_bin}
EOF

echo "Output:"
echo "  $(basename "$sphere_bin")"
echo ""

fslmaths "$sphere_vox" -bin "$sphere_bin"

##############################################################################
# Final Summary
##############################################################################
echo "--- Completion Summary ---"
printf "Region:                    %s\n" "$REGION_CLEAN"
printf "Final Mask File:           %s\n" "$(basename "$sphere_bin")"
printf "Output Directory:          %s\n" "$OUTDIR"
log_info "Created ROI for region '$REGION_CLEAN' at: $sphere_bin" >> $LOG_FILE
