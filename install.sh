#!/usr/bin/env bash
# Instalador do Robô Nicolas 🤖 para Termux (Android, sem root). Também funciona em Linux comum.
# Uso:  bash install.sh
# Variáveis opcionais:  BAILEYS_SPEC=<versão ou tag>  (ex.: BAILEYS_SPEC=6.7.19 bash install.sh)
set -u
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1
ROOT="$(pwd)"

B=$'\033[1m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; N=$'\033[0m'
step() { printf '\n%s==> %s%s\n' "$B" "$*" "$N"; }
ok()   { printf '  %s✔%s %s\n' "$G" "$N" "$*"; }
warn() { printf '  %s!%s %s\n' "$Y" "$N" "$*"; }
die()  { printf '\n%s✖ %s%s\n' "$R" "$*" "$N" >&2; exit 1; }

IS_TERMUX=0
if [ -n "${TERMUX_VERSION:-}" ] || [[ "${PREFIX:-}" == *com.termux* ]]; then IS_TERMUX=1; fi

printf '%s🤖 Instalador do Robô Nicolas%s\n' "$B" "$N"

# ---------------------------------------------------------------- 1. pasta
step "1/6 Verificando a pasta do projeto"
case "$ROOT" in
  /sdcard/*|/storage/*|/mnt/*|/data/media/*)
    die "O projeto está no armazenamento compartilhado ($ROOT), que não aceita links simbólicos nem bloqueio de arquivos
   do SQLite. Copie para a pasta inicial do Termux e rode de lá:
     cp -r \"$ROOT\" ~/Robo-Nicolas && cd ~/Robo-Nicolas && bash install.sh" ;;
esac
ok "pasta: $ROOT"

# ---------------------------------------------------------------- 2. pacotes
step "2/6 Verificando Node.js, Python e Git"
pkgs=()
command -v node    >/dev/null 2>&1 || pkgs+=(nodejs-lts)
command -v npm     >/dev/null 2>&1 || pkgs+=(nodejs-lts)
command -v python3 >/dev/null 2>&1 || pkgs+=(python)
command -v git     >/dev/null 2>&1 || pkgs+=(git)
if [ "${#pkgs[@]}" -gt 0 ]; then
  uniq_pkgs=($(printf '%s\n' "${pkgs[@]}" | sort -u))
  if [ "$IS_TERMUX" -eq 1 ]; then
    warn "Instalando: ${uniq_pkgs[*]}"
    pkg install -y "${uniq_pkgs[@]}" || die "Falha ao instalar pacotes. Tente: pkg update && pkg upgrade, depois rode de novo.
   Se o download falhar, troque o espelho com: termux-change-repo"
  else
    die "Faltam programas: ${uniq_pkgs[*]}. Instale-os pelo gerenciador de pacotes do seu sistema."
  fi
fi

node_major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
[ "$node_major" -ge 20 ] 2>/dev/null || die "Node.js 20 ou mais novo é necessário (encontrado: $(node -v 2>/dev/null || echo nenhum)). No Termux: pkg install nodejs-lts"
ok "Node.js $(node -v)"
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null \
  || die "Python 3.10 ou mais novo é necessário (encontrado: $(python3 --version 2>&1)). No Termux: pkg install python"
python3 -c 'import sqlite3' 2>/dev/null || die "O Python está sem o módulo sqlite3. No Termux: pkg install python (reinstale)."
ok "$(python3 --version 2>&1) (com sqlite3)"
ok "$(git --version)"

# ---------------------------------------------------------------- 3. configuração
step "3/6 Criando a configuração (.env)"
python3 -m nicolas init-env || die "Não foi possível criar o .env."
ok ".env protegido (permissão 600) e pastas data/, logs/ e auth/ prontas"

owner="$(python3 -m nicolas getenv OWNER_IDS)"
if [ -z "$owner" ] && [ -t 0 ]; then
  printf '\n  Seu número de WhatsApp (você será o DONO do bot), com DDI e DDD. Ex.: 5511999999999\n  (Enter para pular e configurar depois no .env): '
  read -r ans
  digits="$(printf '%s' "${ans:-}" | tr -cd '0-9')"
  if [ -n "$digits" ]; then
    if [ "${#digits}" -le 11 ]; then digits="55$digits"; warn "Sem DDI: assumindo Brasil (+55)."; fi
    python3 -m nicolas setenv OWNER_IDS "$digits" >/dev/null && ok "Dono configurado: +$digits"
  else
    warn "Dono não configurado. Edite OWNER_IDS no arquivo .env quando quiser."
  fi
fi

# ---------------------------------------------------------------- 4. dependências Node
step "4/6 Instalando as dependências da ponte WhatsApp (pode levar alguns minutos)"
export npm_config_fund=false npm_config_audit=false npm_config_update_notifier=false
cd "$ROOT/bridge" || die "Pasta bridge/ não encontrada."
installed=0
for attempt in 1 2 3; do
  if [ -n "${BAILEYS_SPEC:-}" ]; then
    warn "Usando a versão informada: @whiskeysockets/baileys@$BAILEYS_SPEC"
    npm install --omit=optional "@whiskeysockets/baileys@$BAILEYS_SPEC" && installed=1 && break
  elif [ -f package-lock.json ]; then
    npm ci --omit=optional && installed=1 && break
    warn "npm ci falhou; tentando npm install..."
    npm install --omit=optional && installed=1 && break
  else
    npm install --omit=optional && installed=1 && break
  fi
  warn "Tentativa $attempt de 3 falhou."
  sleep 3
done
if [ "$installed" -ne 1 ]; then
  die "Não foi possível instalar as dependências do Node. Verifique:
   • a internet do celular (teste: ping -c1 registry.npmjs.org);
   • se o Git está instalado (git --version): algumas dependências vêm do GitHub;
   • se o erro citar node-gyp/make: pkg install -y build-essential python;
   • se citar uma versão inexistente do Baileys: BAILEYS_SPEC=latest bash install.sh
   • limpe o cache e tente de novo: npm cache clean --force && bash install.sh"
fi
cd "$ROOT" || exit 1
ok "dependências instaladas"

# pacote opcional para o comando .qr (puro Python)
if ! python3 -c 'import segno' 2>/dev/null; then
  if python3 -m pip install -q segno >/dev/null 2>&1 || python3 -m pip install -q --break-system-packages segno >/dev/null 2>&1; then
    ok "segno instalado (comando .qr habilitado)"
  else
    warn "Não instalei o 'segno' (opcional). O comando .qr avisará que está indisponível."
  fi
else
  ok "segno já instalado (comando .qr habilitado)"
fi

# ffmpeg (opcional): permite ao modo esperto enviar mensagens de VOZ de verdade (ogg/opus). Sem ele, o áudio vai como arquivo .wav.
if command -v ffmpeg >/dev/null 2>&1; then
  ok "ffmpeg já instalado (respostas em voz habilitadas)"
elif [ "$IS_TERMUX" -eq 1 ]; then
  if pkg install -y ffmpeg >/dev/null 2>&1; then ok "ffmpeg instalado (respostas em voz habilitadas)"
  else warn "Não instalei o ffmpeg (opcional). Tente depois: pkg install ffmpeg. Sem ele o áudio sai como arquivo .wav."; fi
else
  warn "ffmpeg não encontrado (opcional): sem ele o áudio do modo esperto sai como arquivo .wav."
fi

# ---------------------------------------------------------------- 5. verificação
step "5/6 Verificando a instalação"
( cd bridge && node --check index.js && node --check lib.js ) || die "Erro de sintaxe na ponte."
ok "ponte: sintaxe válida"
( cd bridge && node --input-type=module -e "await import('@whiskeysockets/baileys'); await import('pino'); await import('qrcode-terminal');" ) \
  || die "A biblioteca do WhatsApp foi instalada, mas não carrega neste Node. Veja o README (seção Problemas comuns)."
ok "bibliotecas do WhatsApp carregam corretamente"
python3 -m nicolas check || die "A verificação do bot falhou (veja as mensagens acima)."
TESTLOG="$(mktemp 2>/dev/null || echo "$PWD/logs/test-$$.log")"
if python3 -m nicolas test >"$TESTLOG" 2>&1; then
  ok "testes do bot: $(grep -E '^Ran ' "$TESTLOG")"
else
  cat "$TESTLOG"; rm -f "$TESTLOG"
  die "Os testes do bot falharam."
fi
rm -f "$TESTLOG"
if ( cd bridge && node --test test/lib.test.js >/dev/null 2>&1 ); then ok "testes da ponte: aprovados"; else warn "Testes da ponte falharam (o bot pode funcionar, mas avise o suporte)."; fi

# ---------------------------------------------------------------- 6. fim
step "6/6 Pronto!"
printf '  Para iniciar o bot:\n\n      %sbash start.sh%s\n\n' "$B" "$N"
printf '  Na primeira vez ele vai pedir o número do WhatsApp do bot e mostrar um\n  código de pareamento para você digitar em Aparelhos conectados.\n'
printf '  Leia o README.md para o passo a passo e para os cuidados de segurança.\n'
