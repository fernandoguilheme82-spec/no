#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/scripts/common.sh"
if (($#)); then echo 'Uso: bash start-termux.sh' >&2; exit 2; fi
[[ -f $SMART_ROOT/.termux/mode ]] || { echo 'Execute bash install-termux.sh primeiro.' >&2; exit 1; }
mode="$(cat "$SMART_ROOT/.termux/mode")"
locked=false
if command -v termux-wake-lock >/dev/null && termux-wake-lock; then locked=true; fi
cleanup() { if "$locked"; then termux-wake-unlock || true; fi; }
trap cleanup EXIT
case "$mode" in
    native) bash "$SMART_ROOT/start-linux.sh" ;;
    proot)
        container="$(cat "$SMART_ROOT/.termux/container")"
        [[ $container == smartvanilla ]] || { echo 'Contêiner inválido.' >&2; exit 1; }
        proot-distro login --bind "$SMART_ROOT:/opt/smart-vanilla" "$container" -- \
            /bin/bash /opt/smart-vanilla/start-linux.sh
        ;;
    *) echo 'Modo desconhecido. Reexecute install-termux.sh.' >&2; exit 1 ;;
esac
