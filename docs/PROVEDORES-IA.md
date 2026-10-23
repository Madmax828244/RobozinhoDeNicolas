# Configurar provedores de IA no Robô Nicolas

O Nicolas não fica preso ao Gemini. A resposta de texto do modo `/ativaesperto` usa o provedor e o modelo definidos em `AI_PROVIDER` e `AI_MODEL` no `.env`. A chave é guardada localmente e nunca deve ser enviada no chat ou incluída no ZIP.

## OpenRouter (recomendado para escolher entre muitos modelos)

1. Crie uma chave em https://openrouter.ai/keys.
2. Consulte o catálogo em https://openrouter.ai/models e copie o ID exato do modelo.
3. No Termux, dentro de `~/Robo-Nicolas`, rode:

```bash
python3 -m nicolas ia --provider openrouter --model "provedor/modelo"
```

Cole a chave quando solicitada; ela não aparece enquanto você digita. Use o ID real do catálogo no lugar de `provedor/modelo`. O comando testa a API ao final. Se o teste não passar, confirme saldo/créditos, permissões da chave e se o modelo está disponível para sua conta.

Para ver os modelos que o endpoint do provedor disponibiliza:

```bash
python3 -m nicolas modelos
```

Para trocar de modelo, repita `python3 -m nicolas ia --provider openrouter --model "NOVO-ID-EXATO"`.

## Outros provedores suportados

A sintaxe geral é:

```bash
python3 -m nicolas ia --provider NOME --model "ID-EXATO-DO-MODELO"
```

Valores reconhecidos para `NOME`: `openrouter`, `openai`, `groq`, `deepseek`, `together`, `anthropic` e `gemini`. Os modelos mudam com o tempo; informe o ID atualmente aceito pelo serviço. Alguns provedores exigem que a chave tenha crédito ou acesso habilitado ao modelo.

Para uma API própria compatível com o formato OpenAI Chat Completions:

```bash
python3 -m nicolas ia --provider openai-compatible --base-url "https://api.seu-servidor/v1" --model "modelo-exato"
```

O comando também solicitará a chave. Só use HTTP sem TLS para um IP privado de rede local confiável, conforme a opção explícita do CLI; para serviços públicos use HTTPS.

## Testar e iniciar

```bash
python3 -m nicolas aitest
python3 -m nicolas check
bash start.sh
```

Se o bot já estiver rodando, pare com `Ctrl+C` e inicie novamente para garantir que o processo carregue a configuração nova. Depois ative `/ativaesperto` no grupo conforme as permissões do bot.

## O que é independente do provedor

- **Texto/chat:** usa o provedor/modelo configurado.
- **Transcrição de voz:** depende de um serviço STT compatível configurado; não é garantida só por usar OpenRouter.
- **Resposta falada/TTS e geração de imagens:** o projeto atual tem integração específica com Gemini. Escolher outro provedor de texto não converte automaticamente essas funções.
- **Chamadas de voz/vídeo do WhatsApp:** não são implementadas pela ponte atual.

Não coloque chaves no código-fonte, nos logs, em mensagens do WhatsApp nem no ZIP. O `.env` está no `.gitignore` e deve permanecer privado.

## Voz (áudio): modelo de texto ≠ voz

Modelos de **texto** (MiniMax, Llama, GPT-texto etc. no OpenRouter ou Groq) só escrevem texto — eles não geram áudio, mesmo
que a resposta deles diga que "consegue". Por isso o Nicolas faz em duas etapas: o modelo de texto escreve a resposta e o
bot converte em mensagem de voz com um **motor de voz** (`AI_TTS_ENGINE`):

| Motor | O que precisa | Qualidade |
|---|---|---|
| `local` | `pkg install espeak ffmpeg` (grátis, sem conta, sem internet) | voz robótica, mas funciona sempre |
| `gemini` | chave do Gemini só para a voz (`AI_TTS_API_KEY`) | voz natural; sujeita à cota/modelo do Google |
| `openai` | chave de uma API com `/audio/speech` (ex.: OpenAI) | voz natural; paga conforme o provedor |
| `auto` (padrão) | usa Gemini se o texto for Gemini; senão `local` se o espeak estiver instalado | |

Configurar: `python3 -m nicolas voz --motor local` (ou `gemini`, `openai`). Testar: `python3 -m nicolas aitest --tudo`.
Se o motor escolhido falhar, o bot tenta a voz local antes de mandar só texto. Eu não consegui testar a voz real (Gemini/OpenAI/
espeak) no ambiente de desenvolvimento: confirme com `aitest --tudo` no seu aparelho.

### ElevenLabs (voz natural)
`python3 -m nicolas voz --motor elevenlabs` pede a chave (xi-api-key, criada no painel da ElevenLabs), lista as vozes da sua conta e
usa a primeira (ou escolha com `--voz-id`). Usa o modelo `eleven_multilingual_v2` (`AI_TTS_ELEVEN_MODEL`). O plano grátis tem
cota mensal de caracteres e pode restringir vozes da biblioteca; se acabar a cota, o bot cai para a voz local. Precisa do ffmpeg
para virar mensagem de voz. Não testei contra o serviço real.
