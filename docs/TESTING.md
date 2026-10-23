# Testes e limites da entrega

## Executar a suíte

```bash
python3 -m unittest discover -s tests -v
```

Os testes usam diretórios temporários e não tocam seu mundo. A fixture `tests/fake_server.py` é um processo **simulado**, claramente identificado; não é Minecraft. Somente `tests/fake_runner.py` seleciona essa fixture por subclasse. Os inicializadores de produção nunca a usam e validam o hash do JAR oficial antes de cada partida.

Cobertura: perfis/tetos de memória, RAM real, EULA explícita, preservação de JAR inválido, configurações sem execução de shell, padrões multiplayer, backup e inventários de fixture, checksums, corrupção, travessia de diretórios, links, falta de disco, rotação e exclusão mútua. Os testes do supervisor cobrem início/TCP local, save confirmado, console, parada/sinais, backup offline com reinício, parada durante backup, recuperação limitada e desativação da recuperação. Não se trata de um teste de capacidade para dez jogadores.

Para estrutura e análise estática, com PyYAML, ShellCheck e Actionlint instalados:

```bash
python3 tests/validate.py
shellcheck -S warning -e SC1091 ./*.sh scripts/*.sh
actionlint
```

`validate.yml` executa esses checks no GitHub e também baixa o JAR da Mojang, valida metadados/SHA-1 fixado e executa Java 8 real com `eula=false`, verificando que a aceitação é exigida. O JAR fica apenas no job, nunca no commit ou artefato.

O workflow **SMART VANILLA - sessao temporaria de validacao** exige aceitação explícita da EULA. Usa o JAR real e testa protocolo 340/versão 1.12.2, mundo gerado, flush confirmado, parada, backup com JVM desligada, reinício e restauração. Logs são exportados como artefato. O job automático não executa esse teste de mundo real sem consentimento do operador.

## Evidência inicial

Na implementação local, a análise e os testes que não dependem de socket Unix puderam ser executados. Este ambiente bloqueia AF_UNIX com `Operation not permitted`; os testes de supervisor registram skip explícito aqui. O acesso direto por download à Mojang também não respondeu nesta rede; os checks oficiais são executados no CI a partir do commit publicado. O CI completo da execução [39979124134](https://github.com/fernandoguilheme82-spec/no/actions/runs/39979124134) aprovou 33 testes sem skips, ShellCheck/Actionlint e download/execução do JAR em Java 8 Linux x86_64 e ARM64 até a barreira da EULA. Veja [VALIDATION-RESULTS.md](VALIDATION-RESULTS.md) para o relatório e os limites exatos.

Não foram executados em aparelho Android físico: instalação de pacotes Termux, Java 8 ARM64 sob PRoot, consumo/temperatura e concorrência com Zalith. Os caminhos estão implementados, mas execução Linux x86_64 não comprova funcionamento em todo Android.

Também precisam de infraestrutura do operador: instalação/boot real do serviço systemd, registro de runner próprio, firewall/roteador, CGNAT e criação/autenticação de túnel. Não foi provisionado nenhum desses recursos externos, nem criado endereço público.

Os testes não comprovam ausência de toda falha, exploração ou perda de dados. Minecraft 1.12.2 é uma versão antiga; Java 8 atualizado não atualiza automaticamente o código do jogo. Preserve backups externos e use a autenticação oficial.
