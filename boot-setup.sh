#!/usr/bin/env bash
# Faz o Robô Nicolas 🤖 ligar sozinho quando o celular reinicia (precisa do app "Termux:Boot", do F-Droid).
# Uso:  bash boot-setup.sh            cria o script de inicialização
#       bash boot-setup.sh --remove   remove
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1
DIR="$(pwd)"
BOOT="$HOME/.termux/boot"
FILE="$BOOT/robo-nicolas.sh"

if [ "${1:-}" = "--remove" ]; then
  rm -f "$FILE" && echo "✔ Início automático removido."
  exit 0
fi
[ -f auth/creds.json ] || { echo "✖ Conecte o WhatsApp primeiro com  bash start.sh  (depois pare com Ctrl+C)." >&2; exit 1; }
mkdir -p "$BOOT"
cat > "$FILE" <<EOF
#!/data/data/com.termux/files/usr/bin/sh
termux-wake-lock
sleep 25
cd "$DIR" && bash start-bg.sh >> "$DIR/logs/boot.log" 2>&1
EOF
chmod +x "$FILE"
echo "✔ Criado: $FILE"
echo
echo "Falta só isto (uma vez):"
echo "  1. Instale o app Termux:Boot pelo F-Droid (mesma fonte do Termux)."
echo "  2. Abra o Termux:Boot uma vez, para o Android liberar a inicialização."
echo "  3. No Android: Configurações > Apps > Termux > Bateria > Sem restrições (o mesmo para o Termux:Boot)."
echo "Depois disso, o bot liga sozinho alguns segundos após o celular iniciar."
