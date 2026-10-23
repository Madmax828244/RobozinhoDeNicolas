"""Uso: python -m nicolas <start|check|health|commands|docs|console|test>"""
from __future__ import annotations

import argparse
import json
import os
import sys
import unittest
import urllib.request
from pathlib import Path

from .app import build_bot, setup_logging
from .config import ROOT, Config, load_dotenv


def cmd_check(args) -> int:
    load_dotenv()
    cfg = Config.from_env()
    bot = build_bot(cfg)
    h = bot.health()
    c = bot.registry.counts()
    print(f"Banco: {cfg.db_path} • esquema v{h['versao_schema']} • integridade: {'OK' if h['ok'] else 'FALHOU'}")
    print(f"Comandos: {c['comandos']} • aliases: {c['aliases']} • atalhos: {c['atalhos']} • nomes: {c['total_nomes']}")
    print(f"IA configurada: {'sim' if cfg.ai_configured else 'não'} • tradução externa: {'sim' if cfg.translate_configured else 'não'}")
    print(f"Donos configurados: {len(cfg.owner_ids)} • BRIDGE_TOKEN definido: {'sim' if cfg.bridge_token else 'NÃO'}")
    problems = bot.registry.validate()
    for p in problems:
        print("PROBLEMA:", p)
    return 0 if h["ok"] and not problems else 1


def cmd_start(args) -> int:
    from .server import make_server
    load_dotenv()
    cfg = Config.from_env()
    setup_logging(cfg.log_level)
    if not cfg.bridge_token:
        print("Defina BRIDGE_TOKEN no .env (um segredo longo e aleatório) antes de iniciar.", file=sys.stderr)
        return 2
    bot = build_bot(cfg)
    server = make_server(bot, cfg.host, cfg.port, cfg.bridge_token)
    from .backup import start_scheduler
    start_scheduler(bot.db, cfg.backup_hours, cfg.backup_keep)
    print(f"{cfg.bot_name}: gateway em http://{cfg.host}:{cfg.port} ({bot.registry.counts()['comandos']} comandos)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando...")
    finally:
        server.server_close()
        bot.db.close()
    return 0


def cmd_health(args) -> int:
    load_dotenv()
    cfg = Config.from_env()
    try:
        with urllib.request.urlopen(f"http://{cfg.host}:{cfg.port}/health", timeout=5) as r:
            print(r.read().decode())
            return 0
    except Exception as exc:
        print(f"Gateway fora do ar ou com problemas: {type(exc).__name__}", file=sys.stderr)
        return 1


def cmd_commands(args) -> int:
    bot = build_bot(db_path=":memory:")
    for key, cmds in bot.registry.by_category().items():
        print(f"\n[{key}] {len(cmds)}")
        for c in cmds:
            print(f"  {c.name:<16} {c.description}")
    print("\n", json.dumps(bot.registry.counts()))
    return 0


def cmd_docs(args) -> int:
    from .docsgen import generate_markdown
    bot = build_bot(db_path=":memory:")
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "COMANDOS.md").write_text(generate_markdown(bot.registry, bot.cfg.prefix), encoding="utf-8")
    print("docs/COMANDOS.md gerado.")
    return 0


def cmd_console(args) -> int:
    from .cli import run_console
    bot = build_bot(db_path=args.db or ":memory:")
    run_console(bot, user=args.user, admin=not args.membro)
    return 0


def cmd_test(args) -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
    return 0 if unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful() else 1


def cmd_init_env(args) -> int:
    from .envfile import init_env
    result = init_env()
    print(".env criado a partir do exemplo." if result["created"] else ".env já existia.")
    if result["token_generated"]:
        print("BRIDGE_TOKEN gerado automaticamente (não compartilhe o arquivo .env).")
    return 0


def cmd_getenv(args) -> int:
    from .config import parse_env_text
    path = ROOT / ".env"
    values = parse_env_text(path.read_text(encoding="utf-8")) if path.exists() else {}
    print(values.get(args.key, ""))
    return 0


def cmd_setenv(args) -> int:
    from .envfile import set_env
    try:
        set_env(ROOT / ".env", args.key, args.value)
    except ValueError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    print(f"{args.key} atualizado no .env.")
    return 0


