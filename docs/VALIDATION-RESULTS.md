# Relatório de validação

Data: 23/10/2026.

Código verificado: [`4899396`](https://github.com/fernandoguilheme82-spec/no/commit/4899396f2b86ab43e0a74362c555b523607bd831).

**CI concluído com sucesso:** [Validate SMART VANILLA — execução 39979124134](https://github.com/fernandoguilheme82-spec/no/actions/runs/39979124134).

| Verificação executada | Resultado e alcance |
|---|---|
| Estrutura | 32 caminhos obrigatórios conferidos; `teste.txt` preexistente preservado. |
| Bash / Python / YAML | Sintaxe e estrutura aprovadas; ShellCheck e Actionlint aprovados. |
| Suíte Linux da engine | **33 testes aprovados, sem skips**, em 13,382 s no GitHub Actions. Inclui processo de servidor simulado, identificado como fixture. |
| Memória | Perfis, tetos, recusa de heap excessivo, pressão consecutiva, parada/recuperação e métricas locais testadas. |
| Supervisor simulado | Início, console, TCP local, save, stop, sinal, recuperação limitada/desativada, estado após crash, backup com reinício e parada durante backup aprovados. |
| Dados em fixtures | Inventários preservados na restauração, mundo anterior mantido, corrupção/traversal/links recusados, falta de disco e locks testados. |
| Download oficial | Metadados Mojang e JAR 1.12.2 baixados e verificados no CI. SHA-1 oficial confirmado: `886945bfb2b978778c3a0288fd7fab09d315b25f`. |
| Java 8 x86_64 real | JAR executado até a exigência da EULA; nenhum mundo criado com `eula=false`. |
| Java 8 ARM64 real | Instalador baixou Temurin 8 Linux/aarch64 com SHA-256 verificado. O JAR oficial executou e respeitou `eula=false`. |
| Serviço systemd | Unidade passou em `systemd-analyze verify` local. Instalação/boot de um serviço real não foram executados. |
| Execução local restrita | 25 testes aprovados e 8 de socket Unix pulados; AF_UNIX é bloqueado por este ambiente. O CI executou os 8 e aprovou todos. Download Mojang direto local não respondeu; foi confirmado no CI. |

Os logs reais `official-jar-validation-39979124134` e `official-arm64-validation-39979124134` foram exportados como artefatos da execução. Retenção configurada: 7 dias; após expirar, execute novamente o workflow para gerar evidência nova.

## Preparado, mas não executado nesta entrega

- **Mundo Minecraft real:** o workflow manual exige aceitação explícita da EULA pelo operador. Está implementado o teste de geração, protocolo 340, save, stop, backup, reinício e restauração com JAR real, mas não foi disparado nesta entrega. Os testes de backup/supervisão aprovados acima usam fixtures; não substituem essa verificação.
- **Android físico:** instalação de pacotes Termux, Java 8 dentro do PRoot no aparelho, métricas disponíveis, temperatura e disputa de recursos com Zalith. Linux ARM64 aprovado não equivale a Android validado.
- **Infraestrutura própria:** instalação efetiva do systemd, registro do runner e disponibilidade contínua da máquina.
- **Multiplayer externo:** firewall, encaminhamento, CGNAT, conta/agente de túnel e entrada de um jogador real. Nenhum endereço público ativo foi criado.
- **Carga:** não foi realizado teste de capacidade com dez jogadores, exploração simultânea, fazendas ou redstone intensiva.

## Commits de implementação e correção

| Commit | Conteúdo |
|---|---|
| [`d073a6b`](https://github.com/fernandoguilheme82-spec/no/commit/d073a6bf32ac996879fc252c5983301a30aad598) | Implementação da engine, instaladores, serviço, workflows, documentação e testes. |
| [`4198daa`](https://github.com/fernandoguilheme82-spec/no/commit/4198daa6294021b16d5e2fcfc2a9a4da9e29dfe0) | Correção do hash fixado, declaração da label do runner, atualização das Actions e CI ARM64. |
| [`4899396`](https://github.com/fernandoguilheme82-spec/no/commit/4899396f2b86ab43e0a74362c555b523607bd831) | Correção da janela de estado após crash e teste de regressão; CI completo aprovado. |

Este relatório é registrado em commit documental posterior. Ele não altera o código verificado. O servidor usa exclusivamente o JAR Vanilla oficial, sem mods ou plugins, e é baixado durante a instalação. Não há arquivo Minecraft redistribuído no Git, servidor público já ligado nem hospedagem 24 horas fornecida pelo GitHub.
