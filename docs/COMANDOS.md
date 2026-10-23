# Comandos do Robô Nicolas 🤖

> Arquivo gerado automaticamente por `python -m nicolas docs`. Não edite à mão.

- **155** comandos registrados
- **96** aliases simples
- **220** atalhos de conversão de unidades (ex.: `.km-mi 10`)
- **471** nomes invocáveis no total

## ⚙️ Sistema (9)

| Comando | Uso | Descrição | Permissão | Módulo |
|---|---|---|---|---|
| .ajuda | `.ajuda` | Explica como usar o bot (aliases: help) | membro | sistema |
| .comandos | `.comandos <busca>` | Pesquisa comandos pelo nome ou descrição (aliases: buscar, cmds) | membro | sistema |
| .desconectar | `.desconectar confirmar` | [dono] Desconecta o bot do WhatsApp (apaga a sessão; será preciso parear de novo) (aliases: sairconta, logoutbot) | dono | sistema |
| .desligarbot | `.desligarbot` | [dono] Desliga o bot (mantém a conta conectada para ligar depois) (aliases: pararbot, stopbot) | dono | sistema |
| .dono | `.dono` | Informações públicas do responsável pelo bot (aliases: criador) | membro | sistema |
| .info | `.info` | Informações sobre o bot (aliases: sobre, bot) | membro | sistema |
| .menu | `.menu [página|categoria]` | Mostra o menu de comandos (paginado) (aliases: m, start) | membro | sistema |
| .ping | `.ping` | Verifica se o bot está respondendo (aliases: p) | membro | sistema |
| .status | `.status` | Estado dos serviços do bot | membro | sistema |

## 🛡️ Administração (39)

| Comando | Uso | Descrição | Permissão | Módulo |
|---|---|---|---|---|
| .abrirgrupo | `.abrirgrupo` | Abre o grupo: todos podem enviar mensagens (aliases: abrir) | administrador | admin |
| .adv | `.adv @usuário [motivo]` | Adverte um participante (3 advertências = remoção) (aliases: advertir) | moderador | admin |
| .advs | `.advs [@usuário]` | Mostra as advertências de um participante (aliases: advertencias) | moderador | admin |
| .antifake | `.antifake on|off` | Liga/desliga o anti-fake (remove números de outros países) | administrador | admin |
| .antiflood | `.antiflood on|off` | Liga/desliga o anti-flood (silencia quem floda) | administrador | admin |
| .antilink | `.antilink on|off` | Liga/desliga o anti-link (apaga links e adverte) | administrador | admin |
| .ativar | `.ativar <módulo>` | Ativa um módulo neste grupo | administrador | sistema |
| .autorizados | `.autorizados` | Lista moderadores e administradores autorizados | moderador | admin |
| .autorizar | `.autorizar @usuário` | Autoriza um participante como administrador do bot | administrador | admin |
| .ban | `.ban @usuário [motivo]` | Bane um participante (e remove, se eu for admin) | administrador | admin |
| .banidos | `.banidos` | Lista os participantes banidos | administrador | admin |
| .bemvindo | `.bemvindo on|off` | Liga/desliga as mensagens de boas-vindas e despedida | administrador | admin |
| .cargo | `.cargo @usuário <membro|mod|admin>` | Define o cargo no bot: membro, mod ou admin | administrador | admin |
| .cmdoff | `.cmdoff <comando>` | Desativa um comando específico neste grupo | administrador | sistema |
| .cmdon | `.cmdon <comando>` | Reativa um comando desativado neste grupo | administrador | sistema |
| .config | `.config` | Mostra as configurações de segurança do grupo (aliases: configuracoes) | administrador | admin |
| .desativar | `.desativar <módulo>` | Desativa um módulo neste grupo | administrador | sistema |
| .desautorizar | `.desautorizar @usuário` | Remove a autorização de administrador do bot | administrador | admin |
| .desban | `.desban @usuário` | Remove o banimento de um participante (aliases: unban) | administrador | admin |
| .desmute | `.desmute @usuário` | Remove o silenciamento (aliases: dessilenciar) | moderador | admin |
| .expulsar | `.expulsar @usuário` | Remove um participante sem banir (aliases: kick) | administrador | admin |
| .fechargrupo | `.fechargrupo` | Fecha o grupo: só administradores enviam mensagens (aliases: fechar) | administrador | admin |
| .horario | `.horario <abre> <fecha>|off` | Define o horário de funcionamento dos comandos | administrador | admin |
| .liberar | `.liberar <palavra>` | Remove uma palavra da lista de proibidas | administrador | admin |
| .logs | `.logs [quantidade]` | Mostra as últimas ações administrativas | administrador | admin |
| .maxadv | `.maxadv <número>` | Define o limite de advertências antes da remoção (2 a 10) | administrador | admin |
| .membro | `.membro [@usuário]` | Exibe informações de um participante (aliases: infomembro) | moderador | admin |
| .modulos | `.modulos` | Lista os módulos e se estão ativos | membro | sistema |
| .mute | `.mute @usuário [tempo]` | Silencia um participante (apago as mensagens dele) (aliases: silenciar) | moderador | admin |
| .prefixo | `.prefixo [novo]` | Consulta ou altera o prefixo dos comandos neste grupo | membro | sistema |
| .proibidas | `.proibidas` | Lista as palavras proibidas | administrador | admin |
| .proibir | `.proibir <palavra>` | Adiciona uma palavra à lista de palavras proibidas | administrador | admin |
| .regras | `.regras` | Mostra as regras do grupo | membro | admin |
| .renomear | `.renomear <novo nome>` | Muda o nome do grupo | administrador | admin |
| .resetadv | `.resetadv @usuário` | Zera as advertências de um participante (aliases: limparadv) | administrador | admin |
| .setbemvindo | `.setbemvindo <texto>` | Define a mensagem de boas-vindas ({usuario} {grupo} {regras}) | administrador | admin |
| .setdesc | `.setdesc <texto>` | Define a descrição do grupo | administrador | admin |
| .setdespedida | `.setdespedida <texto>` | Define a mensagem de despedida ({usuario} {grupo}) | administrador | admin |
| .setregras | `.setregras <texto>` | Define as regras do grupo | administrador | admin |

