#!/usr/bin/env bash
# Source only from scripts in this repository.
set -euo pipefail
SMART_CODE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
SMART_ROOT="${SMART_SERVER_ROOT:-$SMART_CODE_ROOT}"
smart() { python3 "$SMART_CODE_ROOT/scripts/smart.py" --root "$SMART_ROOT" "$@"; }
