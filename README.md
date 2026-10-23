# Robô Nicolas 🤖

Bot de grupos para WhatsApp em português brasileiro: administração, anti-link/anti-flood/anti-fake, advertências,
jogos, economia virtual (só diversão), IA opcional, ferramentas e muito mais. Roda no **Android pelo Termux, sem root**.

> ⚠️ **Aviso importante.** A conexão com o WhatsApp usa o **Baileys**, uma biblioteca **não oficial**. O WhatsApp pode
> restringir ou banir contas que usam bots. **Use um número dedicado ao bot**, nunca o seu número principal.

## Como funciona

```
WhatsApp  <──Baileys──>  ponte (Node.js, pasta bridge/)  <──HTTP local──>  bot (Python, pasta nicolas/)  ──>  SQLite (data/)
```

* **Ponte (Node):** conecta ao WhatsApp, guarda a sessão em `auth/` e repassa as mensagens ao bot.
* **Bot (Python, só biblioteca padrão):** comandos, permissões, moderação, jogos, economia e banco de dados.
* Os dois sobem juntos com um único comando (`bash start.sh`).

## Instalação no Termux (passo a passo)

Use o Termux baixado do **F-Droid** ou do **GitHub** (a versão da Play Store está desatualizada).

```bash
pkg update && pkg upgrade -y
pkg install -y nodejs-lts python git unzip ffmpeg

# se o ZIP estiver em Downloads, libere o acesso (uma vez):
termux-setup-storage

# descompacte para a pasta privada do Termux (não rode dentro de /sdcard):
unzip -o /sdcard/Download/Robo-Nicolas-atualizado.zip -d ~
cd ~/Robo-Nicolas

bash install.sh     # instala e verifica tudo (leva alguns minutos)
bash start.sh       # inicia o bot
```

> **Não rode de dentro de `/sdcard` ou `Download`.** O armazenamento compartilhado do Android não aceita links
> simbólicos nem o bloqueio de arquivos do SQLite. Sempre copie a pasta para `~` (o `install.sh` avisa se esquecer).

Atalho no estilo dos bots em Node: `npm run setup` equivale a `bash install.sh`, e `npm start` equivale a `bash start.sh`.

## Usando o seu próprio número (só tem um celular)

Se você conectou o bot no **seu** WhatsApp, o bot é o seu número: ele já está nos seus grupos, não precisa adicionar
ninguém. Nesse modo:

* Os comandos que **você mesmo** digita em um grupo funcionam (ex.: `.ping`, `/ativaesperto`), desde que o seu número
  esteja em `OWNER_IDS` no `.env`. Também funcionam na conversa "Você" (mensagem para si mesmo).
* Com `/ativaesperto` ligado naquele grupo, suas mensagens comuns também recebem resposta da IA, sem precisar mencionar o bot.
  Com o modo desligado, mensagens comuns não acionam a IA.
* Comandos digitados em conversa privada com outra pessoa são ignorados.
* O bot só consegue apagar mensagens e remover pessoas nos grupos em que **você é administrador**.
* Atenção: automações no seu número principal aumentam o risco de o WhatsApp restringir a conta. O ideal é um chip separado.

## Conectando ao WhatsApp (primeira vez)

Ao rodar `bash start.sh` pela primeira vez, o bot pergunta:

1. **Como conectar** — `1` código de pareamento (recomendado no celular) ou `2` QR Code (precisa de **outro** aparelho
   para escanear, pois não dá para escanear a tela do próprio celular).
2. **Número do WhatsApp do bot** com DDI e DDD (ex.: `5511999999999`). Ele confirma o número antes de continuar.

Aparece um código assim:

```
════════════════════════════════════════════
  CÓDIGO DE PAREAMENTO:  ABCD-EFGH
════════════════════════════════════════════
```

No WhatsApp **desse número** (pode ser o mesmo celular): **Configurações → Aparelhos conectados → Conectar um aparelho →
Conectar com número de telefone** e digite o código. Quando o WhatsApp confirmar, o terminal mostra
`✅ Autenticado e conectado ao WhatsApp` — essa mensagem só aparece depois da confirmação real.
Se o código expirar, o bot gera outro automaticamente.

