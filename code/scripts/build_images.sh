#!/usr/bin/env bash

###############################################################################
# build_images.sh
#
# Purpose:
#   Build and push the Docker image that contains ICA‑AROMA.
#
# Usage:
#   build_images.sh
#
# Usage Examples:
#   ./build_images.sh
#
# Options:
#   None
#
# Requirements:
#   docker with buildx support and access to ghcr.io
#
# Notes:
#   Uses docker buildx to build multi‑platform images and pushes them to GitHub
#   Container Registry under ghcr.io/youruser/ica_aroma.
#
###############################################################################

set -euo pipefail

TAG="0.1.0"
PLATFORMS="linux/arm64,linux/amd64"

docker buildx build \
  --platform "${PLATFORMS}" \
  --push \
  -t ghcr.io/youruser/ica_aroma:${TAG} \
  "$(dirname "${BASH_SOURCE[0]}")/../ICA-AROMA-master"

