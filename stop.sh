#!/usr/bin/env bash
# Para o Robô Nicolas 🤖 de outra sessão do Termux (a sessão do WhatsApp é preservada).
# Uso:  bash stop.sh
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1
PIDFILE="data/bot.pid"

# processos soltos (de um terminal que travou, por exemplo) também são encerrados
kill_strays() {
  command -v pkill >/dev/null 2>&1 || return 0
  pkill -TERM -f "bash start.sh" 2>/dev/null
  pkill -TERM -f "node bridge/index.js" 2>/dev/null
  pkill -TERM -f "python3 -m nicolas start" 2>/dev/null
  sleep 1
  pkill -KILL -f "bash start.sh" 2>/dev/null
  pkill -KILL -f "node bridge/index.js" 2>/dev/null
  pkill -KILL -f "python3 -m nicolas start" 2>/dev/null
  rm -f data/gateway.pid
  return 0
}

pid="$(cat "$PIDFILE" 2>/dev/null)"
if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
  kill_strays
  echo "✔ Nenhum bot ativo (processos soltos, se havia, foram encerrados)."
  rm -f "$PIDFILE"
  exit 0
fi

echo "Parando o bot (PID $pid)..."
# o Node é o filho do start.sh: pedir a ele para encerrar faz o start.sh sair e limpar tudo
if command -v pkill >/dev/null 2>&1; then
  pkill -TERM -f "node bridge/index.js" 2>/dev/null
fi
kill -TERM "$pid" 2>/dev/null

for _ in $(seq 1 15); do
  kill -0 "$pid" 2>/dev/null || { kill_strays; echo "✔ Bot parado."; rm -f "$PIDFILE"; exit 0; }
  sleep 1
done
echo "O bot não parou sozinho; forçando..."
kill -KILL "$pid" 2>/dev/null
command -v pkill >/dev/null 2>&1 && pkill -KILL -f "node bridge/index.js" 2>/dev/null
command -v pkill >/dev/null 2>&1 && pkill -TERM -f "nicolas start" 2>/dev/null
rm -f "$PIDFILE"
echo "✔ Bot forçado a parar."
