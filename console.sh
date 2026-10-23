#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/scripts/common.sh"
if (($#)); then
    case "$1" in
        --save) smart save ;;
        --audit-items) smart audit-items ;;
        *) smart command "$@" ;;
    esac
else
    echo 'Console local. Use outra sessão para ver logs. Digite sair para fechar somente este console.'
    while IFS= read -r -p 'minecraft> ' cmd; do
        [[ $cmd == sair ]] && break
        [[ -z $cmd ]] && continue
        if [[ $cmd == stop || $cmd == /stop ]]; then
            smart stop
            break
        fi
        smart command "$cmd" || true
    done
fi
