#!/usr/bin/env bash
###############################################################################
# generate_cluster_tables.sh
#
# Purpose:
#   Parse group-level FEAT results to create cluster tables, perform atlas
#   lookups and guide spherical ROI creation.
#
# Usage:
#   generate_cluster_tables.sh (expects FEAT_DIR, COPE_NAME and OUTDIR_BASE env vars)
#
# Usage Examples:
#   export FEAT_DIR=/path/to/cope1.feat
#   export COPE_NAME=cope1
#   export OUTDIR_BASE=/path/to/derivatives
#   ./generate_cluster_tables.sh
#
# Options:
#   None (uses environment variables)
#
# Requirements:
#   FSL with atlasq, std2imgcoord and fslmaths
#
# Notes:
#   Generates summary tables and calls create_spherical_rois.sh to make ROI masks.
#   Outputs & Interactions:
#     - Displays a cluster summary table (Z-MAX, Z-COG, COPE-MAX, local maxima).
#     - Labels probable cortical/subcortical areas by querying the Harvard-Oxford atlas (atlasq).
#     - Assigns ROI IDs for each coordinate; select which IDs to turn into spherical ROIs.
#     - When ROI(s) are selected, the script calls create_spherical_rois.sh, passing each selected coordinate,
#       region label, and sphere radius.
#   - The script logs progress to code/logs/<script>_<timestamp>.log.
#   - Can press ENTER at the ROI selection prompt to select all ROI IDs.
#   - Can press ENTER at the radius prompt to default to 5 mm.
#   **Harvard-Oxford Atlas**:
#     - Queries 'harvardoxford-cortical' for cortical regions.
#     - Queries 'harvardoxford-subcortical' for subcortical structures.
#     - Uses a MIN_PROB threshold (default 5%) to filter out lower-probability overlapping labels.
#   In a pipeline where `select_group_roi.sh` already sets environment variables and calls this script:
#        ./select_group_roi.sh
#      (No manual environment variable export is needed in this example, as the script sets them.)
#
###############################################################################
set -e

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
# Check required environment variables
##############################################################################
: "${FEAT_DIR:?Error: FEAT_DIR environment variable not set.}"
: "${COPE_NAME:?Error: COPE_NAME environment variable not set.}"
: "${STANDARD_TEMPLATE:="$FSLDIR/data/standard/MNI152_T1_2mm_brain.nii.gz"}"
: "${OUTDIR_BASE:?Error: OUTDIR_BASE environment variable not set.}"

##############################################################################
# Configuration
##############################################################################
MIN_PROB=5  # Minimum probability (%) for partial-volume atlas results

CLUSTER_FILE="${FEAT_DIR}/cluster_zstat1_std.txt"
LMAX_FILE="${FEAT_DIR}/lmax_zstat1_std.txt"

if [ ! -f "$CLUSTER_FILE" ]; then
  log_error "Missing $CLUSTER_FILE"
  exit 1
fi
if [ ! -f "$LMAX_FILE" ]; then
  log_error "Missing $LMAX_FILE"
  exit 1
fi

if ! command -v std2imgcoord >/dev/null 2>&1; then
  log_debug "std2imgcoord not found in PATH."
fi
if ! command -v atlasq >/dev/null 2>&1; then
  log_debug "atlasq not found in PATH. Make sure FSL is configured."
fi

##############################################################################
# Data structures
##############################################################################
declare -A cluster_voxels
declare -A cluster_pval
declare -A cluster_log10p
declare -A cluster_zmax

declare -A cluster_zmaxx
declare -A cluster_zmaxy
declare -A cluster_zmaxz

declare -A cluster_zcogx
declare -A cluster_zcogy
declare -A cluster_zcogz

declare -A cluster_copemaxx
declare -A cluster_copemaxy
declare -A cluster_copemaxz

declare -A localmax_list

declare -A roi_voxcoords
declare -A roi_cortical_list
declare -A roi_subcortical_list
declare -A roi_cortical_max
declare -A roi_subcortical_max

cluster_ordered_coords=()
declare -A unique_coords

