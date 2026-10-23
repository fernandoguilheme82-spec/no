#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/scripts/common.sh"
accept=()
start=false
for arg in "$@"; do
    case "$arg" in
        --accept-eula) accept=(--accept-eula) ;;
        --start) start=true ;;
        --no-start) start=false ;;
        *) echo 'Uso: bash install-linux.sh [--accept-eula] [--start|--no-start]' >&2; exit 2 ;;
    esac
done
for dep in python3 bash; do
    command -v "$dep" >/dev/null || { echo 'Instale python3 e bash pelo gerenciador da distribuição.' >&2; exit 1; }
done
python3 -c 'import sys; assert sys.version_info >= (3, 9), "Necessário Python 3.9+"'
smart install-java
smart setup "${accept[@]}"
if "$start"; then exec bash "$SMART_CODE_ROOT/start-linux.sh"; fi
