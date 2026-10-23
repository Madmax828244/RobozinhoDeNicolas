#!/usr/bin/env bash
# Atualiza o Robô Nicolas 🤖 a partir de um novo .zip SEM apagar seus dados (.env, sessão do WhatsApp, banco, lembretes).
# Uso:  bash update.sh caminho/para/Robo-Nicolas.zip
set -u
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1
ZIP="${1:-}"
if [ -z "$ZIP" ] || [ ! -f "$ZIP" ]; then
  echo "Uso: bash update.sh /caminho/Robo-Nicolas.zip"
  echo "Ex.: bash update.sh ~/storage/downloads/Robo-Nicolas.zip"
  exit 1
fi
command -v unzip >/dev/null 2>&1 || { echo "Instale o unzip: pkg install unzip"; exit 1; }

echo "1/5 Parando o bot..."
bash stop.sh >/dev/null 2>&1

echo "2/5 Copiando o banco (backup de segurança)..."
python3 -m nicolas backup || echo "(sem banco ainda — tudo bem)"

echo "3/5 Extraindo a nova versão..."
TMP="$(mktemp -d 2>/dev/null || mktemp -d -p "${TMPDIR:-$HOME}" update.XXXXXX)" || { echo "Não consegui criar pasta temporária."; exit 1; }
trap 'rm -rf "$TMP"' EXIT
unzip -q -o "$ZIP" -d "$TMP" || { echo "Falha ao abrir o zip."; exit 1; }
SRC="$TMP"
if [ "$(ls -1 "$TMP" | wc -l)" = "1" ] && [ -d "$TMP/$(ls -1 "$TMP")" ]; then SRC="$TMP/$(ls -1 "$TMP")"; fi
[ -f "$SRC/nicolas/__main__.py" ] || { echo "Esse zip não parece ser do Robô Nicolas."; exit 1; }

# copia por cima (nunca apaga nada); .env, auth/, data/ e logs/ não vêm no zip, então ficam como estão
cp -a "$SRC"/. . || { echo "Falha ao copiar os arquivos."; exit 1; }

echo "4/5 Atualizando dependências..."
[ -f .env.example ] && [ ! -f .env ] && python3 -m nicolas init-env
if command -v npm >/dev/null 2>&1; then
  (cd bridge && npm install --omit=optional --no-audit --no-fund >/dev/null 2>&1) || echo "⚠ npm install falhou; rode: cd bridge && npm install --omit=optional"
fi

echo "5/5 Corrigindo a progressão antiga e verificando..."
python3 -m nicolas seed-progress || { echo "⚠ Não consegui aplicar a correção de XP. Veja o erro acima; o backup está em data/backups/."; exit 1; }
python3 -m nicolas check || { echo "⚠ A verificação encontrou um problema. Veja a saída acima."; exit 1; }
echo
echo "✔ Atualizado. Seus dados foram mantidos. Para ligar:  bash start-bg.sh   (ou bash start.sh)"