##############################################################################
# Functions for coordinate transforms & atlas lookups
##############################################################################
mni_to_vox() {
  local x="$1"
  local y="$2"
  local z="$3"

  # If std2imgcoord or the standard template isn't present, just return input
  if ! command -v std2imgcoord &>/dev/null || [ ! -f "$STANDARD_TEMPLATE" ]; then
    echo "$x $y $z"
    return
  fi

  local result
  result=$(echo "$x $y $z 1" | std2imgcoord -img "$STANDARD_TEMPLATE" -std "$STANDARD_TEMPLATE" -vox 2>/dev/null)
  if [ -n "$result" ]; then
    set -- $result
    echo "$1 $2 $3"
  else
    echo "$x $y $z"
  fi
}

parse_atlasq_output() {
  local input="$1"
  local output=""
  local found_data=false

  while IFS= read -r line; do
    # skip empty lines or lines with headings/proportions
    if [[ -z "$line" ]] || [[ "$line" =~ ^-+ ]] || [[ "$line" =~ [Cc]oordinate|[Nn]ame|[Ii]ndex|[Ss]ummary[[:space:]]value|[Pp]roportion ]]; then
      continue
    fi

    if [[ "$line" =~ \| ]]; then
      IFS='|' read -ra columns <<< "$line"
      if [[ "${#columns[@]}" -eq 4 ]]; then
        local region proportion
        region="$(echo "${columns[0]}" | xargs)"
        proportion="$(echo "${columns[3]}" | xargs)"

        if ! [[ "$proportion" =~ ^[0-9.]+$ ]]; then
          continue
        fi
        local prop_int
        printf -v prop_int "%.0f" "$proportion"
        local line_out="${prop_int}% ${region}"
        if [ -z "$output" ]; then
          output="$line_out"
        else
          output="${output};${line_out}"
        fi
        found_data=true
      fi
    fi
  done < <(echo "$input")

  $found_data || echo ""
  $found_data && echo "$output"
}

atlas_lookup_all() {
  local x="$1"
  local y="$2"
  local z="$3"

  local cortical="None"
  local subcortical="None"

  if command -v atlasq &>/dev/null; then
    local c_report s_report
    c_report="$(atlasq query harvardoxford-cortical -c "$x" "$y" "$z" 2>/dev/null)"
    s_report="$(atlasq query harvardoxford-subcortical -c "$x" "$y" "$z" 2>/dev/null)"

    local c_parsed s_parsed
    c_parsed="$(parse_atlasq_output "$c_report")"
    s_parsed="$(parse_atlasq_output "$s_report")"

    [ -z "$c_parsed" ] && c_parsed="None"
    [ -z "$s_parsed" ] && s_parsed="None"

    cortical="$c_parsed"
    subcortical="$s_parsed"
  fi

  echo "${cortical}|${subcortical}"
}

