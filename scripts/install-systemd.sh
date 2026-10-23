#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
[[ $(id -u) == 0 ]] || { echo 'No Linux com systemd, use sudo bash scripts/install-systemd.sh.' >&2; exit 1; }
[[ -d /run/systemd/system ]] || { echo 'systemd ativo não encontrado; não use no Termux/PRoot.' >&2; exit 1; }
accept=()
for arg in "$@"; do
    case "$arg" in --accept-eula) accept=(--accept-eula) ;; *) echo 'Opção inválida.' >&2; exit 2 ;; esac
done
command -v python3 >/dev/null || { echo 'Instale python3 antes.' >&2; exit 1; }
dest=/srv/smart-vanilla
code=/opt/smart-vanilla
for path in "$dest" "$code"; do
    [[ ! -L $path ]] || { echo "Diretório de instalação é um link: $path" >&2; exit 1; }
done
if systemctl is-active --quiet minecraft.service; then
    echo 'Pare o serviço com sudo systemctl stop minecraft.service antes de instalar/atualizar.' >&2
    exit 1
fi
id minecraft >/dev/null 2>&1 || useradd --system --home-dir "$dest" --shell /usr/sbin/nologin minecraft
install -d -o root -g root -m 755 "$code"
if [[ $SMART_CODE_ROOT != "$code" ]]; then
    for dir in scripts docs systemd .github config; do cp -a "$SMART_CODE_ROOT/$dir" "$code/"; done
    for src in "$SMART_CODE_ROOT/"*.sh "$SMART_CODE_ROOT/README.md" "$SMART_CODE_ROOT/LICENSE" "$SMART_CODE_ROOT/server.properties"; do cp "$src" "$code/"; done
fi
chown -R root:root "$code"
chmod -R go-w "$code"
install -d -o minecraft -g minecraft -m 750 "$dest"
for name in config .runtime .cache .run logs backups; do
    [[ ! -L $dest/$name ]] || { echo 'Link inesperado no diretório de dados.' >&2; exit 1; }
    install -d -o minecraft -g minecraft -m 700 "$dest/$name"
done
for src in "$SMART_CODE_ROOT/config/"*.conf "$SMART_CODE_ROOT/server.properties"; do
    if [[ $src == */config/* ]]; then target="$dest/config/$(basename "$src")"; else target="$dest/server.properties"; fi
    if [[ ! -e $target ]]; then install -o minecraft -g minecraft -m 600 "$src" "$target"; fi
done
# The service's account may modify data but never its root-owned Python/Bash code.
runuser -u minecraft -- env SMART_SERVER_ROOT="$dest" /bin/bash "$code/install-linux.sh" --no-start "${accept[@]}"
install -m 644 "$code/systemd/minecraft.service" /etc/systemd/system/minecraft.service
systemctl daemon-reload
systemctl enable minecraft.service
printf 'Serviço instalado. Inicie com: sudo systemctl start minecraft.service\n'
