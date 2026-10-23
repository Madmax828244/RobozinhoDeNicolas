#!/usr/bin/env bash
# Copia o banco (lembretes, XP, configurações dos grupos) para data/backups/.  Uso:  bash backup.sh
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1
python3 -m nicolas backup
