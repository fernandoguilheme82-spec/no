# SMART SERVER SELF-HOSTED

Este método usa um Linux **seu**, ligado, com CPU, RAM, disco e rede disponíveis. Pode ser PC, máquina doméstica ou VPS. O GitHub apenas envia comandos ao runner. Ele não entrega gratuitamente o hardware, energia, conexão ou VPS. O serviço Minecraft é independente do job e continua depois que o runner termina seu trabalho.

## 1. Instalar o serviço

Suporte de instalação automática: Linux com systemd, Python 3.9+, glibc, `runuser`, `useradd` e arquitetura com Temurin 8 disponível. Ubuntu 24.04 é a referência. Debian recente também pode funcionar. Em ARM64, o runtime baixado é aarch64; não há emulação. Não use este instalador dentro do PRoot/Termux.

```bash
sudo apt-get update
sudo apt-get install -y git python3 ca-certificates curl bash util-linux
git clone https://github.com/fernandoguilheme82-spec/no.git
cd no
sudo bash scripts/install-systemd.sh
```

Leia e aceite a EULA no terminal. `--accept-eula` só deve ser usado se você já leu e aceitou os termos. A instalação não inicia o serviço automaticamente; habilita o início no boot somente após completar a preparação.

| Local | Conteúdo |
|---|---|
| `/opt/smart-vanilla` | Código controlado pelo root, sem escrita pelo serviço/runner. |
| `/srv/smart-vanilla` | Mundo, configurações, JAR validado, runtime, backups e logs da conta `minecraft`. |
| `/etc/systemd/system/minecraft.service` | Unidade systemd. |

```bash
sudo systemctl start minecraft.service
sudo systemctl status minecraft.service
sudo journalctl -u minecraft.service -f
sudo systemctl stop minecraft.service
```

`logs/engine.log` e `logs/console-...log` persistem em `/srv/smart-vanilla`. O journal segue a política de retenção do seu Linux. A engine cuida dos reinícios limitados após falha do Java. O systemd usa `Restart=on-abnormal` para falha por sinal da própria engine e limita esse caso a três partidas por hora. Erro final de configuração/limite de recuperação da engine retorna código 1 e não é reciclado indefinidamente pelo systemd.

Stop usa stdin e espera o Java salvar e sair. Se Java não responder, há SIGTERM para o shutdown hook; não há SIGKILL automático. Uma JVM travada pode exigir intervenção. Não inicie outro processo apontando para o mesmo mundo enquanto a anterior existir.

## 2. Registrar o runner

Leia as instruções oficiais de [registro](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners) e [segurança](https://docs.github.com/en/actions/reference/security/secure-use#hardening-for-self-hosted-runners). O GitHub recomenda runners próprios em repositórios privados, porque código não confiável pode comprometer o host.

Este repositório é público. Use máquina dedicada/isolada, sem dados pessoais, e mantenha o workflow **somente manual em main**, sem checkout nem execução de código de PR. Não adicione eventos `pull_request`, `pull_request_target` ou jobs de PR ao runner persistente. Considere controlar produção a partir de um repositório privado separado. O código fornecido reduz a superfície, mas não transforma um runner persistente público em ambiente isolado.

Crie um usuário separado, como `actionsrunner`, sem privilégios gerais. Na página do repositório, **Settings → Actions → Runners → New self-hosted runner**, escolha o SO/arquitetura, siga os comandos atuais gerados pelo GitHub e confira o checksum indicado antes de extrair o runner. Durante o registro, inclua a label **smart-vanilla**. Os rótulos `self-hosted` e `Linux` são padrão. Não cole o token temporário em arquivo versionado.

Instale o serviço do runner conforme a página do GitHub, sob a conta `actionsrunner`, não como root. O root pode ser necessário só para instalar esse serviço e as regras de controle abaixo. A conta do runner não precisa ler os mundos nem escrever no código instalado.

Crie o environment `minecraft-production` em **Settings → Environments** e restrinja deployments à branch `main`. Controle quem pode alterar workflows, aprovar mudanças e disparar execuções; uma conta com escrita no repositório é parte da fronteira de confiança.

## 3. Permissões limitadas para controlar o serviço

Com `sudo visudo -f /etc/sudoers.d/smart-vanilla-runner`, e ajustando o nome do usuário se necessário:

```sudoers
actionsrunner ALL=(root) NOPASSWD: /usr/bin/systemctl start minecraft.service, /usr/bin/systemctl stop minecraft.service, /usr/bin/systemctl restart minecraft.service
actionsrunner ALL=(minecraft) NOPASSWD: /usr/bin/python3 /opt/smart-vanilla/scripts/smart.py --root /srv/smart-vanilla backup
```

Confirme o caminho de `systemctl` com `command -v systemctl` antes. Confira a sintaxe com `sudo visudo -cf /etc/sudoers.d/smart-vanilla-runner` e mantenha modo 0440. Não conceda `NOPASSWD: ALL`, `bash` genérico, Python genérico ou permissão de escrever em `/opt/smart-vanilla`. O backup autorizado roda como `minecraft`, não como root.

O workflow só usa comandos fixos selecionados em `case`; não faz `eval` de input, não aceita shell arbitrário, não instala código e não depende do diretório de trabalho do runner.

## 4. Controlar pelo GitHub

Abra **Actions → SMART SERVER SELF-HOSTED → Run workflow**, branch `main`:

| Opção | Ação |
|---|---|
| `status` | Estado e PID da unidade, sem sudo. |
| `start` | Inicia o serviço persistente. |
| `stop` | Salva, encerra e faz backup final quando habilitado. |
| `restart` | Encerra completamente antes de nova partida. |
| `backup` | Solicita o backup offline consistente; avisa, desconecta e reinicia. |

O job dura apenas o controle da operação, com limite de 20 minutos. Não mantém o Minecraft preso ao job. Se ficar aguardando runner, confira se o serviço do runner está online e se a label está correta. O servidor pode continuar funcionando mesmo com o runner offline; nesse caso controle-o localmente via systemctl.

## Console, configuração e restauração

```bash
sudo -u minecraft env SMART_SERVER_ROOT=/srv/smart-vanilla bash /opt/smart-vanilla/status.sh
sudo -u minecraft env SMART_SERVER_ROOT=/srv/smart-vanilla bash /opt/smart-vanilla/console.sh list
sudo -u minecraft env SMART_SERVER_ROOT=/srv/smart-vanilla bash /opt/smart-vanilla/console.sh --save
sudo -u minecraft env SMART_SERVER_ROOT=/srv/smart-vanilla bash /opt/smart-vanilla/backup.sh
```

Pare o serviço antes de editar `/srv/smart-vanilla/server.properties` ou `config/*.conf`. Para restaurar:

```bash
sudo systemctl stop minecraft.service
sudo -u minecraft env SMART_SERVER_ROOT=/srv/smart-vanilla bash /opt/smart-vanilla/restore-backup.sh /srv/smart-vanilla/backups/ARQUIVO_REAL.tar.gz --confirm-restore
sudo systemctl start minecraft.service
```

O mundo anterior permanece em `backups/restore-previous-...`. Para atualizar o código, pare o serviço, atualize seu clone e reexecute `sudo bash scripts/install-systemd.sh`. A instalação recusa atualizar serviço ativo e não substitui configurações de dados existentes. Por isso novos parâmetros de configuração podem exigir inclusão manual após conferir o diff.

Rede de entrada: configure firewall/roteador ou um túnel autenticado na própria máquina, conforme [MULTIPLAYER.md](MULTIPLAYER.md). O runner não abre portas nem cria endereço público automaticamente.