Depois adicione o número do bot a um grupo e **promova-o a administrador** (necessário para remover mensagens/pessoas).
Teste com `.ping` e `.menu`.

### Sessão e reinícios

* A sessão fica em `auth/`. **Reiniciar o bot não pede novo pareamento** enquanto a sessão for válida.
* `Ctrl+C` encerra sem fazer logout (a sessão é preservada).
* Se o WhatsApp invalidar a sessão (aparelho removido, sessão corrompida), o bot **apaga as credenciais antigas** e pede
  nova autenticação (máx. 3 vezes por hora, para não parecer abuso).
* Para trocar de número: pare o bot, apague a pasta `auth/` e rode `bash start.sh` de novo.
* **Nunca compartilhe** `auth/` nem `.env`: quem tiver `auth/` controla a conta do bot. O ZIP não os inclui.

## Configuração (`.env`)

O `install.sh` cria o `.env` e gera o `BRIDGE_TOKEN` sozinho. Edite com `nano .env`.

| Variável | Para quê |
|---|---|
| `OWNER_IDS` | Seu número (só dígitos, com DDI). Donos têm todas as permissões. Vários: separe por vírgula. |
| `BOT_PREFIX` | Prefixo dos comandos (padrão `.`). Cada grupo pode mudar com `.prefixo`. |
| `AUTH_METHOD` / `PAIRING_PHONE` | Opcional: pular as perguntas de conexão (`code` ou `qr` e o número). |
| `AI_PROVIDER`, `AI_MODEL`, `AI_API_KEY` | Escolhem o provedor e o modelo: OpenRouter, OpenAI, Groq, DeepSeek, Together, Anthropic, Gemini ou uma API compatível. Serviços locais podem dispensar chave; configure com `python3 -m nicolas ia-local`. |
| `TRANSLATE_URL` | Servidor LibreTranslate para `.traduzir` (ou use a IA). |
| `RATE_LIMIT_*`, `FLOOD_*`, `MAX_WARNS` | Limites de uso, anti-flood e advertências. |
| `ANTIFAKE_PREFIXES` | DDIs aceitos pelo anti-fake (padrão `55`). |

Depois de editar, reinicie (`Ctrl+C` e `bash start.sh`).

## Modo esperto (IA que responde tudo no grupo)

Quando um **administrador do grupo** manda `/ativaesperto`, o bot passa a responder as mensagens do grupo com o provedor configurado (`AI_PROVIDER` e `AI_MODEL`)
e, se o grupo ficar parado por 3 horas (entre 8h e 22h), puxa assunto sozinho. `/desligaresperto` desliga.

| Comando (admin) | O que faz |
|---|---|
| `/ativaesperto` | Liga o modo esperto neste grupo |
| `/desligaresperto` | Desliga |
| `/esperto` | Mostra o estado |
| `/espertoproativo on\|off` | Liga/desliga as mensagens espontâneas |

Funciona com `/` ou com o prefixo normal (`.ativaesperto`). Cada grupo liga e desliga o seu.

**Recursos por provedor:** texto funciona com os provedores listados abaixo; voz/imagem dependem do modelo e das integrações específicas.

| Poder | Como funciona |
|---|---|
| 🎧 **Ouve áudios** | Mensagens de voz no grupo são enviadas à IA, que entende e responde. |
| 🗣️ **Fala em áudio** | Se alguém pedir "manda um áudio…", ela responde em voz. Se a pessoa mandou áudio, a resposta também vem em voz (`ESPERTO_RESPONDE_AUDIO=0` desliga isso). Para sair como **mensagem de voz** de verdade, o `ffmpeg` precisa estar instalado (`pkg install ffmpeg`; o `install.sh` tenta). Sem ele, o áudio vai como arquivo `.wav`. |
| 🎨 **Gera imagens** | "Desenha um gato astronauta" → a IA cria e envia a imagem. |
| 👀 **Vê imagens** | Fotos enviadas ao grupo são analisadas e comentadas. |