def cmd_aitest(args) -> int:
    from .ai_client import ask
    from .net import NetError
    load_dotenv()
    cfg = Config.from_env()
    if not cfg.ai_configured:
        print("IA não configurada. Rode: python3 -m nicolas ia", file=sys.stderr)
        return 1
    print(f"Testando a IA (provedor: {cfg.ai_provider}, modelo: {cfg.effective_model})...")
    try:
        try:
            answer = ask(cfg, "Responda apenas: funcionando", max_tokens=30)
        except NetError as exc:
            if getattr(exc, "status", None) != 404:
                raise
            # modelo inexistente: pergunta ao provedor quais modelos a chave enxerga e escolhe um
            from .ai_client import list_models, pick_model
            from .envfile import set_env
            print(f"Modelo '{cfg.effective_model}' não existe nesse provedor. Procurando os disponíveis...")
            ids = list_models(cfg)
            new = pick_model(ids)
            if not new:
                raise NetError("o provedor não listou nenhum modelo de texto para esta chave") from None
            set_env(ROOT / ".env", "AI_MODEL", new)
            print(f"Usando o modelo '{new}' (salvo no .env). Outros disponíveis: {', '.join(ids[:12])}")
            import dataclasses
            cfg = dataclasses.replace(cfg, ai_model=new)
            answer = ask(cfg, "Responda apenas: funcionando", max_tokens=30)
    except NetError as exc:
        print(f"❌ Falhou: {exc}", file=sys.stderr)
        if "503" in str(exc) or "demorou" in str(exc):
            print("   O serviço está sobrecarregado ou a internet lenta. Isso é do lado do provedor/rede: espere "
                  "1 minuto e rode de novo: python3 -m nicolas aitest", file=sys.stderr)
        if "401" in str(exc) or "403" in str(exc) or "400" in str(exc):
            if cfg.ai_provider == "gemini":
                print("   Confira se a chave foi copiada inteira e se a API Gemini está habilitada para ela.", file=sys.stderr)
            else:
                print("   Confira a chave, as permissões, o provedor e o modelo configurado.", file=sys.stderr)
        elif "404" in str(exc):
            print("   Modelo não encontrado. Troque AI_MODEL no .env (ex.: gemini-flash-latest, gemini-2.5-flash).",
                  file=sys.stderr)
        return 1
    print(f"✅ Texto: a IA respondeu: {answer[:80]}")
    if getattr(args, "tudo", False):
        from . import gemini_media, tts
        import shutil
        if cfg.ai_provider == "gemini":
            try:
                gemini_media.make_image(cfg, "um círculo vermelho simples em fundo branco")
                print("✅ Imagem: funcionando")
            except NetError as exc:
                print(f"❌ Imagem: {exc} (modelo: {cfg.ai_image_model})", file=sys.stderr)
        else:
            print("ℹ️ Imagem: só o provedor Gemini gera imagens neste bot.")
        eng = tts.engine(cfg)
        if not eng:
            print("❌ Voz: nenhum motor de voz. Grátis no celular: pkg install espeak ffmpeg  |  ou rode: python3 -m nicolas voz",
                  file=sys.stderr)
        else:
            try:
                v = tts.speak(cfg, "Teste de voz do Robô Nicolas.")
                print(f"✅ Voz ({eng}): funcionando ({len(v['data'])} bytes, {v['mimetype']})")
            except NetError as exc:
                print(f"❌ Voz ({eng}): {exc}", file=sys.stderr)
        print(f"{'✅' if shutil.which('ffmpeg') else '⚠️'} ffmpeg: "
              f"{'instalado (voz em formato de mensagem de voz)' if shutil.which('ffmpeg') else 'ausente (o áudio sai como arquivo; instale com: pkg install ffmpeg)'}")
    return 0


def cmd_gemini(args) -> int:
    """Configura a IA Gemini sem deixar a chave no histórico do terminal."""
    import getpass
    from .envfile import set_env
    key = getpass.getpass("Cole a chave da API Gemini (não aparece na tela) e tecle Enter: ").strip()
    if len(key) < 20 or any(c.isspace() for c in key):
        print("Chave inválida (muito curta ou com espaços).", file=sys.stderr)
        return 1
    model = args.model or "gemini-flash-latest"
    set_env(ROOT / ".env", "AI_PROVIDER", "gemini")
    set_env(ROOT / ".env", "AI_MODEL", model)
    set_env(ROOT / ".env", "AI_BASE_URL", "")
    set_env(ROOT / ".env", "AI_ALLOW_HTTP_LAN", "0")
    set_env(ROOT / ".env", "AI_API_KEY", key)
    print(f"Gemini configurado no .env (modelo {model}). Testando...")
    return cmd_aitest(args)


