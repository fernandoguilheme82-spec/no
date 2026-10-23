# SMART VANILLA SURVIVAL 1.12.2

[![Validate](https://github.com/fernandoguilheme82-spec/no/actions/workflows/validate.yml/badge.svg)](https://github.com/fernandoguilheme82-spec/no/actions/workflows/validate.yml)

Servidor **oficial Minecraft Java 1.12.2**, Survival, com SMART SERVER ENGINE externo. Sem Forge, Fabric, Bukkit, Paper, mods ou plugins. Jogadores usam Minecraft Java **1.12.2** normal e autenticação oficial. O JAR não é redistribuído: o instalador baixa diretamente da Mojang, confere os metadados e o SHA-1 oficial fixado da versão; também registra SHA-256 local.

O mundo mantém geração normal, estruturas, redstone, mobs, agricultura, mineração, Nether, End e inventários. “Infinito” significa os limites normais do Minecraft (`max-world-size=29999984`), sujeito a disco e capacidade do dispositivo.

## O que a engine faz

| Recurso | Comportamento real |
|---|---|
| Memória | Detecta RAM disponível e limites cgroup; reserva espaço para sistema e memória nativa; recusa heap excessivo. |
| Perfis | `economico`, `equilibrado` e `desempenho`; padrão equilibrado, heap automático limitado a 2048 MiB. |
| Monitor | PID, RSS, CPU amostrada, tempo, disco, saves confirmados, backups, TCP local e eventos. Métrica inacessível aparece N/D. |
| Saves | `save-all flush` periódico, confirmação no log, mais salvamento durante `stop`. |
| Backups | Avisa os jogadores, salva, **para o Java**, copia mundo e inventários, confere checksum e reinicia. Há uma desconexão temporária. Padrão: a cada 6 horas e na parada manual. |
| Recuperação | Intervalo e até três tentativas consecutivas. Parada manual e `/stop` não reiniciam. Sem cópia enquanto Java escreve. |
| Entidades/chunks | Reconhece sinais de sobrecarga do log. Auditoria opcional de itens. Não altera geração, mobs, chunks ou sobrevivência. |
| Proteção | Console Unix local com permissões restritas, sem porta administrativa TCP e sem RCON. |

Não há TPS exato, eliminação garantida de lag, RAM “infinita” ou proteção absoluta contra corte de energia/Android encerrando o aplicativo. A API Vanilla 1.12.2 não permite garantir a identificação de todos os itens nomeados/importantes por seletores. Por isso **nenhum item é apagado pela engine**; limpeza destrutiva fica desativada e sua ativação é recusada. O despawn natural do jogo continua normal.

## Tutorial A — Termux (método principal)

Use Termux atual de uma [fonte oficial](https://github.com/termux/termux-app#installation), no armazenamento privado do app. Não execute como root nem de dentro de outro Ubuntu/PRoot.

```bash
pkg update
pkg install -y git
git clone https://github.com/fernandoguilheme82-spec/no.git
cd no
bash install-termux.sh
```

O instalador detecta a arquitetura e procura Java **8** executável. Se não existir no Termux, prepara um contêiner PRoot separado, instala Linux e baixa Temurin 8 da Adoptium para a arquitetura correta com SHA-256 verificado. Não tenta executar um Java Linux/glibc diretamente no Android/Bionic, nem substitui Java 8 por Java moderno sem validação.

Leia a [EULA](https://aka.ms/MinecraftEULA) e digite `ACEITO` quando solicitado. A instalação inicia o servidor e exibe o log. Para instalar sem iniciar: `bash install-termux.sh --no-start`. Uma segunda execução preserva mundo, configurações, EULA e backups. Não remova o contêiner `smartvanilla`.

Para ligar novamente:

```bash
cd ~/no
bash start-termux.sh
```

Espere `Done (...)! For help...`. Em **outra sessão do Termux**, na pasta `~/no`:

```bash
bash status.sh
bash status.sh --watch
bash console.sh list
bash console.sh --save
bash stop-server.sh
```

`Ctrl+C` no inicializador também solicita parada segura. Para jogar no próprio celular, o endereço é `127.0.0.1:25565`. Na mesma rede Wi-Fi, use o IP local do celular. Para amigos fora de casa, configure o acesso descrito em [Multiplayer](docs/MULTIPLAYER.md); clonar o repositório não cria um IP público.

Desative restrições de bateria do Termux nas configurações do Android e mantenha o aplicativo aberto. O inicializador tenta usar `termux-wake-lock` quando disponível e libera o bloqueio ao sair. O Android ainda pode encerrar processos, e jogar no Zalith no mesmo aparelho disputa CPU/RAM com o servidor. Comece com poucos jogadores; `max-players=10` é um limite de configuração, não garantia de capacidade. Detalhes: [TERMUX.md](docs/TERMUX.md).

## Tutorial B — GitHub Actions (validação temporária)

1. Abra [Actions deste repositório](https://github.com/fernandoguilheme82-spec/no/actions).
2. Selecione **SMART VANILLA - sessao temporaria de validacao**.
3. Clique em **Run workflow**, escolha `main`, marque a aceitação da EULA somente após lê-la e escolha 5, 10 ou 15 minutos.
4. Abra o job para acompanhar o estado. Ele inicia o JAR real em Java 8, verifica a versão pelo protocolo, testa save, parada, backup, reinício e restauração.
5. Ao terminar, baixe os logs e o snapshot do mundo de teste em **Artifacts** (retenção de 7 dias).

**Este método é CI/teste do projeto.** GitHub-hosted Actions não é hospedagem para jogar nem um serviço 24 horas. Os [termos do GitHub](https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features#actions) restringem uso dos runners hospedados a atividades do projeto. O workflow tem limite de 25 minutos, abaixo do limite geral atual de [6 horas por job hospedado](https://docs.github.com/en/actions/reference/limits). Não há agendamento de relançamento ou técnica para contornar limites.

O teste escuta apenas em loopback, sem túnel ou IP público. A máquina é descartada; o mundo de teste não é reaproveitado na próxima execução. Artefatos têm retenção limitada e não são backup permanente. Para multiplayer real pelo GitHub, use sua máquina no Tutorial C. Mais detalhes: [GITHUB-ACTIONS.md](docs/GITHUB-ACTIONS.md).

A validação automática de cada push não aceita a EULA: verifica o download e executa o JAR até a barreira de `eula=false`, além dos testes independentes da engine.

## Tutorial C — GitHub com runner próprio

Você precisa de **um Linux ligado e recursos próprios**: computador, máquina doméstica ou VPS. O GitHub controla o serviço; não fornece essa máquina. systemd não roda normalmente no PRoot do Android.

Em Debian/Ubuntu Linux compatível, usando um usuário normal:

```bash
sudo apt-get update
sudo apt-get install -y git python3 ca-certificates curl bash util-linux
git clone https://github.com/fernandoguilheme82-spec/no.git
cd no
sudo bash scripts/install-systemd.sh
```

Aceite a EULA interativamente. O instalador cria a conta de serviço `minecraft`, mantém código em `/opt/smart-vanilla` sob controle do root e dados em `/srv/smart-vanilla`. O serviço executa com usuário sem privilégios e tem logs persistentes. Para iniciar/parar diretamente:

```bash
sudo systemctl start minecraft.service
sudo systemctl stop minecraft.service
sudo journalctl -u minecraft.service -f
```

Depois:

1. No GitHub, vá em **Settings → Actions → Runners → New self-hosted runner** e escolha o Linux/arquitetura da sua máquina.
2. Siga os comandos **gerados pelo GitHub**, valide o SHA-256 mostrado e registre o runner como usuário separado (`actionsrunner`), com a label adicional `smart-vanilla`. Não publique o token temporário.
3. Instale o serviço do runner conforme as instruções oficiais e configure as permissões limitadas descritas em [SELF-HOSTED.md](docs/SELF-HOSTED.md).
4. Abra **Actions → SMART SERVER SELF-HOSTED → Run workflow**. Escolha `status`, `start`, `stop`, `restart` ou `backup`.

O Minecraft pertence ao systemd e continua funcionando após o job terminar. O job não faz checkout de código nem roda em eventos de PR. Este repositório é público: siga as restrições de segurança do tutorial antes de conectar uma máquina com dados pessoais. Configure a rede conforme [MULTIPLAYER.md](docs/MULTIPLAYER.md).

Também é possível usar Linux sem serviço, sem root, após instalar as dependências:

```bash
bash install-linux.sh
bash start-linux.sh
```

## Administração diária

Os comandos abaixo são executados na pasta clonada (Termux/Linux simples):

| Tarefa | Comando |
|---|---|
| Painel | `bash status.sh --watch` |
| Console interativo | `bash console.sh` (digite `sair` para fechar só o console) |
| Administrador | `bash console.sh op SEU_NICK` (somente um nome autenticado que você conferiu) |
| Save confirmado | `bash console.sh --save` |
| Auditoria de itens, sem exclusão | `bash console.sh --audit-items` |
| Backup agora (desconecta e religa) | `bash backup.sh` |
| Reinício seguro | `bash scripts/safe-restart.sh` |
| Parar e esperar finalização | `bash stop-server.sh` |
| Saúde local | `bash scripts/health-check.sh` |
| Simular cálculo de heap | `python3 scripts/smart.py memory` |

No serviço Linux, use `sudo -u minecraft env SMART_SERVER_ROOT=/srv/smart-vanilla bash /opt/smart-vanilla/console.sh list` e equivalentes; controle início/parada com systemctl.

**Memória:** pare o servidor, edite `config/memory.conf` e reinicie. Exemplo para pedir 1024 MiB (ainda sujeito ao teto seguro):

```ini
PROFILE=economico
HEAP_MAX_MB=1024
HEAP_MIN_MB=256
RESERVED_MB=1024
```

Os demais valores do arquivo permanecem. Não coloque argumentos de shell nesses arquivos. Heap alto não corrige CPU lenta e deixa menos RAM para o Android/Zalith. No serviço, os arquivos ficam em `/srv/smart-vanilla/config`.

**Jogadores:** com o servidor parado, altere `max-players=10` no `server.properties`. View distance também pode ser reduzida ali, por exemplo para `4`. Reinicie para aplicar. Não há descarregamento mágico de chunks pela engine.

**Restauração:** pare primeiro; confira o arquivo e mantenha seu `.sha256` ao lado:

```bash
bash stop-server.sh
ls -lt backups/
bash restore-backup.sh backups/ARQUIVO_REAL.tar.gz --confirm-restore
bash start-termux.sh
```

Substitua `ARQUIVO_REAL.tar.gz` pelo backup existente. O mundo atual vai para `backups/restore-previous-.../`; não é apagado. Restauração recupera apenas a pasta do mundo, incluindo dimensões, inventários e avanços; não sobrescreve configuração, operadores ou whitelist. Os JSON administrativos estão no arquivo para recuperação manual. Mantenha também uma cópia de backup em outro dispositivo.

**Atualizações:** pare antes de `git pull --ff-only`. Se você alterou arquivos de configuração versionados, preserve essas alterações e resolva eventuais conflitos; não use `git reset --hard`. No serviço, atualize o clone e reexecute `install-systemd.sh` com o serviço parado. Configurações existentes são preservadas.

## Segurança, diagnóstico e validação

`online-mode=true`, RCON desligado, sem tokens ou senhas no repositório. Modo offline é apenas para redes privadas/controladas: veja [MULTIPLAYER.md](docs/MULTIPLAYER.md) antes de considerar essa alteração. A engine não recebe comandos de jogadores comuns; somente o usuário local dono dos arquivos pode usar seu console administrativo. Operadores do jogo continuam com as permissões Vanilla.

Dados, JAR, logs e backups são ignorados pelo Git. Se mudar `level-name`, acrescente a nova pasta ao `.gitignore` antes de usar `git add`. Nunca envie `eula.txt`, tokens de túnel/runner, dumps ou seu mundo público sem conferir o conteúdo.

Testes automatizados, abrangência e limites de verificação: [TESTING.md](docs/TESTING.md). Problemas de Java, porta, autenticação, memória, Android e restauração: [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

Licença MIT para scripts/documentação; Minecraft continua sujeito à EULA da Mojang/Microsoft.
