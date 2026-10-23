#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
exec bash "$SMART_CODE_ROOT/status.sh" --watch