def cmd_ia_local(args) -> int:
    """Configura uma API auto-hospedada compatível com OpenAI, sem exigir chave."""
    import getpass
    import urllib.parse
    from .envfile import set_env
    from .providers import default_base

    kinds = {
        "ollama": ("ollama", "Ollama", "http://127.0.0.1:11434/v1"),
        "docker": ("docker-model-runner", "Docker Model Runner", "http://127.0.0.1:12434/engines/v1"),
        "compativel": ("openai-compatible", "API compatível com OpenAI", ""),
    }
    kind = (getattr(args, "tipo", "") or "").strip().lower()
    if not kind:
        print("Qual API você quer conectar?\n  1) Ollama\n  2) Docker Model Runner\n  3) Outra API compatível com OpenAI")
        answer = input("Escolha [1-3]: ").strip()
        kind = {"1": "ollama", "2": "docker", "3": "compativel"}.get(answer, answer.lower())
    if kind not in kinds:
        print("Tipo inválido. Use --tipo ollama, --tipo docker ou --tipo compativel.", file=sys.stderr)
        return 2
    provider, label, default_url = kinds[kind]
    base_url = (getattr(args, "url", "") or "").strip()
    if not base_url:
        suggestion = default_url or "https://seu-servidor/v1"
        base_url = input(f"URL base da API [{suggestion}]: ").strip() or default_url
    if not base_url:
        print("A URL da API é obrigatória para o modo compatível.", file=sys.stderr)
        return 2
    base_url = base_url.rstrip("/")
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        print("URL inválida. Exemplo: http://127.0.0.1:11434/v1", file=sys.stderr)
        return 2

    model = (getattr(args, "model", "") or "").strip()
    if not model:
        example = "llama3.2:3b" if kind == "ollama" else (
            "hf.co/ORG/MODELO (use o identificador mostrado pelo Docker Model Runner)" if kind == "docker" else "nome-do-modelo")
        model = input(f"Nome exato do modelo (exemplo: {example}): ").strip()
    if not model or any(c.isspace() for c in model):
        print("O nome do modelo é obrigatório e não deve conter espaços.", file=sys.stderr)
        return 2

    key = getpass.getpass("Chave da API (opcional; pressione Enter se o servidor não exigir): ").strip()
    if any(c.isspace() for c in key):
        print("A chave não pode conter espaços.", file=sys.stderr)
        return 2

    allow_lan_http = bool(getattr(args, "permitir_http_rede", False))
    host = (parsed.hostname or "").lower()
    if parsed.scheme == "http" and host not in {"localhost", "127.0.0.1", "::1"} and not allow_lan_http:
        print("A URL usa HTTP fora de localhost. Para uma API num PC da sua rede local, confirme a confiança na rede e rode com --permitir-http-rede.", file=sys.stderr)
        return 2
    if allow_lan_http:
        import ipaddress
        try:
            if parsed.scheme != "http" or not ipaddress.ip_address(host).is_private:
                print("--permitir-http-rede só aceita HTTP para um IP privado (por exemplo, 192.168.1.20). Use HTTPS para servidores públicos.", file=sys.stderr)
                return 2
        except ValueError:
            print("--permitir-http-rede exige um endereço IP privado, não um domínio.", file=sys.stderr)
            return 2

    set_env(ROOT / ".env", "AI_PROVIDER", provider)
    set_env(ROOT / ".env", "AI_MODEL", model)
    set_env(ROOT / ".env", "AI_BASE_URL", base_url)
    set_env(ROOT / ".env", "AI_API_KEY", key)
    set_env(ROOT / ".env", "AI_ALLOW_HTTP_LAN", "1" if allow_lan_http else "0")
    print(f"{label} salvo no .env (modelo: {model}; chave: {'configurada' if key else 'não necessária'}).")
    if kind == "docker" and host in {"localhost", "127.0.0.1", "::1"}:
        print("Aviso: localhost só funciona se o Docker Model Runner estiver acessível neste mesmo ambiente. No Termux/Android, normalmente ele precisa estar num computador; nesse caso use o IP desse PC e --permitir-http-rede (se for HTTP na sua rede privada).")
    print("Testando a conexão...")
    import argparse as _argparse
    return cmd_aitest(_argparse.Namespace(tudo=False))


