#!/usr/bin/env bash
# Diagnóstico: o bot está pronto para ficar ligado 24h? Uso:  bash checar24h.sh
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1
ok(){ echo "  ✔ $*"; }; no(){ echo "  ✖ $*"; }
pid="$(cat data/bot.pid 2>/dev/null)"
if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then ok "bot rodando (PID $pid)"; else no "bot PARADO → bash start-bg.sh"; fi
python3 -m nicolas health >/dev/null 2>&1 && ok "gateway respondendo" || no "gateway não responde"
[ -f auth/creds.json ] && ok "sessão do WhatsApp salva (não precisa parear de novo)" || no "sem sessão: rode bash start.sh uma vez"
if [ -n "${TERMUX_VERSION:-}" ] || [[ "${PREFIX:-}" == *com.termux* ]]; then
  [ -f "$HOME/.termux/boot/robo-nicolas.sh" ] && ok "liga sozinho ao reiniciar o celular (Termux:Boot)" \
    || no "NÃO liga sozinho após reiniciar → instale o app Termux:Boot, abra-o uma vez e rode: bash boot-setup.sh"
  command -v termux-wake-lock >/dev/null 2>&1 && ok "termux-wake-lock disponível" || no "instale: pkg install termux-api (e o app Termux:API)"
  echo "  ℹ Android: Configurações > Apps > Termux > Bateria > 'Sem restrições' (e o mesmo para Termux:Boot)."
fi
echo "Últimas linhas do log:"; tail -n 5 logs/supervisor.log 2>/dev/null
