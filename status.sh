#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/scripts/common.sh"
if [[ ${1:-} == --watch ]]; then
    while true; do
        printf '\033[2J\033[H'
        smart status
        sleep 3
    done
else
    smart status "$@"
fi