def cmd_modelos(args) -> int:
    from .ai_client import list_models
    from .net import NetError
    load_dotenv()
    cfg = Config.from_env()
    if not cfg.ai_configured:
        print("IA não configurada. Rode: python3 -m nicolas ia", file=sys.stderr)
        return 1
    try:
        ids = list_models(cfg)
    except NetError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1
    print(f"Modelos disponíveis ({cfg.ai_provider}):\n  " + "\n  ".join(ids))
    print("Para usar um:  python3 -m nicolas setenv AI_MODEL <nome>")
    return 0


def cmd_seed_progress(args) -> int:
    from .db import Database
    from .initial_users import apply_initial_progression
    load_dotenv()
    cfg = Config.from_env()
    db = Database(cfg.db_path)
    try:
        result = apply_initial_progression(db)
        print(f"Carteiras tratadas: {result['wallets']} • registros de XP tratados: {result['xp_rows']}")
        if result["backup"]:
            print(f"Backup anterior à alteração: {result['backup']}")
        else:
            print("Nenhum ajuste de XP/moedas pendente nos registros existentes.")
            print("Se um dos números ainda não tiver registro de XP neste grupo, ele receberá o nível configurado quando enviar a primeira mensagem aqui.")
    finally:
        db.close()
    return 0


def cmd_voz(args) -> int:
    """Configura a VOZ do bot (independente do modelo de texto)."""
    import getpass
    from . import tts
    from .envfile import set_env
    from .net import NetError
    load_dotenv()
    motor = (args.motor or "").lower()
    if motor not in {"local", "gemini", "openai", "elevenlabs"}:
        cfg = Config.from_env()
        print(f"Voz atual: {tts.engine(cfg) or 'nenhuma'} (AI_TTS_ENGINE={cfg.ai_tts_engine})")
        print("Escolha o motor:\n  python3 -m nicolas voz --motor local    (grátis, no próprio aparelho: pkg install espeak ffmpeg)\n"
              "  python3 -m nicolas voz --motor gemini   (pede uma chave do Gemini, só para a voz)\n"
              "  python3 -m nicolas voz --motor openai   (API com /audio/speech, ex.: OpenAI)\n"
              "  python3 -m nicolas voz --motor elevenlabs   (voz natural da ElevenLabs)")
        return 0
    set_env(ROOT / ".env", "AI_TTS_ENGINE", motor)
    if motor in {"gemini", "openai", "elevenlabs"}:
        key = getpass.getpass(f"Cole a chave da API de voz ({motor}) (não aparece na tela): ").strip()
        if len(key) < 20 or any(c.isspace() for c in key):
            print("Chave inválida.", file=sys.stderr)
            return 1
        set_env(ROOT / ".env", "AI_TTS_API_KEY", key)
        if motor == "openai" and args.base_url:
            set_env(ROOT / ".env", "AI_TTS_BASE_URL", args.base_url)
    os.environ["AI_TTS_ENGINE"] = motor
    if motor in {"gemini", "openai", "elevenlabs"}:
        os.environ["AI_TTS_API_KEY"] = key
    if motor == "elevenlabs":
        voice = args.voz_id
        if not voice:
            from .net import request_json
            try:
                data = request_json("https://api.elevenlabs.io/v1/voices", headers={"xi-api-key": key}, timeout=30)
                voices = [(v.get("voice_id"), v.get("name", "?")) for v in data.get("voices", []) if v.get("voice_id")]
            except NetError as exc:
                print(f"❌ Não consegui listar as vozes: {exc}. Confira a chave ou passe --voz-id <id>.", file=sys.stderr)
                return 1
            if not voices:
                print("❌ Sua conta não listou nenhuma voz. Escolha uma no site e use --voz-id <id>.", file=sys.stderr)
                return 1
            print("Vozes da sua conta: " + ", ".join(f"{n} ({i})" for i, n in voices[:10]))
            voice = voices[0][0]
            print(f"Usando a primeira ({voices[0][1]}). Para outra: python3 -m nicolas voz --motor elevenlabs --voz-id <id>")
        set_env(ROOT / ".env", "AI_TTS_VOICE_ID", voice)
        os.environ["AI_TTS_VOICE_ID"] = voice
    cfg = Config.from_env()
    print(f"Motor de voz salvo: {motor}. Testando...")
    try:
        v = tts.speak(cfg, "Teste de voz do Robô Nicolas.")
    except NetError as exc:
        print(f"❌ Falhou: {exc}", file=sys.stderr)
        return 1
    print(f"✅ Voz funcionando ({len(v['data'])} bytes, {v['mimetype']}). Reinicie o bot: bash stop.sh && bash start-bg.sh")
    return 0


