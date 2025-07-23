#!/usr/bin/env bash
set -euo pipefail

show_help() {
    cat <<'USAGE'
Usage: $(basename "$0") --name NAME [OPTIONS]

Initialise a BIDS dataset by renaming its root folder, creating a
virtual environment and generating dataset_description.json.

Options:
  --name NAME          Dataset name (required)
  --author NAME        Author name (may be repeated)
  --dataset-type TYPE  BIDS dataset type (raw|derivative)
  --license TEXT       License identifier for dataset_description.json
  --acknowledgements TEXT  Acknowledgements text
  --how-to-acknowledge TEXT  How users should cite the dataset
  --funding TEXT       Funding source (may be repeated)
  --ethics-approval TEXT  Ethics approval identifier (may be repeated)
  --reference TEXT     Related reference or link (may be repeated)
  --dataset-doi TEXT   DOI for the dataset
  --path DIR           Path to existing dataset root (default: current dir)
  --force              Overwrite existing dataset_description.json
  -h, --help           Show this help and exit
USAGE
}

# Defaults
root_dir=$(pwd)
name=""
dataset_type="raw"
force_flag=""
authors=()
license=""
acknowledgements=""
how_to_ack=""
fundings=()
ethics=()
references=()
dataset_doi=""

# Option parsing
while [[ $# -gt 0 ]]; do
    case "$1" in
        --name|--Name)
            name="$2"; shift 2;;
        --author|--Author)
            authors+=("$2"); shift 2;;
        --dataset-type)
            dataset_type="$2"; shift 2;;
        --license)
            license="$2"; shift 2;;
        --acknowledgements)
            acknowledgements="$2"; shift 2;;
        --how-to-acknowledge)
            how_to_ack="$2"; shift 2;;
        --funding)
            fundings+=("$2"); shift 2;;
        --ethics-approval)
            ethics+=("$2"); shift 2;;
        --reference)
            references+=("$2"); shift 2;;
        --dataset-doi)
            dataset_doi="$2"; shift 2;;
        --path)
            root_dir="$2"; shift 2;;
        --force)
            force_flag="--force"; shift;;
        -h|--help)
            show_help; exit 0;;
        *)
            echo "Unknown option: $1" >&2
            show_help
            exit 1;;
    esac
done

if [[ -z "$name" ]]; then
    echo "[ERROR] --name is required" >&2
    exit 1
fi

# Resolve root directory
root_dir=$(cd "$root_dir" && pwd)

# Choose python interpreter
python_cmd=$(command -v python3 || command -v python || true)
if [[ -z "$python_cmd" ]]; then
    echo "[ERROR] python3 or python is required" >&2
    exit 1
fi

# Inline slugification logic mirroring bidscomatic.utils.naming.slugify,
# but kept self-contained so the script works even when the package is
# not yet installed.
slug=$("$python_cmd" - "$name" <<'PY'
import sys, re, unicodedata

text = sys.argv[1]
ascii_txt = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
slug = re.sub(r"[^\w-]+", "-", ascii_txt).strip("-")
# Collapse duplicate dashes but keep original case.
slug = re.sub(r"-{2,}", "-", slug)
print(slug if slug else "unnamed-study")
PY
)

new_root="$(dirname "$root_dir")/$slug"
if [[ "$root_dir" != "$new_root" ]]; then
    if [[ -e "$new_root" ]]; then
        echo "[ERROR] Cannot rename to $new_root: target exists" >&2
        exit 1
    fi
    echo "[INFO] Renaming dataset folder to $new_root"
    mv "$root_dir" "$new_root"
    root_dir="$new_root"
fi

cd "$root_dir"

# If an example dataset_description.json already exists (as in the repo
# template), default to overwriting it so the new metadata is written
# without needing an explicit --force flag.
if [[ -f "dataset_description.json" && -z "$force_flag" ]]; then
    echo "[INFO] dataset_description.json exists – overwriting with --force"
    force_flag="--force"
fi

echo "[INFO] Creating virtual environment"
"$python_cmd" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "[INFO] Upgrading pip"
python -m pip install --upgrade pip >/dev/null

echo "[INFO] Installing local packages"
"$root_dir/code/MyBidsApp/dev_install.sh"

author_flags=()
for a in "${authors[@]}"; do
    author_flags+=(--authors "$a")
done
funding_flags=()
for f in "${fundings[@]}"; do
    funding_flags+=(--funding "$f")
done
ethics_flags=()
for e in "${ethics[@]}"; do
    ethics_flags+=(--ethics-approval "$e")
done
reference_flags=()
for r in "${references[@]}"; do
    reference_flags+=(--reference "$r")
done

echo "[INFO] Creating dataset_description.json"
bidscomatic-cli init "$root_dir" --name "$name" "${author_flags[@]}" \
    --dataset-type "$dataset_type" \
    ${license:+--license "$license"} \
    ${acknowledgements:+--acknowledgements "$acknowledgements"} \
    ${how_to_ack:+--how-to-acknowledge "$how_to_ack"} \
    "${funding_flags[@]}" "${ethics_flags[@]}" "${reference_flags[@]}" \
    ${dataset_doi:+--dataset-doi "$dataset_doi"} \
    $force_flag --no-rename-root

echo "[INFO] Setup complete: $root_dir"

# Drop into an interactive shell within the new dataset root using the
# freshly created virtual environment.  We start an interactive shell,
# source the activation script after the user's rc files have run and
# then replace that shell with another instance that does not re-read
# any rc files so the virtual environment prompt is preserved.
cd "$root_dir"

shell="${SHELL:-bash}"
case "$(basename "$shell")" in
    zsh)
        no_rc="-f"
        ;;
    bash)
        no_rc="--norc"
        ;;
    *)
        no_rc=""
        ;;
esac

exec "$shell" -ic "source .venv/bin/activate && exec \"$shell\" $no_rc -i"