## 🎉 Diversão (14)

| Comando | Uso | Descrição | Permissão | Módulo |
|---|---|---|---|---|
| .bola8 | `.bola8 <pergunta>` | Bola 8 mágica: responda sim/não (aliases: 8ball) | membro | diversao |
| .casal | `.casal` | Escolhe aleatoriamente dois participantes ativos (só diversão) | membro | diversao |
| .curiosidade | `.curiosidade` | Mostra uma curiosidade interessante (aliases: sabia) | membro | diversao |
| .dado | `.dado [lados] [quantidade]` | Rola um dado (padrão 6 lados, máx. 1000) (aliases: d) | membro | diversao |
| .desafio | `.desafio` | Mostra o desafio seguro do dia (aliases: desafiododia) | membro | diversao |
| .desafiofeito | `.desafiofeito` | Resgata a recompensa do desafio do dia (1x por dia) | membro | diversao |
| .escolher | `.escolher a | b | c` | Escolhe uma opção entre várias separadas por | ou vírgula | membro | diversao |
| .frase | `.frase` | Envia uma frase de incentivo (aliases: motivacao) | membro | diversao |
| .moeda | `.moeda` | Joga uma moeda (cara ou coroa) (aliases: caraoucoroa) | membro | diversao |
| .piada | `.piada` | Conta uma piada (aliases: joke) | membro | diversao |
| .porcentagem | `.porcentagem <assunto>` | Mede aleatoriamente uma 'porcentagem' divertida (aliases: medidor) | membro | diversao |
| .roleta | `.roleta a | b | c` | Roleta virtual de entretenimento: gira entre as opções | membro | diversao |
| .sorteio | `.sorteio [quantidade] [nome1, nome2, ...]` | Sorteio transparente entre os participantes ativos ou uma lista | membro | diversao |
| .sortenumero | `.sortenumero <mín> <máx>` | Sorteia um número entre dois valores | membro | diversao |

## 🎮 Jogos (10)