def cmd_perfis(args) -> int:
    """Mostra o XP/moedas dos dois perfis iniciais no banco e, com --aplicar, reaplica os valores configurados."""
    from .db import Database
    from .initial_users import apply_initial_progression, report
    load_dotenv()
    cfg = Config.from_env()
    db = Database(cfg.db_path)
    try:
        if args.aplicar:
            res = apply_initial_progression(db)
            print(f"Aplicado: {res['wallets']} carteira(s), {res['xp_rows']} linha(s) de XP (backup: {res['backup'] or 'não necessário'}).")
        for r in report(db):
            print(f"\n+{r['phone']}  (meta: {r['target_xp']} XP, {r['target_coins']} moedas)")
            print("  moedas: " + (", ".join(f"{w['coins']} (id {w['user_id']})" for w in r["wallets"]) or "sem carteira ainda"))
            if not r["groups"]:
                print("  XP: este número ainda não tem linha de ranking em nenhum grupo "
                      "(ele precisa mandar mensagem, ou use .ajustarperfis no grupo)")
            for g in r["groups"]:
                print(f"  XP {g['xp']} no grupo {g['chat_id']}")
    finally:
        db.close()
    return 0


def cmd_backup(args) -> int:
    from .backup import make_backup
    from .db import Database
    load_dotenv()
    cfg = Config.from_env()
    db = Database(cfg.db_path)
    try:
        path = make_backup(db, cfg.backup_keep)
    finally:
        db.close()
    print(f"Backup salvo em: {path}" if path else "Banco em memória: nada a salvar.")
    return 0


