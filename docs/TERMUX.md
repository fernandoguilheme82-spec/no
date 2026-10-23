# Android / Termux

## Instalar e iniciar

```bash
pkg update
pkg install -y git
git clone https://github.com/fernandoguilheme82-spec/no.git
cd no
bash install-termux.sh
```

O script deve rodar no Termux normal, sem `su`. Confirma arquitetura (`aarch64`, `armv7l`/`armv8l`, `x86_64`), instala dependências dos repositórios configurados e testa a execução de `java -version`. Java 8 nativo só é aproveitado se realmente executável. Sem ele, usa PRoot-Distro com contêiner **próprio** `smartvanilla`, sem alterar seu Ubuntu existente.

A versão atual do PRoot-Distro aceita imagens OCI: o instalador usa `ubuntu:24.04 --name smartvanilla`. Na interface clássica usa `ubuntu --override-alias smartvanilla`. Detecta a interface por `install --help`; não remove nem reseta contêineres. O PRoot-Distro valida os arquivos/imagens conforme seu mecanismo de distribuição. Dentro do Linux, Temurin 8 é obtido pela API oficial Adoptium, validado por SHA-256 e executado antes de preparar o Minecraft.

A arquitetura é nativa; não há QEMU/emulação x86 no ARM. Se a Adoptium não disponibilizar o binário necessário, a instalação falha com diagnóstico, sem alegar sucesso.

O projeto é vinculado a `/opt/smart-vanilla` dentro do PRoot. Os arquivos continuam em `~/no` no Termux, incluindo `world/`, `.runtime/`, `.run/`, `backups/` e `logs/`. Não execute dois inicializadores ao mesmo tempo; há trava exclusiva que impede a segunda instância. Mantenha o clone em um caminho curto e privado, como `~/no`; armazenamento compartilhado `/sdcard` não oferece as mesmas permissões, links ou execução.

Na primeira preparação você precisa ler a [EULA](https://aka.ms/MinecraftEULA) e digitar `ACEITO`. Em automação controlada, `--accept-eula` registra essa decisão explícita; não use a opção sem aceitar os termos. `--no-start` instala sem iniciar. Depois:

```bash
cd ~/no
bash start-termux.sh
```

Abra outra sessão do Termux para comandos:

```bash
cd ~/no
bash console.sh list
bash console.sh --save
bash status.sh --watch
bash backup.sh
bash stop-server.sh
```

O console não é o prompt no terminal ocupado pelo log: use `console.sh` na segunda sessão. Ctrl+C no painel só fecha o painel; Ctrl+C no inicializador solicita parada do servidor. Espere o backup final terminar antes de fechar o app.

## Compatibilidade e limites

Minecraft 1.12.2 usa Java antigo; esta distribuição exige Java **8**. Java 17/21 instalado no Android não substitui automaticamente o Java 8. Binários Linux da Adoptium dependem de glibc e entram pelo PRoot; o Android nativo usa Bionic. Não copie um `java` Linux para `$PREFIX/bin`.

PRoot não exige root real, mas tem custo de chamadas de sistema e não oferece systemd, namespaces ou limites cgroup próprios. O usuário “root” mostrado no contêiner não é root do Android. Mantenha a sessão do inicializador viva. Algumas versões do Android bloqueiam métricas `/proc`; nesse caso elas aparecem indisponíveis. Se a RAM disponível não puder ser medida, a engine recusa iniciar para não inventar um orçamento seguro. Não há tentativa de burlar proteções do sistema.

As fontes oficiais explicam o funcionamento e as limitações do [PRoot-Distro](https://github.com/termux/proot-distro#limitations) e a instalação do [Termux](https://github.com/termux/termux-app#installation). A implementação contém caminhos para as duas interfaces, mas a execução física em Android/ARM64 deve ser validada no dispositivo; CI Linux x86_64 não substitui esse teste.

Um celular com 8 GB pode dividir a RAM entre Android, servidor e Zalith; isso não significa 8 GB disponíveis para heap. Comece com `PROFILE=economico`, poucos jogadores e `view-distance=4` se houver atrasos. Altere configurações com o servidor parado. Evite exploração simultânea de regiões novas no começo.

O wake lock ajuda a evitar suspensão, mas não impede o Android de matar processos por memória, temperatura ou restrição de bateria. Permita execução em segundo plano nas configurações do fabricante e confira a temperatura do aparelho. A engine não altera serviços Android nem executa limpeza agressiva de RAM.

## Falhas de instalação e atualização

Reexecute `bash install-termux.sh --no-start` após corrigir rede/dependências. A operação não substitui mundos ou configurações e não aceita EULA automaticamente. Um JAR ou Java anterior com integridade/versão inválida precisa ser movido manualmente antes de novo download; o instalador não o apaga.

Uma instalação interrompida de PRoot pode exigir diagnóstico pelo `proot-distro list`; não use `reset` ou `remove` como tentativa genérica. Nunca apague `~/no/world` para resolver Java. DNS no contêiner, disponibilidade dos mirrors e restrições do operador de rede podem interromper downloads.

Para atualizar o código, pare, preserve seu backup e use `git pull --ff-only`. Não atualize arquivos enquanto a engine está executando. Se já usa outro servidor na porta 25565, pare-o ou configure outra porta antes de iniciar este.