| Comando | Uso | Descrição | Permissão | Módulo |
|---|---|---|---|---|
| .adivinhar | `.adivinhar [máximo 10-1000]` | Inicia o jogo de adivinhar o número secreto | membro | jogos |
| .charada | `.charada` | Propõe uma charada ou enigma (aliases: enigma) | membro | jogos |
| .chute | `.chute <número>` | Dá um palpite no jogo de adivinhação | membro | jogos |
| .jogar | `.jogar <1-9>` | Faz uma jogada no jogo da velha | membro | jogos |
| .ppt | `.ppt pedra|papel|tesoura` | Pedra, papel e tesoura contra o bot (aliases: pedrapapeltesoura) | membro | jogos |
| .quiz | `.quiz` | Pergunta de conhecimentos gerais (todos podem responder) (aliases: pergunta) | membro | jogos |
| .rc | `.rc <resposta>` | Responde à charada atual | membro | jogos |
| .resp | `.resp a|b|c|d` | Responde ao quiz atual (aliases: r) | membro | jogos |
| .revelar | `.revelar` | Revela a resposta da charada atual | membro | jogos |
| .velha | `.velha @usuário | cancelar` | Jogo da velha multiplayer: desafie alguém | membro | jogos |

## 🧠 Inteligência Artificial (13)

| Comando | Uso | Descrição | Permissão | Módulo |
|---|---|---|---|---|
| .ativaesperto | `.ativaesperto` | [admin] Liga o modo esperto: a IA responde tudo no grupo | administrador | ia |
| .codigo | `.codigo <dúvida>` | A IA ajuda com programação (aliases: code, programar) | membro | ia |
| .corrigir | `.corrigir <texto>` | A IA corrige ortografia e gramática | membro | ia |
| .desligaresperto | `.desligaresperto` | [admin] Desliga o modo esperto (aliases: desativaesperto) | administrador | ia |
| .esperto | `.esperto` | [admin] Mostra o estado do modo esperto | administrador | ia |
| .espertodm | `.espertodm on|off` | [dono] Liga/desliga a IA nas conversas diretas (privado) com qualquer pessoa | dono | ia |
| .espertoproativo | `.espertoproativo on|off` | [admin] Liga/desliga as mensagens espontâneas do modo esperto | administrador | ia |
| .explicar | `.explicar <assunto>` | A IA explica um assunto de forma simples | membro | ia |
| .historia | `.historia <tema>` | A IA cria uma história original curta (aliases: conto) | membro | ia |
| .ia | `.ia <pergunta>` | Conversa com a IA (lembra das últimas mensagens) (aliases: ai, nicolas, gpt) | membro | ia |
| .iareset | `.iareset` | Apaga o contexto da sua conversa com a IA | membro | ia |
| .ideias | `.ideias <tema>` | A IA sugere ideias sobre um tema | membro | ia |
| .resumir | `.resumir <texto>` | A IA resume um texto | membro | ia |

## 🧰 Utilidades (17)

| Comando | Uso | Descrição | Permissão | Módulo |
|---|---|---|---|---|
| .calcular | `.calcular <expressão>` | Calculadora segura (+ - * / ^ % parênteses, sqrt, sin, log, fatorial...) (aliases: calc, calcula) | membro | utilidades |
| .converter | `.converter <valor> <de> <para>` | Converte unidades (comprimento, massa, volume, tempo, dados, temperatura...) (aliases: conv) | membro | utilidades |
| .desconto | `.desconto <preço> <% de desconto>` | Calcula o preço com desconto | membro | matematica |
| .equipes | `.equipes <nº de equipes> <nome1> <nome2> ...` | Sorteia nomes em equipes | membro | matematica |
| .fibonacci | `.fibonacci <quantidade até 60>` | Primeiros termos da sequência de Fibonacci (aliases: fib) | membro | matematica |
| .gorjeta | `.gorjeta <valor> [%] [pessoas]` | Calcula a gorjeta e divide a conta | membro | matematica |
| .imc | `.imc <peso kg> <altura m>` | Calcula o índice de massa corporal | membro | matematica |
| .inverter | `.inverter <texto>` | Inverte um texto | membro | matematica |
| .mdc | `.mdc <n1> <n2> [...]` | Máximo divisor comum de números | membro | matematica |
| .mmc | `.mmc <n1> <n2> [...]` | Mínimo múltiplo comum de números | membro | matematica |
| .palindromo | `.palindromo <texto>` | Diz se uma frase é palíndromo | membro | matematica |
| .primo | `.primo <número>` | Diz se um número é primo (e o fatora) | membro | matematica |
| .romano | `.romano <valor>` | Converte número (1-3999) em romano ou romano em número | membro | matematica |
| .tabuada | `.tabuada <número>` | Mostra a tabuada de um número | membro | matematica |
| .texto | `.texto <estilo> <texto>` | Formata texto: negrito, mono, bolhas, largo, inverter, espacado, maiusculas... (aliases: fonte) | membro | utilidades |
| .traduzir | `.traduzir <idioma> <texto>` | Traduz um texto (LibreTranslate ou IA, se configurados) (aliases: tr, translate) | membro | utilidades |
| .unidades | `.unidades` | Lista as unidades suportadas pelo conversor | membro | utilidades |

