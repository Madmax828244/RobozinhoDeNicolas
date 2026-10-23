#!/usr/bin/env bash
# Inicia o Robô Nicolas 🤖: sobe o bot (Python) e a ponte com o WhatsApp (Node).
# Uso:  bash start.sh      (Ctrl+C encerra; ou, em outra sessão do Termux:  bash stop.sh)
#       bash start-bg.sh   roda em segundo plano (sobrevive ao fechar a sessão do Termux)
#       A sessão do WhatsApp é preservada ao parar. O bot reinicia sozinho se algo cair e só para com Ctrl+C,
#       bash stop.sh ou o comando .desligarbot.
set -u
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1

B=$'\033[1m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; N=$'\033[0m'
info() { printf '%s[bot]%s %s\n' "$B" "$N" "$*"; }
warn() { printf '%s[bot]%s %s%s%s\n' "$B" "$N" "$Y" "$*" "$N"; }
die()  { printf '\n%s✖ %s%s\n' "$R" "$*" "$N" >&2; exit 1; }

RESTART_DELAY="${NICOLAS_RESTART_DELAY:-5}"
GWPID_FILE="data/gateway.pid"
WATCH_PID=""

[ -f .env ] || die "Arquivo .env não encontrado. Rode primeiro: bash install.sh"
[ -d bridge/node_modules/@whiskeysockets/baileys ] || die "Dependências não instaladas. Rode primeiro: bash install.sh"
command -v node >/dev/null 2>&1 || die "Node.js não encontrado. No Termux: pkg install nodejs-lts"
command -v python3 >/dev/null 2>&1 || die "Python não encontrado. No Termux: pkg install python"
mkdir -p logs data auth
chmod 700 auth 2>/dev/null

PIDFILE="data/bot.pid"
if [ -f "$PIDFILE" ]; then
  old="$(cat "$PIDFILE" 2>/dev/null)"
  if [ -n "$old" ] && [ "$old" != "$$" ] && kill -0 "$old" 2>/dev/null && ps -p "$old" -o args= 2>/dev/null | grep -q "start.sh"; then
    die "O bot já está rodando (PID $old). Para parar: bash stop.sh   (duas conexões com a mesma conta derrubam uma à outra)"
  fi
fi
echo "$$" > "$PIDFILE"

cleanup() {
  trap - EXIT INT TERM
  [ "$(cat "$PIDFILE" 2>/dev/null)" = "$$" ] && rm -f "$PIDFILE"
  if [ -n "$WATCH_PID" ]; then kill "$WATCH_PID" 2>/dev/null; wait "$WATCH_PID" 2>/dev/null; fi
  gw="$(cat "$GWPID_FILE" 2>/dev/null)"
  if [ -n "$gw" ] && kill -0 "$gw" 2>/dev/null; then
    kill "$gw" 2>/dev/null
    wait "$gw" 2>/dev/null
  fi
  rm -f "$GWPID_FILE"
  command -v termux-wake-unlock >/dev/null 2>&1 && termux-wake-unlock >/dev/null 2>&1
  return 0
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# mantém o celular acordado enquanto o bot roda (só existe no Termux)
if command -v termux-wake-lock >/dev/null 2>&1; then
  termux-wake-lock >/dev/null 2>&1 && info "Wake-lock ativado (o Android não suspende o Termux)."
fi

info "Verificando a configuração..."
python3 -m nicolas check || die "A verificação falhou. Corrija o que foi indicado e tente de novo."

launch_gateway() {
  if [ -f logs/bot.log ] && [ "$(wc -c < logs/bot.log)" -gt 2000000 ]; then mv -f logs/bot.log logs/bot.log.1; fi
  python3 -m nicolas start >> logs/bot.log 2>&1 &
  echo "$!" > "$GWPID_FILE"
}

gateway_alive() {
  local p
  p="$(cat "$GWPID_FILE" 2>/dev/null)"
  [ -n "$p" ] && kill -0 "$p" 2>/dev/null
}

start_gateway() {
  launch_gateway
  local i
  for i in $(seq 1 30); do
    if python3 -m nicolas health >/dev/null 2>&1; then return 0; fi
    gateway_alive || return 1
    sleep 1
  done
  return 1
}

# Vigia o bot (Python) enquanto a ponte roda: se ele cair ou travar, é reiniciado sozinho.
watch_gateway() {
  local fails=0 p
  while true; do
    sleep 20
    if python3 -m nicolas health >/dev/null 2>&1; then
      fails=0
    else
      fails=$((fails + 1))
      if [ "$fails" -ge 2 ]; then
        p="$(cat "$GWPID_FILE" 2>/dev/null)"
        [ -n "$p" ] && kill "$p" 2>/dev/null && sleep 2
        printf '[%s] bot (Python) sem resposta: reiniciando\n' "$(date +%H:%M:%S)" >> logs/bot.log
        launch_gateway
        fails=0
      fi
    fi
  done
}

info "Iniciando o bot (logs em logs/bot.log)..."
start_gateway || { tail -n 15 logs/bot.log 2>/dev/null; die "O bot não iniciou. Veja as últimas linhas do log acima."; }
watch_gateway &
WATCH_PID=$!
info "Bot no ar. Iniciando a conexão com o WhatsApp..."

fast_fail=0
while true; do
  gateway_alive || { warn "O bot parou inesperadamente. Reiniciando..."; start_gateway || warn "Ainda não consegui reiniciar o bot; o vigia tentará de novo."; }
  started="$(date +%s)"
  node bridge/index.js
  code=$?
  case "$code" in
    0)       info "Encerrado. Até a próxima!"; exit 0 ;;
    130|143) exit "$code" ;;
    2)       die "Configuração ou dependências com problema (veja a mensagem acima). Rode: bash install.sh" ;;
    3)       die "É preciso um terminal interativo para autenticar. Rode 'bash start.sh' diretamente no Termux." ;;
    4)       die "A conexão foi encerrada de propósito (veja a mensagem acima). Corrija o motivo e rode de novo." ;;
  esac
  # Modo 24/7: nunca desiste. Se a ponte cai repetidamente logo ao iniciar, espera cada vez mais (até 2 min).
  now="$(date +%s)"
  if [ $((now - started)) -lt 20 ]; then fast_fail=$((fast_fail + 1)); else fast_fail=0; fi
  delay=$((RESTART_DELAY * (1 << (fast_fail > 5 ? 5 : fast_fail))))
  [ "$delay" -gt 120 ] && delay=120
  warn "A ponte encerrou (código $code). Reiniciando em ${delay}s... (Ctrl+C para sair)"
  sleep "$delay"
done
