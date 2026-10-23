#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/scripts/common.sh"
if (($#)); then echo 'Uso: bash start-linux.sh' >&2; exit 2; fi
exec python3 "$SMART_CODE_ROOT/scripts/smart.py" --root "$SMART_ROOT" run
