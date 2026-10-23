# Solução de problemas

## Java / instalação

- **Java 8 não encontrado:** rode o instalador correspondente. `bash scripts/check-java.sh` mostra o binário que realmente passou em `java -version`. Java 17/21 não é selecionado como substituto. Temurin glibc deve executar dentro do PRoot no Android.
- **No such file ao executar Java no Android:** confirme que não está tentando usar binário Linux diretamente no Bionic. Rode `start-termux.sh`, não o Java extraído manualmente.
- **Java não oferecido para arquitetura:** a instalação falha; não baixa x86 para ARM. Confira `uname -m`. Arquitetura não suportada precisa de runtime Java 8 compatível fornecido pelo operador ou de outro host.
- **SHA inválido:** nenhum arquivo é tratado como válido. Verifique rede/disco. O instalador não apaga um `server.jar` existente inválido; mova-o para inspeção e reexecute. Não desative a validação.
- **Download timeout/DNS:** verifique acesso aos domínios Mojang, Adoptium e GitHub, certificados e DNS do PRoot. A rede deste ambiente de desenvolvimento pode ser diferente da sua. Não troque o JAR por um mirror não verificado.
- **EULA:** o projeto não aceita por você. Execute o instalador interativamente, leia os termos e confirme. Em Actions, marque a opção somente após aceitar.

## Início, console e rede

- **Caminho longo para socket:** clone em `~/no`; não use caminhos profundos. O limite é do socket Unix, incluindo o caminho real do Termux.
- **Address already in use / Failed to bind:** outro servidor ocupa a porta. Use `ss -ltn` no Linux quando disponível e pare o processo correto. Não use `pkill java`, pois pode matar outros jogos/serviços. Também pode haver IP fixado incorretamente: mantenha `server-ip=` vazio.
- **Supervisor desligado:** inicie pelo launcher correto. `java -jar` manual não fornece console/backup/recuperação da engine. PIDs antigos não são usados para matar processos arbitrários.
- **Console local sem permissão:** execute como o mesmo usuário que iniciou o servidor. No systemd use os comandos `sudo -u minecraft` do tutorial. `.run` é privado; não mude para 0777 nem exponha RCON para contornar o problema.
- **Socket Unix bloqueado:** o ambiente precisa suportar sockets AF_UNIX e locks `flock`. Não há fallback administrativo TCP público. Use host Linux/Termux compatível. Um ambiente de teste restrito pode bloquear o socket e deve registrar o teste como não executado.
- **Amigos não entram:** `tcp_local=true` só prova resposta local. Veja IP, CGNAT, firewall e túnel em [MULTIPLAYER.md](MULTIPLAYER.md). Endereço de saída do GitHub não é IP de entrada.
- **Invalid session / verify username:** renove a sessão oficial do Minecraft e confira DNS/horário. Não desligue `online-mode` como correção genérica.

## Desempenho e recuperação

- **Heap excede teto seguro:** feche aplicativos, reduza o pedido ou use `auto`. O limite considera RAM disponível, reserva do sistema, overhead nativo e cgroup; swap não é contada como RAM disponível. Não ponha 6–8 GB de heap só porque seu telefone tem 8 GB físicos.
- **RAM não pode ser medida:** a engine para em vez de inventar um valor. Algumas versões de Android/PRoot restringem `/proc`. O painel também pode exibir CPU/RSS como N/D.
- **Can't keep up:** indica atraso reportado pelo próprio Minecraft, sem estimativa confiável de TPS exato. Reduza view-distance com o servidor parado, quantidade de jogadores/exploração simultânea e carga do aparelho. A engine registra o sinal, mas não modifica mobs/redstone/chunks para mascará-lo.
- **Exit 137 / SIGKILL / OutOfMemoryError:** falta de memória é uma hipótese, não diagnóstico certo. Android, operador ou host também podem matar o processo. Confira os logs, temperatura e política de bateria. Após três falhas consecutivas a engine exige intervenção. Não há garantia de salvar dados que o sistema matou antes do save.
- **Não quer recuperação:** configure `AUTO_RECOVERY=false`. `CRITICAL_ACTION=stop` para desligar em pressão de RAM; `restart` tenta recalcular heap depois da parada e respeita o mesmo limite de tentativas. Memória crítica não dispara backup enquanto Java está vivo.
- **Parada demora:** aguarde save, saída do Java e backup final. Não abra uma segunda JVM. Se a engine registrar que espera Java encerrar, pode haver travamento real; inspecione logs/processos. Não há SIGKILL automático nem promessa de recuperar uma JVM congelada.

## Backup e restauração

- Backup usa parada do Java para incluir mundo e inventários em um estado consistente. Há aviso no chat e breve desconexão. Intervalo padrão: 21600 segundos. `BACKUP_INTERVAL_SECONDS=0` desabilita periodicidade; `BACKUP_ON_STOP=false` desliga backup final. Saves periódicos continuam.
- “Sem espaço seguro” não provoca exclusão do mundo ou de backups anteriores para abrir espaço. Libere arquivos conscientemente ou copie backups para outro dispositivo. Só backups completos entram na rotação, depois de um novo snapshot válido.
- Não remova arquivos `.lock`: `flock` usa o inode; excluir trava de um processo ativo pode permitir concorrência. As travas antigas ficam sem bloqueio após o processo morrer e podem ser reutilizadas.
- Restauração exige servidor desligado, `--confirm-restore`, checksum válido e mesmo `level-name`. Tar com caminhos externos, links ou arquivos especiais é recusado antes de alterar o mundo atual.
- O mundo anterior vai para `backups/restore-previous-...`. Diretórios anteriores não entram na rotação dos `.tar.gz`; confira o espaço e gerencie-os manualmente depois de validar a restauração.
- Restauração recupera a pasta do mundo; propriedades, operadores e whitelist permanecem como estão. Os arquivos administrativos estão no tar para recuperação manual.
- Backup não protege o que está no mesmo aparelho contra perda/roubo/defeito físico. Copie snapshots e checksums para outro dispositivo.

## Serviço e GitHub

- Job self-hosted aguardando: confira runner online, label `smart-vanilla`, branch `main`, environment e permissões. GitHub não provisiona o host.
- `sudo: a password is required`: ajuste somente as regras específicas no tutorial, verificando usuário/caminhos. Não use `NOPASSWD: ALL`.
- `start-limit-hit`: investigue a falha antes de `sudo systemctl reset-failed minecraft.service` e de nova partida. O limite existe para interromper ciclos de falha.
- Actions temporário pulou o job: verifique se marcou EULA. Não há mundo persistente nem porta pública nesse método de teste.

Consulte `logs/engine.log`, `logs/console-...log` e `crash-reports/`. Antes de compartilhar logs, remova IPs, identificadores e qualquer dado que você não queira publicar.