## 💰 Economia virtual (11)

| Comando | Uso | Descrição | Permissão | Módulo |
|---|---|---|---|---|
| .apostar | `.apostar <valor>` | Aposta moedas VIRTUAIS (45% de chance de dobrar). Só diversão | membro | economia |
| .carteira | `.carteira [@usuário]` | Mostra seu saldo de moedas virtuais (aliases: saldo, bal) | membro | economia |
| .comprar | `.comprar <item>` | Compra um item da loja virtual | membro | economia |
| .diario | `.diario` | Resgata a recompensa diária (1x por dia) (aliases: daily) | membro | economia |
| .inventario | `.inventario [@usuário]` | Mostra seus itens comprados (aliases: inv, mochila) | membro | economia |
| .loja | `.loja` | Mostra os itens da loja virtual (aliases: shop) | membro | economia |
| .missoes | `.missoes` | Mostra suas missões diárias (aliases: quests) | membro | economia |
| .resgatar | `.resgatar` | Resgata as missões diárias concluídas | membro | economia |
| .topricos | `.topricos` | Ranking de riqueza virtual do grupo (aliases: ricos) | membro | economia |
| .trabalhar | `.trabalhar` | Faz um 'trabalho' virtual e ganha moedas (a cada 1 hora) (aliases: work) | membro | economia |
| .transferir | `.transferir @usuário <valor>` | Transfere moedas virtuais para outro participante (aliases: pix, dar) | membro | economia |

## 👤 Perfil e ranking (5)

| Comando | Uso | Descrição | Permissão | Módulo |
|---|---|---|---|---|
| .ajustarperfis | `.ajustarperfis` | [dono] Aplica neste grupo o XP e as moedas configurados para os dois perfis iniciais | dono | perfil |
| .medalhas | `.medalhas [@usuário]` | Lista suas conquistas desbloqueadas (aliases: conquistas) | membro | perfil |
| .nivel | `.nivel` | Mostra seu nível e quanto falta para o próximo (aliases: level, xp) | membro | perfil |
| .perfil | `.perfil [@usuário]` | Mostra o perfil de um participante (aliases: profile) | membro | perfil |
| .rank | `.rank [xp|msgs|ricos]` | Ranking do grupo por xp, msgs ou ricos (aliases: ranking, top) | membro | perfil |

## 🎨 Personalização (2)

| Comando | Uso | Descrição | Permissão | Módulo |
|---|---|---|---|---|
| .setbio | `.setbio <texto>` | Define a bio do seu perfil (até 120 caracteres) | membro | perfil |
| .titulo | `.titulo <título>|remover` | Escolhe um título comprado na loja para o perfil | membro | perfil |

## ℹ️ Informações (12)

| Comando | Uso | Descrição | Permissão | Módulo |
|---|---|---|---|---|
| .admins | `.admins` | Lista os administradores do grupo | membro | informacoes |
| .cep | `.cep <cep>` | Consulta um CEP brasileiro (ViaCEP) | membro | informacoes |
| .data | `.data` | Mostra a data de hoje por extenso | membro | informacoes |
| .diasate | `.diasate <DD/MM[/AAAA]>` | Quantos dias faltam para uma data | membro | informacoes |
| .dicionario | `.dicionario <palavra>` | Significado de uma palavra (dictionaryapi.dev) (aliases: significado, dic) | membro | informacoes |
| .grupo | `.grupo` | Informações do grupo atual (aliases: infogrupo) | membro | informacoes |
| .hora | `.hora [fuso]` | Mostra a hora atual (Brasília ou outro fuso, ex.: +9) (aliases: horas) | membro | informacoes |
| .idade | `.idade <DD/MM/AAAA>` | Calcula a idade a partir da data de nascimento | membro | informacoes |
| .signo | `.signo <DD/MM>` | Descobre o signo pela data de nascimento | membro | informacoes |
| .tempo | `.tempo <cidade>` | Previsão do tempo para uma cidade (serviço Open-Meteo) (aliases: clima, previsao) | membro | informacoes |
| .uptime | `.uptime` | Há quanto tempo o bot está online | membro | informacoes |
| .wiki | `.wiki <assunto>` | Resumo da Wikipédia em português (aliases: pesquisar, buscaweb) | membro | informacoes |

