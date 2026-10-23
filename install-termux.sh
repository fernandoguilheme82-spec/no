#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/scripts/common.sh"
accept=()
start=true
for arg in "$@"; do
    case "$arg" in
        --accept-eula) accept=(--accept-eula) ;;
        --no-start) start=false ;;
        *) echo 'Uso: bash install-termux.sh [--accept-eula] [--no-start]' >&2; exit 2 ;;
    esac
done
if [[ ${PREFIX:-} != *com.termux* ]] || ! command -v pkg >/dev/null; then
    echo 'Execute no Termux normal, fora do Ubuntu/PRoot e sem su. No Linux use install-linux.sh.' >&2
    exit 1
fi
case "$(uname -m)" in
    aarch64|armv7l|armv8l|x86_64) ;;
    *) echo 'Arquitetura sem runtime automático validável. Use Linux ARM64 ou x86_64.' >&2; exit 1 ;;
esac
case "$SMART_ROOT" in /sdcard/*|/storage/*) echo 'Clone em ~/no, no armazenamento interno privado do Termux.' >&2; exit 1 ;; esac
if [[ $SMART_ROOT == *:* ]]; then echo 'O caminho não pode conter dois-pontos.' >&2; exit 1; fi
printf 'Arquitetura: %s\n' "$(uname -m)"
pkg install -y python git curl ca-certificates coreutils util-linux
mkdir -p "$SMART_ROOT/.termux"
chmod 700 "$SMART_ROOT/.termux"
# Only install a native Java 8 when the configured Termux repositories offer it.
if ! smart java >/dev/null 2>&1 && apt-cache show openjdk-8 >/dev/null 2>&1; then
    pkg install -y openjdk-8
fi
if smart java >/dev/null 2>&1; then
    smart setup "${accept[@]}"
    printf 'native\n' > "$SMART_ROOT/.termux/mode"
else
    pkg install -y proot-distro
    container=smartvanilla
    if ! proot-distro login "$container" -- /bin/true >/dev/null 2>&1; then
        help_text="$(proot-distro install --help 2>&1)"
        if [[ $help_text == *--name* ]]; then
            proot-distro install ubuntu:24.04 --name "$container"
        else
            # Classic proot-distro package (pre OCI rewrite).
            proot-distro install ubuntu --override-alias "$container"
        fi
    fi
    proot-distro login --bind "$SMART_ROOT:/opt/smart-vanilla" "$container" -- \
        /bin/bash -c 'apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y python3 ca-certificates curl bash coreutils util-linux'
    proot-distro login --bind "$SMART_ROOT:/opt/smart-vanilla" "$container" -- \
        /bin/bash /opt/smart-vanilla/install-linux.sh --no-start "${accept[@]}"
    printf 'proot\n' > "$SMART_ROOT/.termux/mode"
    printf '%s\n' "$container" > "$SMART_ROOT/.termux/container"
fi
chmod 600 "$SMART_ROOT/.termux/"*
if "$start"; then exec bash "$SMART_ROOT/start-termux.sh"; fi