cleanup_atlas_output() {
  local raw_str="$1"
  IFS=';' read -ra chunks <<< "$raw_str"
  local cleaned=()

  for c in "${chunks[@]}"; do
    c="$(echo "$c" | sed 's/^[ \t]*//;s/[ \t]*$//')"
    [ -z "$c" ] && continue
    c="$(echo "$c" | sed 's/<[^>]*>//g')"  # remove any HTML
    if [[ "$c" =~ "No label found!" ]]; then
      continue
    fi

    local line_remaining="$c"
    local line_out=""

    while [[ "$line_remaining" =~ ([0-9]+)%[[:space:]]*(.*) ]]; do
      local prob="${BASH_REMATCH[1]}"
      local region="${BASH_REMATCH[2]}"
      line_remaining="${line_remaining#*${BASH_REMATCH[0]}}"

      (( prob < MIN_PROB )) && continue

      local formatted="${region} (${prob}%)"
      if [ -z "$line_out" ]; then
        line_out="$formatted"
      else
        line_out="${line_out}, $formatted"
      fi
    done

    [ -z "$line_out" ] || cleaned+=( "$line_out" )
  done

  if [ "${#cleaned[@]}" -eq 0 ]; then
    echo "None"
  else
    local joined="${cleaned[0]}"
    for ((i=1; i<${#cleaned[@]}; i++)); do
      joined="${joined};${cleaned[i]}"
    done
    echo "$joined"
  fi
}

parse_atlas_lines() {
  local region_string="$1"
  [ "$region_string" = "None" ] && echo "None" && return

  IFS=';' read -ra lines <<< "$region_string"
  for l in "${lines[@]}"; do
    l="$(echo "$l" | sed 's/^[ \t]*//;s/[ \t]*$//')"
    echo "$l"
  done
}

find_highest_probability_cortical() {
  local region_string="$1"
  [ "$region_string" = "None" ] && echo "None" && return

  local best_prob=-999
  local best_region="None"

  IFS=';' read -ra lines <<< "$region_string"
  for l in "${lines[@]}"; do
    if [[ "$l" =~ \(([0-9]+)\%\) ]]; then
      local prob="${BASH_REMATCH[1]}"
      (( prob > best_prob )) && {
        best_prob=$prob
        best_region="$l"
      }
    fi
  done

  echo "$best_region"
}

find_highest_probability_subcortical() {
  local region_string="$1"
  [ "$region_string" = "None" ] && echo "None" && return

  local best_prob=-999
  local best_region="None"

  IFS=';' read -ra lines <<< "$region_string"
  for l in "${lines[@]}"; do
    if [[ "$l" =~ \(([0-9]+)\%\) ]]; then
      local prob="${BASH_REMATCH[1]}"
      (( prob > best_prob )) && {
        best_prob=$prob
        best_region="$l"
      }
    fi
  done

  echo "$best_region"
}

wrap_line_by_comma() {
  local line="$1"
  [ "$line" = "None" ] && echo "None" && return

  IFS=',' read -ra parts <<< "$line"
  for (( i=0; i<${#parts[@]}; i++ )); do
    local p="${parts[$i]}"
    [ $i -lt $(( ${#parts[@]} - 1 )) ] && p="${p},"
    echo "$(echo "$p" | xargs)"
  done
}

wrap_multiple_lines() {
  local multiline="$1"
  [ "$multiline" = "None" ] && echo "None" && return

  local out=()
  while IFS= read -r struct_line; do
    while IFS= read -r splitted; do
      out+=( "$splitted" )
    done < <(wrap_line_by_comma "$struct_line")
  done < <(echo "$multiline")

  for line in "${out[@]}"; do
    echo "$line"
  done
}

add_coord_if_not_exists() {
  local x="$1"
  local y="$2"
  local z="$3"
  local -n arrRef="$4"

  [ -z "$x" ] && return
  [ -z "$y" ] && return
  [ -z "$z" ] && return

  local key="${x},${y},${z}"

  if [ -z "${unique_coords[$key]}" ]; then
    unique_coords["$key"]="1"
    arrRef+=( "$key" )
  fi
}

##############################################################################
# Parse cluster_zstat1_std.txt
##############################################################################
while IFS= read -r line; do
  [[ -z "$line" || "$line" =~ [Cc]luster\ [Ii]ndex ]] && continue
  arr=($line)
  [ "${#arr[@]}" -lt 16 ] && continue

  clust_idx="${arr[0]}"
  cluster_voxels[$clust_idx]="${arr[1]}"
  cluster_pval[$clust_idx]="${arr[2]}"
  cluster_log10p[$clust_idx]="${arr[3]}"
  cluster_zmax[$clust_idx]="${arr[4]}"

  cluster_zmaxx[$clust_idx]="${arr[5]}"
  cluster_zmaxy[$clust_idx]="${arr[6]}"
  cluster_zmaxz[$clust_idx]="${arr[7]}"

  cluster_zcogx[$clust_idx]="${arr[8]}"
  cluster_zcogy[$clust_idx]="${arr[9]}"
  cluster_zcogz[$clust_idx]="${arr[10]}"

  cluster_copemaxx[$clust_idx]="${arr[12]}"
  cluster_copemaxy[$clust_idx]="${arr[13]}"
  cluster_copemaxz[$clust_idx]="${arr[14]}"
done < "$CLUSTER_FILE"

##############################################################################
# Parse lmax_zstat1_std.txt
##############################################################################
while IFS= read -r line; do
  [[ -z "$line" || "$line" =~ [Cc]luster\ [Ii]ndex ]] && continue
  arr=($line)
  [ "${#arr[@]}" -lt 5 ] && continue

  clust_idx="${arr[0]}"
  peak_z="${arr[1]}"
  xcoord="${arr[2]}"
  ycoord="${arr[3]}"
  zcoord="${arr[4]}"

  new_entry="${peak_z},${xcoord},${ycoord},${zcoord}"
  if [ -z "${localmax_list[$clust_idx]}" ]; then
    localmax_list[$clust_idx]="$new_entry"
  else
    localmax_list[$clust_idx]+=";$new_entry"
  fi
done < "$LMAX_FILE"

##############################################################################
# Build sorted list of clusters
##############################################################################
clusters_sorted=( $(echo "${!cluster_voxels[@]}" | tr ' ' '\n' | sort -n) )

##############################################################################
# Print main cluster list
##############################################################################
echo ""
printf "                                 %s - CLUSTER LIST\n" "$COPE_NAME"
echo "========================================================================================================"
fmt_clusters_header="| %4s | %6s | %8s | %8s | %5s | %15s | %20s | %15s \n"
fmt_clusters_line="--------------------------------------------------------------------------------------------------------"

printf "$fmt_clusters_header" "Clus" "Voxels" "p" "-log10p" "Z-MAX" "Z-MAX Coord" "Z-COG Coord" "COPE-MAX Coord"
echo "$fmt_clusters_line"

for clust_idx in "${clusters_sorted[@]}"; do
  v="${cluster_voxels[$clust_idx]}"
  p_="${cluster_pval[$clust_idx]}"
  logp_="${cluster_log10p[$clust_idx]}"
  z_="${cluster_zmax[$clust_idx]}"

  zx="${cluster_zmaxx[$clust_idx]}"
  zy="${cluster_zmaxy[$clust_idx]}"
  zz="${cluster_zmaxz[$clust_idx]}"

  cx="${cluster_zcogx[$clust_idx]}"
  cy="${cluster_zcogy[$clust_idx]}"
  cz="${cluster_zcogz[$clust_idx]}"

  cpx="${cluster_copemaxx[$clust_idx]}"
  cpy="${cluster_copemaxy[$clust_idx]}"
  cpz="${cluster_copemaxz[$clust_idx]}"

  zmax_str="($zx,$zy,$zz)"
  zcog_str="($cx,$cy,$cz)"
  copem_str="($cpx,$cpy,$cpz)"

  printf "$fmt_clusters_header" \
         "$clust_idx" \
         "$v" \
         "$p_" \
         "$logp_" \
         "$z_" \
         "$zmax_str" \
         "$zcog_str" \
         "$copem_str"

  echo "$fmt_clusters_line"
done

##############################################################################
# Print local maxima + atlas lookups
##############################################################################
echo ""
echo "=================================================================================================================================="
printf "                          %s - LOCAL MAXIMA\n" "$COPE_NAME"
echo "=================================================================================================================================="

local_line="----------------------------------------------------------------------------------------------------------------------------------"
printf "| %7s | %10s | %-18s | %-50s | %-50s\n" \
       "Clus" "Z" "( x,   y,   z )" "Cortical Regions" "Subcortical Regions"
echo "$local_line"

for clust_idx in "${clusters_sorted[@]}"; do
  allmax="${localmax_list[$clust_idx]}"
  [ -z "$allmax" ] && continue

  IFS=';' read -ra max_array <<< "$allmax"
  for entry in "${max_array[@]}"; do
    IFS=',' read -ra fields <<< "$entry"
    zval="${fields[0]}"
    mx="${fields[1]}"
    my="${fields[2]}"
    mz="${fields[3]}"

    raw_atl="$(atlas_lookup_all "$mx" "$my" "$mz")"
    c_part="${raw_atl%%|*}"
    s_part="${raw_atl#*|}"

    c_part="$(cleanup_atlas_output "$c_part")"
    s_part="$(cleanup_atlas_output "$s_part")"

    c_part="$(parse_atlas_lines "$c_part")"
    s_part="$(parse_atlas_lines "$s_part")"

    mapfile -t c_wrapped < <(wrap_multiple_lines "$c_part")
    mapfile -t s_wrapped < <(wrap_multiple_lines "$s_part")

    maxlen=${#c_wrapped[@]}
    [ ${#s_wrapped[@]} -gt "$maxlen" ] && maxlen=${#s_wrapped[@]}

    for (( i=0; i<maxlen; i++ )); do
      c_line="${c_wrapped[$i]}"
      s_line="${s_wrapped[$i]}"
      [ -z "$c_line" ] && c_line=""
      [ -z "$s_line" ] && s_line=""

      if [ $i -eq 0 ]; then
        printf "| %7s | %10s | (%4s,%4s,%4s )  | %-50s | %-50s\n" \
               "$clust_idx" \
               "$zval" \
               "$mx" \
               "$my" \
               "$mz" \
               "$c_line" \
               "$s_line"
      else
        printf "| %7s | %10s | %-18s | %-50s | %-50s\n" \
               "" \
               "" \
               "" \
               "$c_line" \
               "$s_line"
      fi
    done
    echo "$local_line"
  done
done

##############################################################################
# Gather all unique coords (Z-MAX, Z-COG, COPE-MAX, local maxima)
##############################################################################
for clust_idx in "${clusters_sorted[@]}"; do
  add_coord_if_not_exists "${cluster_zmaxx[$clust_idx]}" "${cluster_zmaxy[$clust_idx]}" "${cluster_zmaxz[$clust_idx]}" cluster_ordered_coords
  add_coord_if_not_exists "${cluster_zcogx[$clust_idx]}" "${cluster_zcogy[$clust_idx]}" "${cluster_zcogz[$clust_idx]}" cluster_ordered_coords
  add_coord_if_not_exists "${cluster_copemaxx[$clust_idx]}" "${cluster_copemaxy[$clust_idx]}" "${cluster_copemaxz[$clust_idx]}" cluster_ordered_coords

  allmax="${localmax_list[$clust_idx]}"
  if [ -n "$allmax" ]; then
    IFS=';' read -ra max_array <<< "$allmax"
    for entry in "${max_array[@]}"; do
      IFS=',' read -ra fields <<< "$entry"
      add_coord_if_not_exists "${fields[1]}" "${fields[2]}" "${fields[3]}" cluster_ordered_coords
    done
  fi
done

##############################################################################
# Convert each unique MNI coord to voxel coords, run atlas lookups
##############################################################################
for coord in "${cluster_ordered_coords[@]}"; do
  IFS=',' read -r x y z <<< "$coord"
  local_v="$(mni_to_vox "$x" "$y" "$z")"

  raw_atl="$(atlas_lookup_all "$x" "$y" "$z")"
  c_part="${raw_atl%%|*}"
  s_part="${raw_atl#*|}"

  c_part="$(cleanup_atlas_output "$c_part")"
  s_part="$(cleanup_atlas_output "$s_part")"

  c_list="$(parse_atlas_lines "$c_part")"
  s_list="$(parse_atlas_lines "$s_part")"

  best_cort="$(find_highest_probability_cortical "$c_part")"
  best_subcort="$(find_highest_probability_subcortical "$s_part")"

  roi_voxcoords[$coord]="$local_v"
  roi_cortical_list[$coord]="$c_list"
  roi_subcortical_list[$coord]="$s_list"
  roi_cortical_max[$coord]="$best_cort"
  roi_subcortical_max[$coord]="$best_subcort"
done

##############################################################################
# Print "ROI Coordinates Table"
##############################################################################
echo ""
echo "====================================================================================================================================================================================================================================================="
printf "                %s - CLUSTER LIST & LOCAL MAXIMA ATLAS PROBABILITY \n" "$COPE_NAME"
echo "====================================================================================================================================================================================================================================================="

fmt_rois_header=" %-8s | %25s | %-23s | %-50s | %-50s | %-35s | %-35s\n"
fmt_rois_line="-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------"

printf "$fmt_rois_header" \
       "ROI List" \
       "( x,   y,   z )" \
       "Voxel Location" \
       "Cortical Regions" \
       "Subcortical Regions" \
       "Cortical (Highest Probability %)" \
       "Subcortical (Highest Probability %)"
echo "$fmt_rois_line"

roi_index=1
declare -A final_coord_for_id
declare -A final_region_for_id
declare -A final_vox_for_id

for coord in "${cluster_ordered_coords[@]}"; do
  IFS=',' read -r x y z <<< "$coord"
  local_v="${roi_voxcoords[$coord]}"

  c_lines="${roi_cortical_list[$coord]}"
  s_lines="${roi_subcortical_list[$coord]}"
  best_cort="${roi_cortical_max[$coord]}"
  best_subcort="${roi_subcortical_max[$coord]}"

  mapfile -t c_wrapped < <(wrap_multiple_lines "$c_lines")
  mapfile -t s_wrapped < <(wrap_multiple_lines "$s_lines")
  mapfile -t best_c_wrapped < <(wrap_line_by_comma "$best_cort")
  mapfile -t best_s_wrapped < <(wrap_line_by_comma "$best_subcort")

  c_first="${c_wrapped[0]}"
  s_first="${s_wrapped[0]}"
  bc_first="${best_c_wrapped[0]}"
  bs_first="${best_s_wrapped[0]}"

  [ "$c_first" = "None" ] && c_first=""
  [ "$s_first" = "None" ] && s_first=""
  [ "$bc_first" = "None" ] && bc_first=""
  [ "$bs_first" = "None" ] && bs_first=""

  printf "$fmt_rois_header" \
         "${roi_index}." \
         "$(printf "(%.2f, %.2f, %.2f)" "$x" "$y" "$z")" \
         "($local_v)" \
         "$c_first" \
         "$s_first" \
         "$bc_first" \
         "$bs_first"

  final_coord_for_id[$roi_index]="$coord"
  final_region_for_id[$roi_index]="$best_cort"
  final_vox_for_id[$roi_index]="$local_v"

  max_len=${#c_wrapped[@]}
  [ ${#s_wrapped[@]} -gt "$max_len" ] && max_len=${#s_wrapped[@]}
  [ ${#best_c_wrapped[@]} -gt "$max_len" ] && max_len=${#best_c_wrapped[@]}
  [ ${#best_s_wrapped[@]} -gt "$max_len" ] && max_len=${#best_s_wrapped[@]}

  for (( i=1; i<max_len; i++ )); do
    c_line="${c_wrapped[$i]}"
    s_line="${s_wrapped[$i]}"
    bc_line="${best_c_wrapped[$i]}"
    bs_line="${best_s_wrapped[$i]}"

    [ "$c_line" = "None" ] && c_line=""
    [ "$s_line" = "None" ] && s_line=""
    [ "$bc_line" = "None" ] && bc_line=""
    [ "$bs_line" = "None" ] && bs_line=""

    printf "$fmt_rois_header" \
           "" \
           "" \
           "" \
           "$c_line" \
           "$s_line" \
           "$bc_line" \
           "$bs_line"
  done

  echo "$fmt_rois_line"
  ((roi_index++))
done

##############################################################################
# Summarize best coordinates per region
##############################################################################
echo ""
printf "                === %s - ROIs SELECTION ===\n" "$COPE_NAME"

declare -A best_region_for_coord
declare -A best_prob_for_coord

for coord in "${cluster_ordered_coords[@]}"; do
  c_lines="${roi_cortical_list[$coord]}"
  coord_best_prob=-999
  coord_best_region=""

  while IFS= read -r line; do
    line="$(echo "$line" | xargs)"
    [ -z "$line" ] || [ "$line" = "None" ] && continue
    if [[ "$line" =~ ^(.*)\(([0-9]+)\%\)$ ]]; then
      rname="${BASH_REMATCH[1]}"
      rprob="${BASH_REMATCH[2]}"
      rname="$(echo "$rname" | xargs)"
      if (( rprob > coord_best_prob )); then
        coord_best_prob=$rprob
        coord_best_region="$rname"
      fi
    fi
  done < <(printf "%s\n" "$c_lines")

  if [ -n "$coord_best_region" ]; then
    best_region_for_coord[$coord]="$coord_best_region"
    best_prob_for_coord[$coord]="$coord_best_prob"
  fi
done

declare -A region_best_prob
declare -A region_best_coord
declare -A region_best_vox

for coord in "${cluster_ordered_coords[@]}"; do
  region="${best_region_for_coord[$coord]}"
  prob="${best_prob_for_coord[$coord]}"
  [ -n "$region" ] || continue

  old_prob="${region_best_prob[$region]:-0}"
  if (( prob > old_prob )); then
    region_best_prob[$region]="$prob"
    region_best_coord[$region]="$coord"
    region_best_vox[$region]="${roi_voxcoords[$coord]}"
  fi
done

fmt_summary_header=" %-8s | %25s | %-23s | %-50s\n"
fmt_summary_line="----------------------------------------------------------------------------------------------------------------"

echo "$fmt_summary_line"
printf "$fmt_summary_header" \
       "ROI ID" \
       "( x,   y,   z )" \
       "Voxel Location" \
       "Cortical ROI (Highest Probability %)"
echo "$fmt_summary_line"

summary_index=1
declare -A summary_coord
declare -A summary_region
declare -A summary_vox

for coord in "${cluster_ordered_coords[@]}"; do
  region="${best_region_for_coord[$coord]}"
  prob="${best_prob_for_coord[$coord]}"
  [ -z "$region" ] && continue

  best_coord_for_region="${region_best_coord[$region]}"
  if [ "$best_coord_for_region" = "$coord" ]; then
    vox="${region_best_vox[$region]}"
    IFS=',' read -r x y z <<< "$coord"
    region_display="$(printf "%s (%s%%)" "$region" "$prob")"

    printf "$fmt_summary_header" \
           "${summary_index}." \
           "$(printf "(%.2f, %.2f, %.2f)" "$x" "$y" "$z")" \
           "($vox)" \
           "$region_display"
    echo "$fmt_summary_line"

    summary_coord[$summary_index]="$coord"
    summary_region[$summary_index]="$region"
    summary_vox[$summary_index]="$vox"

    ((summary_index++))
  fi
done

log_info "Done generating tables for $COPE_NAME."

##############################################################################
# Prompt for ROI ID selection (minimal re-prints)
##############################################################################
if [ $summary_index -eq 1 ]; then
  echo ""
  log_info "No ROIs found for $COPE_NAME.gfeat"
  exit 0
fi

echo ""
echo "Enter ROI ID(s) to use for spherical ROI (e.g. 1 2 3), or press ENTER/RETURN for all:"

while true; do
  # Show just the prompt arrow
  echo -n "> "
  read -r sel_ids

  if [ -z "$sel_ids" ]; then
    # User pressed ENTER -> select ALL
    sel_ids=$(seq 1 $((summary_index-1)))
    id_array=($(seq 1 $((summary_index-1))))
    echo "ROI ID(s) selected: ${id_array[*]}"
    break
  fi

  IFS=' ' read -ra id_array <<< "$sel_ids"
  valid=true

  for sid in "${id_array[@]}"; do
    # Must be integer
    if ! [[ "$sid" =~ ^[0-9]+$ ]]; then
      echo "Invalid ROI ID. Please enter ROI ID(s) separated by spaces or press ENTER/RETURN for all."
      valid=false
      break
    fi
    # Must be in range
    if [ "$sid" -lt 1 ] || [ "$sid" -ge "$summary_index" ]; then
      echo "ROI ID $sid out of range (1..$((summary_index-1))). Please enter available ROI ID(s) or press ENTER/RETURN for all."
      valid=false
      break
    fi
  done

  if $valid; then
    echo "ROI ID(s) selected: ${id_array[*]}"
    break
  fi
done

echo ""

##############################################################################
# Prompt for radius (minimal re-prints)
##############################################################################
echo "Enter Radius, or press ENTER/RETURN to use default 5mm:"

while true; do
  echo -n "> "
  read -r user_radius

  if [ -z "$user_radius" ]; then
    user_radius=5
    echo "Radius: ${user_radius}mm"
    break
  fi

  if [[ "$user_radius" =~ ^[0-9]+$ ]]; then
    echo "Radius: ${user_radius}mm"
    break
  else
    echo "Please enter a valid radius integer."
  fi
done

echo ""

##############################################################################
# Call create_spherical_rois.sh for each selected ROI
##############################################################################
for sid in "${id_array[@]}"; do
  coord="${summary_coord[$sid]}"
  region="${summary_region[$sid]}"
  vox="${summary_vox[$sid]}"
  if [ -z "$coord" ] || [ -z "$region" ] || [ -z "$vox" ]; then
    log_debug "ROI ID $sid not valid; skipping."
    continue
  fi

  "$SCRIPT_DIR/create_spherical_rois.sh" \
    --region "$region" \
    --mni "$coord" \
    --vox "$vox" \
    --cope "$COPE_NAME" \
    --radius "$user_radius" \
    --outdir "$OUTDIR_BASE"
done