Áudios e imagens só são baixados em conversas onde o modo está ligado. Provedores compatíveis com OpenAI, incluindo OpenRouter, são usados para respostas de texto. Transcrição de áudio requer um modelo/serviço STT compatível configurado; geração de voz e imagens segue a integração Gemini atual e não é garantida por trocar apenas o provedor de texto. Teste a conexão com `python3 -m nicolas aitest`. Veja `docs/PROVEDORES-IA.md` para configurar qualquer modelo disponível na sua conta.

**Conversas diretas (privado):** o dono liga com `/espertodm on` (e desliga com `/espertodm off`). Aí o bot responde
automaticamente quem te chamar no privado, **como se fosse você**. Se você mesmo escrever na conversa, a IA fica quieta
por 10 minutos (`ESPERTO_DM_PAUSA_MIN`). Vem **desligado** por padrão.

**Comunidades:** os grupos de uma comunidade são grupos normais para o bot; basta ele estar em cada um. (Não testado em
comunidades reais.)

**Configurar OpenRouter ou outro provedor no celular** (a chave não vai no ZIP e não aparece na tela):

```bash
cd ~/Robo-Nicolas
python3 -m nicolas ia --provider openrouter --model "ID-EXATO-DO-MODELO"
python3 -m nicolas aitest
python3 -m nicolas modelos
```

O comando pede a chave de forma oculta e salva a configuração no `.env`. Substitua `ID-EXATO-DO-MODELO` pelo identificador copiado do catálogo do OpenRouter (por exemplo, um modelo `provedor/modelo` que esteja disponível para sua conta). Você pode trocar de modelo repetindo o comando. Para outros provedores, use `--provider groq`, `--provider openai`, `--provider deepseek`, `--provider together` ou `--provider anthropic`. Para uma API personalizada compatível com OpenAI, use `--provider openai-compatible --base-url "https://seu-servidor/v1"`.

A configuração de IA é independente do WhatsApp: depois de testar, inicie/reinicie o bot com `bash start.sh`. O modo `/ativaesperto` usará o provedor/modelo definido em `AI_PROVIDER` e `AI_MODEL`.

**Limitação de multimídia:** trocar para OpenRouter libera os modelos de texto disponíveis nele, mas não ativa automaticamente geração de voz, geração de imagem ou reconhecimento de áudio. Esses recursos dependem de endpoints/modelos compatíveis e da implementação específica no bot.

**Usar um modelo local/aberto sem chave de API:** rode `python3 -m nicolas ia-local`, escolha Ollama, Docker Model Runner ou outra API compatível, informe a URL base e o nome exato do modelo. A chave pode ficar vazia quando o servidor não exigir autenticação. O comando salva a configuração em `.env` e testa a conexão.

Exemplo para um Docker Model Runner no mesmo ambiente:

```bash
python3 -m nicolas ia-local --tipo docker --url http://127.0.0.1:12434/engines/v1 --model ai/llama3.2
```

Se o Docker Model Runner estiver num computador da mesma rede Wi-Fi, informe o IP privado desse PC no lugar de `127.0.0.1` e use `--permitir-http-rede` somente se confiar nessa rede. Ative o acesso TCP/firewall no computador conforme a documentação do Docker. O endpoint local `localhost` do PC não é o `localhost` do celular.

**Atenção ao DeepSeek-V4.1-Flash-1017:** o modelo de referência é de aproximadamente 763 bilhões de parâmetros e exige armazenamento/memória de classe servidor; ele não é uma opção prática para executar no Galaxy A50. O bot pode conectar-se a um servidor que já esteja rodando esse modelo, mas o comando não torna o celular capaz de executá-lo.

Cuidados:

* Enquanto o modo estiver ligado, as **mensagens recentes do grupo são enviadas ao Google**. Avise o grupo.
* O bot responde no máximo `ESPERTO_POR_MINUTO` (padrão 6) vezes por minuto em cada grupo, para não estourar a cota
  da API nem virar spam. Mensagens além do limite são ignoradas.
