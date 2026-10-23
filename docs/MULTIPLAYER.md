# Como os jogadores entram

Use Minecraft **Java 1.12.2**, opção Multiplayer → Add Server / Direct Connect. Bedrock não é compatível com este servidor e não há tradutor instalado. Clientes sem mods funcionam; cliente Forge com mods de conteúdo pode não ser compatível. A versão de protocolo verificada é 340.

O padrão é `server-port=25565`, `server-ip=` vazio e `online-mode=true`. IP vazio significa escutar nas interfaces disponíveis; não significa IP público. Deixe RCON e Query desligados. O console administrativo usa socket Unix em `.run`, sem porta de rede.

## Escolher o endereço

| Onde o jogador está | Endereço |
|---|---|
| Mesmo celular/PC | `127.0.0.1:25565` |
| Mesmo Wi-Fi/LAN | `IP_LOCAL_DO_HOST:25565` |
| Fora da sua rede, com porta encaminhada | `IP_PUBLICO_REAL:25565` ou DNS correspondente |
| Via túnel TCP | Hostname **e porta exibidos pelo provedor**, apontando para a porta local do servidor |

Nomes em maiúsculas são campos a substituir, não endereços prontos.

## IP local, público e CGNAT

IP local é o endereço do celular/host na rede, encontrado nas informações da conexão Wi-Fi do Android ou em `ip -4 addr` no Linux. Os blocos privados comuns são `10.0.0.0/8`, `172.16.0.0/12` e `192.168.0.0/16`. Ele normalmente não aceita acesso direto da internet.

O IP público é o endereço apresentado pela conexão de internet; veja a página WAN do roteador e compare com o resultado de um serviço de consulta de IP que você escolha. Não confunda gateway (roteador) com host Minecraft. Não publique senha ou painel do roteador.

Em CGNAT, o provedor compartilha IPv4 público entre assinantes. WAN dentro de `100.64.0.0/10` (RFC 6598), IP privado na WAN ou diferença entre WAN e IP externo são indícios de CGNAT/double NAT. Você pode precisar de IPv4 público do provedor ou de túnel; abrir porta apenas no seu roteador não resolve o NAT que você não controla. Referência: [RFC 6598](https://www.rfc-editor.org/rfc/rfc6598).

## Encaminhamento de portas e firewall

Em uma conexão com IPv4 público de entrada:

1. Reserve o IP local do host no DHCP do roteador.
2. Crie uma regra de entrada **TCP 25565 → IP local do host, TCP 25565**. Não encaminhe RCON, SSH ou painel do roteador como parte desta instalação.
3. No Linux, permita TCP 25565 no firewall ativo. Exemplo se você já administra UFW: `sudo ufw allow 25565/tcp`. Não habilite/reset o firewall sem preservar seu acesso SSH.
4. Inicie o servidor e confirme `Done` e `bash scripts/health-check.sh`.
5. Teste de uma rede diferente, por exemplo outro celular em dados móveis. Alguns roteadores não permitem testar o próprio IP público de dentro da LAN (NAT loopback).

Porta aberta não é garantia de que o servidor responde corretamente. `status.sh` verifica apenas TCP **local**. Bloqueio de operadora, firewall externo, regras de VPS e múltiplos roteadores também precisam ser verificados. Não desative a autenticação para corrigir rede.

IPv6 depende de rota pública e firewall IPv6 de todos os lados. Nem todos os jogadores têm IPv6. Ter IPv6 no celular não cria automaticamente um endpoint IPv4 universal.

## Túnel TCP autenticado (alternativa para CGNAT)

Uma opção é o **agente independente** do [playit.gg](https://playit.gg/), que encaminha tráfego até um servidor local sem plugin do Minecraft. Não instale a versão de mod/plugin neste projeto. Veja [downloads oficiais](https://playit.gg/download) e [suporte](https://playit.gg/support/); disponibilidade, cotas, regiões e planos devem ser conferidos no serviço, sem promessa de gratuidade permanente.

Procedimento no **Termux/PRoot ou Linux próprio**:

1. Baixe o agente para o SO/arquitetura corretos a partir do provedor; valide checksum/assinatura quando publicado. Um agente Linux ARM64 usa o Linux PRoot, assim como qualquer executável glibc. Não rode um `curl | bash` desconhecido.
2. Execute o agente separadamente. Use a URL de associação **gerada pelo seu agente**, autentique-se no site oficial e associe-o à sua conta. Essa URL/token é secreta; não a coloque em commits ou prints públicos.
3. No painel, crie um túnel **Minecraft Java / TCP** para o agente do mesmo host. Destino local: `127.0.0.1`, porta `25565`. Se você alterou a porta do Minecraft, use o mesmo valor aqui.
4. Mantenha servidor e agente ligados. Compartilhe somente o hostname/porta de conexão mostrado no painel, nunca as credenciais do agente.
5. Confira acesso por um cliente 1.12.2 de outra rede. Aumentos de latência, indisponibilidade do provedor ou bloqueios de saída na operadora podem afetar a conexão.

A autenticação do agente protege o controle do túnel; não substitui `online-mode=true` do Minecraft. Guarde a configuração do agente fora do clone, com modo 0600. O projeto não instala nem inicia agentes externos automaticamente, não armazena tokens e não inventa um endereço já ativo. O túnel só existe depois da associação pelo dono da conta.

A configuração de túnel em runner hospedado não integra o método de CI: respeite os termos de Actions. Para jogos, use os métodos Termux ou máquina própria.

## DNS e redes móveis

DNS A/AAAA aponta um nome para um endereço; DNS dinâmico acompanha mudanças desse endereço. DNS não atravessa CGNAT e não abre firewall. Um registro SRV de Minecraft pode indicar uma porta diferente, mas precisa corresponder a um endpoint TCP que já funcione. Se usar domínio próprio com túnel, siga as instruções DNS do provedor.

Redes móveis frequentemente usam CGNAT, mudam o IP e bloqueiam conexões de entrada. Trocar Wi-Fi por 4G/5G pode derrubar sessões/túnel. Usar hotspot também envolve regras NAT próprias. Túnel precisa de acesso de saída e de agente compatível com a rede.

## Autenticação e redes privadas

O padrão obrigatório é **online-mode=true**: contas Java autenticadas oficialmente. Erros “Failed to verify username”/“Invalid session” pedem verificar a sessão do launcher, licença, horário, DNS e acesso aos serviços de autenticação.

Se houver uma necessidade explícita em uma **rede privada/controlada**, pare o servidor, restrinja o acesso por firewall/rede privada, mude para `online-mode=false` em `server.properties` e reinicie. A engine não faz essa alteração por você. Esse modo permite que alguém se apresente com o nome de outra pessoa, inclusive operador, e muda a associação de UUID/inventários. Whitelist por nome não autentica identidade nesse cenário. Não publique esse servidor na internet e faça backup antes de alternar o modo.

Sem plugin de login, a engine não pode fornecer autenticação alternativa dentro do Vanilla. Não prometemos acesso seguro universal com autenticação oficial desligada.
