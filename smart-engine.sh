#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/scripts/common.sh"
exec python3 "$SMART_CODE_ROOT/scripts/smart.py" --root "$SMART_ROOT" run "$@"