def cmd_ia(args) -> int:
    """Configura a IA com chave, ou um provedor local explicitamente escolhido."""
    import getpass
    from .envfile import set_env
    from .providers import PROVIDERS, default_model, default_base, detect_provider
    prefix = "AI_FALLBACK_" if getattr(args, "reserva", False) else "AI_"
    requested_provider = (getattr(args, "provider", "") or "").strip().lower()
    keyless_providers = {"ollama", "docker-model-runner", "openai-compatible"}
    print("Provedores: " + ", ".join(PROVIDERS))
    key = getpass.getpass("Cole a chave da API (pressione Enter se o servidor local não exigir; não aparece na tela): ").strip()
    if key and (len(key) < 20 or any(c.isspace() for c in key)):
        print("Chave inválida (muito curta ou com espaços).", file=sys.stderr)
        return 1
    if not key and requested_provider not in keyless_providers:
        print("Este provedor exige chave. Para uma API local sem chave, use: python3 -m nicolas ia-local", file=sys.stderr)
        return 1
    provider = requested_provider or detect_provider(key)
    if not provider:
        provider = input("Não reconheci o formato da chave. Qual o provedor? ").strip().lower()
    if provider not in PROVIDERS:
        print(f"Provedor desconhecido: {provider}. Use um de: {', '.join(PROVIDERS)}", file=sys.stderr)
        return 1
    if not key and provider not in keyless_providers:
        print("Este provedor exige chave. Para uma API local sem chave, use: python3 -m nicolas ia-local", file=sys.stderr)
        return 1
    model = getattr(args, "model", "") or default_model(provider)
    if not model:
        model = input(f"Nome do modelo para {provider}: ").strip()
        if not model:
            print("Modelo obrigatório para este provedor.", file=sys.stderr)
            return 1

    # Não deixe uma URL de um provedor anterior contaminar a configuração do novo provedor.
    base = (getattr(args, "base_url", "") or "").strip().rstrip("/")
    if not base and provider in {"ollama", "docker-model-runner"}:
        base = default_base(provider)
    if not base and provider == "openai-compatible":
        base = input("URL base da API (ex.: https://servidor/v1): ").strip().rstrip("/")
    if provider == "openai-compatible" and not base:
        print("A URL base é obrigatória para openai-compatible.", file=sys.stderr)
        return 1

    set_env(ROOT / ".env", prefix + "PROVIDER", provider)
    set_env(ROOT / ".env", prefix + "MODEL", model)
    set_env(ROOT / ".env", prefix + "API_KEY", key)
    set_env(ROOT / ".env", prefix + "BASE_URL", base)
    print(f"{PROVIDERS[provider]['label']} configurado no .env (modelo {model}){' como IA reserva' if prefix != 'AI_' else ''}; chave {'configurada' if key else 'não necessária'}.")
    if prefix != "AI_":
        print("Pronto. A reserva só é usada quando a principal falha (limite de uso, instabilidade).")
        return 0
    # Desative a exceção de HTTP na rede local ao trocar para um provedor normal.
    if provider not in keyless_providers or not getattr(args, "permitir_http_rede", False):
        set_env(ROOT / ".env", "AI_ALLOW_HTTP_LAN", "0")
    elif getattr(args, "permitir_http_rede", False):
        set_env(ROOT / ".env", "AI_ALLOW_HTTP_LAN", "1")
    print("Testando...")
    return cmd_aitest(args)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="nicolas", description="Robô Nicolas 🤖")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name, fn, help_ in [("start", cmd_start, "inicia o gateway HTTP"), ("check", cmd_check, "verifica configuração e banco"),
                            ("health", cmd_health, "consulta /health do gateway em execução"),
                            ("commands", cmd_commands, "lista os comandos registrados"),
                            ("docs", cmd_docs, "gera docs/COMANDOS.md"), ("test", cmd_test, "roda os testes")]:
        sub.add_parser(name, help=help_).set_defaults(fn=fn)
    at = sub.add_parser("aitest", help="testa a conexão com a IA configurada")
    at.add_argument("--tudo", action="store_true", help="testa também geração de imagem e de voz (Gemini)")
    at.set_defaults(fn=cmd_aitest)
    gm = sub.add_parser("gemini", help="configura a IA Gemini (pede a chave sem mostrar na tela)")
    gm.add_argument("--model", default="")
    gm.set_defaults(fn=cmd_gemini)
    local = sub.add_parser("ia-local", help="configura/testa API local ou compatível sem exigir chave")
    local.add_argument("--tipo", choices=("ollama", "docker", "compativel"), default="")
    local.add_argument("--url", default="", help="URL base da API; para Docker Model Runner, termina em /engines/v1")
    local.add_argument("--model", default="", help="identificador exato do modelo")
    local.add_argument("--permitir-http-rede", action="store_true",
                       help="permite HTTP apenas para um IP privado confiável da rede local")
    local.set_defaults(fn=cmd_ia_local)
    sub.add_parser("modelos", help="lista os modelos de IA que a sua chave pode usar").set_defaults(fn=cmd_modelos)
    vz = sub.add_parser("voz", help="configura a voz do bot (local grátis, Gemini ou OpenAI)")
    vz.add_argument("--motor", default="")
    vz.add_argument("--base-url", default="")
    vz.add_argument("--voz-id", default="", help="(elevenlabs) id da voz; sem isso usa a primeira da sua conta")
    vz.set_defaults(fn=cmd_voz)
    pf = sub.add_parser("perfis", help="mostra o XP/moedas dos dois perfis iniciais (--aplicar reaplica)")
    pf.add_argument("--aplicar", action="store_true")
    pf.set_defaults(fn=cmd_perfis)
    sub.add_parser("backup", help="copia o banco para data/backups/").set_defaults(fn=cmd_backup)
    sub.add_parser("seed-progress", help="aplica uma única vez os pisos iniciais de moedas/XP aos dois usuários configurados").set_defaults(fn=cmd_seed_progress)
    ia = sub.add_parser("ia", help="configura a IA com chave (Groq, Gemini, OpenAI...) — a chave não aparece na tela")
    ia.add_argument("--provider", default="", help="groq, gemini, openai, openrouter, deepseek, anthropic...")
    ia.add_argument("--model", default="")
    ia.add_argument("--base-url", default="", help="URL base para uma API compatível/customizada")
    ia.add_argument("--permitir-http-rede", action="store_true",
                    help="permite HTTP apenas para um IP privado confiável da rede local")
    ia.add_argument("--reserva", action="store_true", help="guarda como IA reserva (usada se a principal falhar)")
    ia.set_defaults(fn=cmd_ia)
    sub.add_parser("init-env", help="cria o .env e gera o BRIDGE_TOKEN").set_defaults(fn=cmd_init_env)
    ge = sub.add_parser("getenv", help="mostra o valor de uma variável do .env")
    ge.add_argument("key")
    ge.set_defaults(fn=cmd_getenv)
    se = sub.add_parser("setenv", help="define uma variável no .env")
    se.add_argument("key")
    se.add_argument("value")
    se.set_defaults(fn=cmd_setenv)
    c = sub.add_parser("console", help="simulador de conversa no terminal")
    c.add_argument("--user", default="5511999990001")
    c.add_argument("--membro", action="store_true", help="entra como membro comum (não admin)")
    c.add_argument("--db", default="")
    c.set_defaults(fn=cmd_console)
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
