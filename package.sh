#!/usr/bin/env bash
set -euo pipefail

ADDON_NAME="anki-fsrs-preset-manager"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST_DIR="${ROOT_DIR}/dist"
OUTPUT="${DIST_DIR}/${ADDON_NAME}.ankiaddon"

mkdir -p "${DIST_DIR}"
rm -f "${OUTPUT}"

cd "${ROOT_DIR}"
zip -r "${OUTPUT}" \
  manifest.json \
  config.json \
  __init__.py \
  fsrs_preset_manager \
  -x '*/__pycache__/*' '*.pyc' '*.pyo' '*.DS_Store' '*/.DS_Store'

echo "Created ${OUTPUT}"
