#!/usr/bin/env bash
set -euo pipefail

root="$(cd -- "$(dirname "$0")" && pwd)"   # → …/code/MyBidsApp

# helper: install one package from inside its directory
install_editable () {
  local pkg_dir="$1"
  echo "▶ pip install -e $pkg_dir"
  ( cd "$pkg_dir" && pip install -e . )
}

# 1) install dependencies in any order you like
install_editable "$root/bidscomatic"
install_editable "$root/dicomatic"
install_editable "$root/cbrain_bids_pipeline"

# 2) install the hub last
install_editable "$root/bids_cli_hub"

echo "✅  All editable installs complete."
