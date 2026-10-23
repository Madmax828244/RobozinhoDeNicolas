# Bot ligado 24h, mesmo com o celular desligado

Um bot rodando no Termux **para quando o celular desliga, descarrega ou o Android mata o app** — isso não tem como
corrigir por software. O WhatsApp aceita aparelhos conectados, então o bot pode rodar em **outro computador que fique
sempre ligado** (VPS barata, Raspberry Pi, PC velho, ou um celular antigo na tomada) sem depender do seu celular.

Passos (Linux): instale `nodejs` (20+), `python3`, `ffmpeg`; copie a pasta do bot; rode `bash install.sh`;
`python3 -m nicolas ia`; `bash start.sh` e pareie com o código. Depois use **systemd** (`robo-nicolas.service`) ou
**Docker** (`docker-compose.yml`) para ligar sozinho no boot e reiniciar se cair.

A sessão fica em `auth/` e o banco em `data/` — faça cópia dessas pastas (o bot também faz backup do banco sozinho em
`data/backups/`). Para parar de vez: `/desligarbot` (dono) ou `bash stop.sh`.