## 🖼️ Mídia (2)

| Comando | Uso | Descrição | Permissão | Módulo |
|---|---|---|---|---|
| .cor | `.cor <#rrggbb | r g b>` | Converte cor HEX <-> RGB | membro | dev |
| .qr | `.qr <texto>` | Gera um QR Code a partir de um texto ou link (gerado localmente) | membro | utilidades |

## 📝 Produtividade (8)

| Comando | Uso | Descrição | Permissão | Módulo |
|---|---|---|---|---|
| .cronometro | `.cronometro iniciar|parcial|parar` | Cronômetro pessoal: iniciar, parcial ou parar | membro | produtividade |
| .feito | `.feito <número>` | Marca uma tarefa como concluída | membro | produtividade |
| .lembrete | `.lembrete <tempo> <texto>` | Cria um lembrete (30s, 10m, 2h, 1d) (aliases: lembrar, remind) | membro | produtividade |
| .lembretes | `.lembretes` | Lista seus lembretes pendentes neste chat | membro | produtividade |
| .tarefa | `.tarefa <texto>` | Adiciona uma tarefa à sua lista (aliases: todo) | membro | produtividade |
| .tarefadel | `.tarefadel <número>` | Remove uma tarefa da lista | membro | produtividade |
| .tarefas | `.tarefas` | Mostra sua lista de tarefas (aliases: lista) | membro | produtividade |
| .temporizador | `.temporizador <tempo>` | Inicia um temporizador (30s, 10m, 1h) (aliases: timer) | membro | produtividade |

## 🔐 Segurança (3)

| Comando | Uso | Descrição | Permissão | Módulo |
|---|---|---|---|---|
| .forcasenha | `.forcasenha <senha>` | Avalia a força de uma senha localmente (não use senhas reais em grupos) (aliases: testarsenha) | membro | seguranca |
| .senha | `.senha [tamanho 8-64] [simples]` | Gera uma senha forte aleatória (use no privado!) (aliases: gerarsenha, password) | membro | seguranca |
| .token | `.token [bytes 4-64]` | Gera um token hexadecimal aleatório | membro | seguranca |

## 💻 Desenvolvedores (10)

| Comando | Uso | Descrição | Permissão | Módulo |
|---|---|---|---|---|
| .base64 | `.base64 enc|dec <texto>` | Codifica ou decodifica Base64 (aliases: b64) | membro | dev |
| .binario | `.binario <número> [bin|hex|dec]` | Converte número decimal em binário/hexadecimal e vice-versa (aliases: bin) | membro | dev |
| .contar | `.contar <texto>` | Conta caracteres, palavras e linhas de um texto (aliases: count) | membro | dev |
| .hash | `.hash <algoritmo> <texto>` | Calcula hash (md5, sha1, sha256, sha512) de um texto | membro | dev |
| .json | `.json <json>` | Valida e formata um JSON (aliases: jsonformat) | membro | dev |
| .slug | `.slug <texto>` | Transforma um texto em slug de URL | membro | dev |
| .timestamp | `.timestamp [número|AAAA-MM-DD]` | Converte timestamp Unix <-> data (UTC); sem argumento mostra o atual | membro | dev |
| .urlcodificar | `.urlcodificar <texto>` | Codifica um texto para URL (aliases: urlenc) | membro | dev |
| .urldecodificar | `.urldecodificar <texto>` | Decodifica um texto de URL (aliases: urldec) | membro | dev |
| .uuid | `.uuid` | Gera um UUID v4 | membro | dev |