* Se a IA estiver fora do ar, a chave for recusada ou a cota acabar, o bot envia um aviso curto no máximo uma vez por conversa por minuto e registra um motivo sem imprimir a chave em `logs/bot.log`.
* **Chave Gemini:** gere/seleciona uma chave recente no [Google AI Studio](https://aistudio.google.com/apikey). A documentação do Google mudou em 2026; chaves padrão antigas e irrestritas podem ser recusadas. Este projeto usa o cabeçalho de chave da API Gemini; valide a chave com `python3 -m nicolas aitest`. Se ocorrer 401/403, confira o tipo/restrições da chave e a habilitação da API no projeto Google Cloud associado.
* Nunca cole a chave em grupos ou prints. Se ela já apareceu em algum chat, gere uma nova e apague a antiga.

## Níveis, XP, moedas e ranking inicial

O ranking usa o XP persistido em `data/nicolas.db` e desempata de maneira estável pelo identificador do usuário. A fórmula do projeto é `nível = floor(sqrt(XP / 100)) + 1`, portanto XP e nível não podem ser configurados separadamente sem contradição: para nível 10 são necessários 8.100 XP; para nível 9, 6.400 XP. Assim, a configuração inicial garante ao perfil terminado em **6369** nível 10, pelo menos 1.279 moedas e 8.100 XP, e ao perfil terminado em **3183** nível 9, pelo menos 1.345 moedas e 6.400 XP. Os valores solicitados originalmente de 1.460/1.209 XP corresponderiam ao nível 4 nessa fórmula.

A inicialização é idempotente: não reaplica as moedas a cada reinício, não reduz saldos/XP maiores e preserva os demais usuários. Números com ou sem o nono dígito brasileiro são reconhecidos para evitar uma conta duplicada. Antes de alterar um banco existente, o bot cria um backup em `data/backups/`. O XP do perfil segue o escopo por grupo já usado pelo sistema de ranking; o piso é aplicado nos registros desses perfis e nos novos registros de grupo.

## Desligar e desconectar o bot

| O que você quer | Como |
|---|---|
| Parar o bot (a sessão do WhatsApp fica salva) | No terminal onde ele roda: **Ctrl+C**. No Termux: toque em **CTRL** na barra de teclas extra e depois na letra **C** (ou volume-baixo + C). |
| Parar de outra sessão do Termux | `cd ~/Robo-Nicolas && bash stop.sh` |
| Parar pelo WhatsApp (só o dono) | `.desligarbot` (ou `/desligarbot`) |
| Sair da conta do WhatsApp e apagar a sessão (só o dono) | `.desconectar` pede confirmação; confirme com `.desconectar confirmar`. Depois será preciso parear de novo. |

> **Atenção:** enquanto o bot está rodando, o terminal está "ocupado" com ele. Tudo que você digitar ou colar ali vai
> para o bot, não para o Termux. Para voltar ao terminal normal, pare o bot primeiro (Ctrl+C) ou abra **outra sessão**
> do Termux (deslize da borda esquerda da tela → **New session**).

## Deixando o bot ligado 24 horas

O bot foi feito para **nunca parar sozinho**: se a conexão cair, ele reconecta; se a ponte ou o bot em Python travarem,
são reiniciados; erros inesperados são registrados e ignorados. Ele só para com `Ctrl+C`, `bash stop.sh` ou `.desligarbot`.

**A parte que o programa não controla é o Android.** O sistema mata apps em segundo plano para poupar bateria. Para o
bot sobreviver:

1. Rode em segundo plano: `bash start-bg.sh` (precisa ter feito o login uma vez com `bash start.sh`). Pode fechar o
   Termux. Acompanhe com `tail -f logs/supervisor.log`; pare com `bash stop.sh`.
2. **Android → Configurações → Apps → Termux → Bateria → Sem restrições** (o nome varia por marca; em Samsung:
   "Nunca em suspensão" / tirar o Termux da lista de apps em suspensão).
3. Deixe a notificação do Termux fixa e o **wake-lock** ativo (o script já ativa).
4. Em Wi-Fi: "manter Wi-Fi ligado durante a suspensão: sempre". Se puder, deixe o celular carregando.
5. Para ligar sozinho depois de reiniciar o celular: instale **Termux:Boot** (F-Droid), abra-o uma vez e rode
   `bash boot-setup.sh`.

Mesmo assim, alguns celulares (Xiaomi, Huawei, Samsung mais antigos) são muito agressivos e podem encerrar o Termux
depois de horas. Nesse caso, o bot volta quando você abrir o Termux (ou no próximo boot, com o Termux:Boot).
**Não dá para garantir 24/7 num celular**; para isso o ideal é um servidor (VPS) ou um aparelho dedicado ligado na tomada.

## Quem é o dono

O número que você digitou no `install.sh` (e `OWNER_IDS`) é o dono. O bot também aceita o número **com ou sem o 9
brasileiro** (ex.: `5581988616931` e `558188616931`) e considera a **própria conta conectada** como dona, então os
comandos que você digita no seu WhatsApp sempre são de dono. Para remover pessoas e apagar mensagens, o número do bot
precisa ser **administrador do grupo** (o WhatsApp só deixa admins fazerem isso).

## Comandos

Lista completa, gerada do registro real: [`docs/COMANDOS.md`](docs/COMANDOS.md). Use `.menu` (paginado), `.ajuda <comando>`
e `.comandos <busca>` dentro do WhatsApp. Principais: `.menu .ajuda .comandos .ping .status .info .dono .prefixo .ativar
.desativar .rank .perfil .regras .sorteio .ia .calcular .traduzir .tempo`.

**Quantidade real nesta versão:** 155 comandos, 96 aliases e 220 atalhos de conversão de unidades (ex.: `.km-mi 10`),
ou seja, **471 nomes** invocáveis. A meta de 10.000 **ainda não foi atingida** — veja `docs/EXPANSAO.md`.
O número exato do seu bot aparece em `.menu` e `.info`.

## O que foi testado e o que depende de você

| Item | Situação |
|---|---|
| Suíte Python (202 testes automatizados, incluindo comandos, banco, IA simulada e configuração inicial) | ✅ testado |
| Banco SQLite, migrações, economia (sem duplicar recompensa nem saldo negativo), permissões, anti-link/flood/fake | ✅ testado |
| Gateway HTTP com token | ✅ testado |
| Lógica da ponte (telefone, sessão, desconexões, envio, ações) — 21 testes | ✅ testado |
| Fluxo de pareamento/reconexão do `bridge/index.js` | ✅ testado com um **Baileys simulado** |
| **Conexão real com o WhatsApp e instalação real do Baileys no Termux** | ⚠️ **não testado** — só você consegue confirmar no celular |
| IA, tradução, clima, dicionário, Wikipédia, CEP | 🌐 dependem de internet/API; testados com respostas simuladas |
| `.qr` | 📦 precisa do pacote opcional `segno` (o `install.sh` tenta instalar) |

### Versões

A ponte usa `@whiskeysockets/baileys ~6.7.18`, `pino ^9.5.0` e `qrcode-terminal 0.12.0` (Node 20+). Não foi possível
consultar o registro do npm no ambiente em que o projeto foi montado, então **a versão exata mais recente do Baileys
não foi confirmada**. Se a instalação reclamar de versão, tente `BAILEYS_SPEC=latest bash install.sh`. O `qrcode-terminal`
não recebe atualizações há anos, mas é um módulo pequeno, em JavaScript puro, usado só no modo QR.

## Problemas comuns

| Sintoma | O que fazer |
|---|---|
| `install.sh` falha no `npm install` | Confira a internet; `pkg upgrade`; `npm cache clean --force`; rode de novo. Se citar `node-gyp`/`make`: `pkg install -y build-essential python`. |
| "Versão inexistente do Baileys" | `BAILEYS_SPEC=latest bash install.sh` |
| Código de pareamento não é aceito | Confirme que digitou o número do WhatsApp **que vai ser o bot**, com DDI. Peça outro reiniciando (`Ctrl+C`, `bash start.sh`) ou use `AUTH_METHOD=qr`. |
| Bot conecta mas não remove mensagens | Promova o número do bot a **administrador do grupo**. |
| `.ping` não responde | Veja `logs/bot.log`; confirme o prefixo (`.prefixo`); o módulo/comando pode estar desativado no grupo (`.modulos`). |
| "Conexão substituída" (código 440) | A mesma sessão foi aberta em outro lugar. Rode o bot em um só lugar. |
| `Address already in use` no `logs/bot.log` ou o bot ignora comandos novos | Sobrou um bot antigo rodando em segundo plano. Rode `bash stop.sh` (ele encerra processos soltos) e depois `bash start.sh`. |
| Reconecta sem parar | Veja a mensagem de erro; internet instável; ou o WhatsApp invalidou a sessão (apague `auth/`). |

## Testes

```bash
python3 -m nicolas test                    # 202 testes Python
cd bridge && node --test test/lib.test.js  # testes da ponte
python3 -m nicolas console                 # conversa de teste no terminal, sem WhatsApp
python3 -m nicolas commands                # lista os comandos registrados
python3 -m nicolas docs                    # regenera docs/COMANDOS.md
```

## Estrutura

```
install.sh  start.sh  start-bg.sh  stop.sh  boot-setup.sh  .env.example  README.md
bridge/     index.js (WhatsApp)  lib.js  test/
nicolas/    dispatcher.py  registry.py  db.py  config.py  security.py  server.py ...
nicolas/plugins/   um arquivo por módulo (admin, jogos, economia, ia, utilidades, ...)
tests/      testes do bot
docs/       COMANDOS.md  EXPANSAO.md
```

Para criar um comando novo, adicione uma função em `nicolas/plugins/<modulo>.py` com `@reg.command(...)`: o registro,
o menu, a ajuda, a documentação e os testes de execução passam a enxergá-lo automaticamente.

## Correção de progressão para bancos antigos

A correção versiona o marcador do XP para reparar cadastros iniciados por uma versão anterior com XP insuficiente para o nível solicitado. O pacote eleva XP apenas até o piso necessário, nunca diminui XP maior e não repõe moedas já gastas. Durante `bash update.sh`, o comando `python3 -m nicolas seed-progress` roda antes da verificação e guarda backup do banco se houver alteração. XP é individual por grupo; um número sem registro naquele grupo começa com o nível configurado quando interage pela primeira vez.

## Novidades (atualização anterior)

- **Modelo errado (404)?** `python3 -m nicolas modelos` lista os modelos da sua chave e o `ia`/`aitest` escolhem um sozinhos.
- **Várias IAs:** `python3 -m nicolas ia` aceita chave do Groq (`gsk_...`, console.groq.com/keys), Gemini, OpenAI, OpenRouter,
  DeepSeek, Anthropic etc. e troca a chave sem mostrar na tela. `python3 -m nicolas ia-local` configura endpoints auto-hospedados/compatíveis sem chave obrigatória. `python3 -m nicolas ia --reserva` guarda uma IA reserva usada
  quando a principal dá limite (429) ou erro. Com Groq/OpenAI a voz é transcrita (Whisper); imagem/voz gerada só no Gemini.
  Os nomes de modelo padrão mudam com o tempo: se der "modelo não encontrado", use `python3 -m nicolas setenv AI_MODEL <nome>`.
- **"Ei bot, organize o grupo":** com `/ativaesperto` ligado, um admin que chama o bot ("Ei bot", "Nicolas,", ou @bot) tem o
  pedido transformado em comandos de administração (descrição, regras, boas-vindas, antilink/antiflood, fechar/abrir, renomear,
  advertir/silenciar/expulsar quem ele marcar). Roda com as permissões do admin, máx. 6 comandos, só lista permitida; o bot
  precisa ser admin do grupo para mudar nome/descrição/fechar. Promover/rebaixar admins e sair do grupo **não** são feitos pela IA.
- **Conversas privadas:** o dono escreve `/ativaesperto` na conversa com a pessoa para a IA responder ali; `/espertodm on` liga
  para todas. `/esperto` mostra contadores e o último erro. Sem a IA configurada ou com o modo desligado, o log diz o motivo.
- **Dados salvos:** lembretes, XP e configurações ficam em `data/nicolas.db` (backup automático em `data/backups/`,
  `bash backup.sh`). **Para atualizar sem perder nada use `bash update.sh Robo-Nicolas.zip`** — nunca apague a pasta `data/`.
- **24h:** veja `deploy/LEIA-ME.md`. Se o celular desligar ou acabar a bateria, o bot para; para ficar sempre ativo rode-o em
  um servidor/PC/celular sempre ligado.

## Ficar ligado 24h (leia isto)

Se o celular **desliga, reinicia ou a bateria acaba, o bot para** — nenhum programa consegue rodar com o aparelho desligado.
O que dá para fazer para ele voltar sozinho e ficar o máximo possível ligado:

1. Instale os apps **Termux:Boot** e **Termux:API** (mesma fonte do Termux, F-Droid), abra o Termux:Boot uma vez.
2. `pkg install termux-api` e depois `bash boot-setup.sh` (liga o bot sozinho quando o celular reinicia).
3. Android: Configurações > Apps > Termux (e Termux:Boot) > Bateria > **Sem restrições**. Deixe o celular carregando.
4. Use `bash start-bg.sh` para ligar, e `bash checar24h.sh` para ver o que falta.
5. Quando o bot volta, ele manda uma mensagem para o dono ("ligado e funcionando… fiquei fora por X min"). Desligue com `AVISO_INICIO=0` no `.env`.
A sessão do WhatsApp fica salva em `auth/`: depois de reiniciar **não precisa parear de novo**.
Para ficar 24h de verdade, rode o bot em um aparelho que fique sempre ligado (veja `deploy/LEIA-ME.md`).

## Dono no modo esperto
O bot roda no seu número; quando `/ativaesperto` está ligado em um grupo, suas mensagens comuns nesse grupo também podem
receber resposta da IA sem mencionar o bot. A ponte filtra os ecos das mensagens enviadas pelo próprio bot e o banco deduplica
mensagens repetidas por ID. Com o modo desligado, mensagens comuns do dono não acionam a IA. Em conversas privadas, continue
usando os comandos de ativação específicos (`/ativaesperto` na conversa ou `/espertodm on`).

## Voz e áudio (OpenRouter, Groq e outros modelos de texto)
Modelos de texto não geram áudio; o bot usa um motor de voz separado. Grátis no Termux: `pkg install espeak ffmpeg` e depois
`python3 -m nicolas voz --motor local`. Teste: `python3 -m nicolas aitest --tudo`. Detalhes em `docs/PROVEDORES-IA.md`.
Peça no grupo com o modo esperto ligado: "cria um áudio falando oi", "responde em áudio", "manda uma mensagem de voz".

## XP e moedas iniciais de dois perfis
`nicolas/initial_users.py` define (uma vez, com backup antes): 55 81 9727-6369 → 891 XP e 789 moedas; 55 81 7314-3183 → 1228 XP
(nível 4) e mais de 1.090.000 moedas. O nível vem do XP (nível 4 = a partir de 900 XP; 891 XP é nível 3).

**Rank dos dois perfis:** se não aparecerem no `.rank` de um grupo, o dono manda `.ajustarperfis` **nesse grupo**. No Termux,
`python3 -m nicolas perfis` mostra o que está salvo no banco (`--aplicar` reaplica).

**Conversa privada (DM):** com `/ativaesperto` ligado na conversa, a IA responde a **pessoa**. As **suas** mensagens são
ignoradas de propósito (para o bot não responder por cima de você), a não ser que você chame o bot: `Ei bot, ...` ou `/pergunta`.
Na conversa com você mesmo ("Mensagens para você") a IA responde tudo. A resposta sai do seu número, visível para a pessoa.

**"Aguardando mensagem" nas respostas do bot:** acontece quando o WhatsApp não consegue decifrar uma mensagem enviada pelo
aparelho conectado. A ponte agora guarda as últimas mensagens enviadas para atender o pedido de reenvio (`getMessage`).
Se persistir: confirme que só há UM bot rodando (`bash stop.sh` e depois `bash start-bg.sh`) e que o WhatsApp do celular está
atualizado; em último caso, `.desconectar confirmar` e parear de novo.
