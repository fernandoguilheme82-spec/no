# Relatório de validação

Data: 23/10/2026.

- Arquivo preexistente `teste.txt` preservado.
- Implementação do servidor: JAR oficial Vanilla 1.12.2 baixado durante instalação; sem mods ou plugins.
- Suíte local: 29 testes; 21 aprovados e 8 testes de supervisor não executados porque este ambiente bloqueia sockets AF_UNIX.
- Integridade, memória, corrupção, backup/restore e preservação dos dados: testes locais executados sobre fixtures, não sobre um mundo Minecraft real.
- Download Mojang local: não concluído por indisponibilidade de acesso nesta rede.
- Validação automática GitHub: consulte a execução associada ao commit; este relatório será atualizado após a publicação.
- Mundo Minecraft real: teste preparado em workflow manual, condicionado à aceitação explícita da EULA pelo operador; não afirmar que passou antes de rodar.
- Android/Termux físico, Linux systemd real, runner próprio e acesso TCP externo: não executados nesta entrega, dependem do dispositivo/infraestrutura do operador.

Não existe endereço público ativo ou servidor 24 horas fornecido pelo GitHub neste projeto.
