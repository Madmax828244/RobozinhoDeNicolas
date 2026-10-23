#!/usr/bin/env bash
# Roda o Robô Nicolas 🤖 em SEGUNDO PLANO: continua ativo mesmo se você fechar a sessão do Termux.
# Uso:  bash start-bg.sh      (precisa ter feito o primeiro login com "bash start.sh")
#       tail -f logs/supervisor.log     acompanha o que está acontecendo
#       bash stop.sh                    para tudo
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1
die() { printf '\n✖ %s\n' "$*" >&2; exit 1; }

[ -f .env ] || die "Arquivo .env não encontrado. Rode primeiro: bash install.sh"
[ -f auth/creds.json ] || die "O WhatsApp ainda não foi conectado. Rode uma vez  bash start.sh  (faz o login), pare com Ctrl+C e depois use  bash start-bg.sh"
mkdir -p logs data

PIDFILE="data/bot.pid"
old="$(cat "$PIDFILE" 2>/dev/null)"
if [ -n "$old" ] && kill -0 "$old" 2>/dev/null && ps -p "$old" -o args= 2>/dev/null | grep -q "start.sh"; then
  die "O bot já está rodando (PID $old). Para parar: bash stop.sh"
fi

command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock >/dev/null 2>&1
if [ -f logs/supervisor.log ] && [ "$(wc -c < logs/supervisor.log)" -gt 1000000 ]; then mv -f logs/supervisor.log logs/supervisor.log.1; fi

if command -v setsid >/dev/null 2>&1; then
  nohup setsid bash start.sh >> logs/supervisor.log 2>&1 < /dev/null &
else
  nohup bash start.sh >> logs/supervisor.log 2>&1 < /dev/null &
fi
sleep 6
pid="$(cat "$PIDFILE" 2>/dev/null)"
if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
  echo "✔ Bot rodando em segundo plano (PID $pid)."
  echo "  Acompanhar:  tail -f logs/supervisor.log"
  echo "  Parar:       bash stop.sh   (ou mande .desligarbot no WhatsApp)"
else
  echo "✖ O bot não ficou de pé. Últimas linhas do log:" >&2
  tail -n 15 logs/supervisor.log >&2
  exit 1
fi
