# GitHub Actions — validação do projeto

O GitHub distingue automação de desenvolvimento de hospedagem de aplicações. Os [termos de Actions](https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features#actions) não autorizam usar runners hospedados para atividades alheias à produção, teste, implantação ou publicação do projeto. Assim, este método entrega **teste temporário do servidor**, com acesso local, sem hospedagem pública para jogar. Use Termux ou máquina própria para multiplayer contínuo.

## Rodar o servidor de teste

1. Abra [a página do workflow](https://github.com/fernandoguilheme82-spec/no/actions/workflows/minecraft-server.yml).
2. Clique em **Run workflow** na branch `main`.
3. Leia a EULA e marque `accept_eula` se a aceitar. Sem essa opção, o job é ignorado e nenhum mundo é iniciado.
4. Escolha 5, 10 ou 15 minutos. Acompanhe o job `server`.
5. Baixe `smart-vanilla-test-ID` em **Artifacts**. O arquivo inclui logs e um backup do mundo de teste com SHA-256.

O job prepara Temurin 8, valida o download oficial, inicia um mundo temporário escutando em `127.0.0.1`, confirma Minecraft 1.12.2 pelo protocolo 340, salva, faz backup com Java parado, religa e restaura o mundo de teste. O console completo fica em `ci-real-session.log`; o estado aparece periodicamente no job. A EULA é uma escolha do operador no dispatch, não uma aceitação automática feita pelo projeto.

O limite configurado do job é 25 minutos para acomodar preparação e desligamento. O [limite atual de runners hospedados](https://docs.github.com/en/actions/reference/limits) é 6 horas por job; este workflow não tenta usar todo esse tempo. Não há agendamento periódico nem relançamento automático para contornar limites. Cancelamento forçado pelo GitHub, falha da VM ou timeout podem impedir as etapas finais; `always()` tenta exportar os logs que existirem, mas não garante sua execução após remoção da máquina.

## Conectividade e persistência

Não existe porta pública 25565 garantida em um runner hospedado. O IP de saída do job não é um endereço de entrada para jogadores. O teste usa porta local temporária; não anuncia endereço funcional nem configura túneis.

Um túnel TCP autenticado pode ser legítimo para testes de rede autorizados, mas sua configuração não transforma Actions em hospedagem permitida para jogos. Para acesso externo normal, configure o túnel em **Termux ou runner próprio** conforme [MULTIPLAYER.md](MULTIPLAYER.md). Segredos de agente devem ficar fora do Git; em workflows que realmente necessitem deles para teste, use GitHub Secrets, jamais argumentos impressos em logs.

A VM do GitHub desaparece após a execução. Não há restauração de mundo entre execuções neste workflow; é sempre um teste independente. Os artefatos duram 7 dias conforme configuração, e podem estar sujeitos a cotas/alterações da conta. Guarde backups reais fora de Actions.

## CI automático

`validate.yml` roda em push/PR e manualmente:

- Estrutura, Bash, Python, YAML, ShellCheck e Actionlint.
- Testes determinísticos de memória, corrupção, restauração, locks e ciclo do supervisor com processo simulado claramente identificado.
- Java 8 real, download Mojang e integridade fixada do JAR 1.12.2.
- Execução real do JAR com **eula=false**, confirmando que o servidor exige aceitação e não cria mundo.

Esse job não cobre início de mundo real: esse teste depende do dispatch com aceitação explícita da EULA. Consulte [TESTING.md](TESTING.md) para distinguir cada evidência. Actions de terceiros estão fixadas por commit, `GITHUB_TOKEN` tem só leitura e o checkout não persiste credenciais.
