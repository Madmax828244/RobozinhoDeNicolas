"""Utilidades: calculadora, conversores, textos formatados e tradução."""
from __future__ import annotations

import base64
import io

from ..ai_client import AINotConfigured, ask
from ..calc import CalcError, calculate
from ..core import CommandError, Reply
from ..net import NetError, request_json
from ..units import UnitError, all_units, canon, convert
from ..utils import fmt_number, norm, parse_number

LANGS = {
    "pt": "pt", "portugues": "pt", "português": "pt", "en": "en", "ingles": "en", "inglês": "en",
    "es": "es", "espanhol": "es", "fr": "fr", "frances": "fr", "francês": "fr", "de": "de", "alemao": "de",
    "alemão": "de", "it": "it", "italiano": "it", "ja": "ja", "japones": "ja", "japonês": "ja",
    "ru": "ru", "russo": "ru", "zh": "zh", "chines": "zh", "chinês": "zh", "ko": "ko", "coreano": "ko",
}
LANG_NAMES = {"pt": "português do Brasil", "en": "inglês", "es": "espanhol", "fr": "francês", "de": "alemão",
              "it": "italiano", "ja": "japonês", "ru": "russo", "zh": "chinês", "ko": "coreano"}

_BOLD = (0x1D5D4, 0x1D5EE, 0x1D7EC)       # sans-serif bold
_MONO = (0x1D670, 0x1D68A, 0x1D7F6)       # monoespaçado


def _shift(text: str, start_upper: int, start_lower: int, start_digit: int) -> str:
    out = []
    for ch in text:
        if "A" <= ch <= "Z":
            out.append(chr(start_upper + ord(ch) - 65))
        elif "a" <= ch <= "z":
            out.append(chr(start_lower + ord(ch) - 97))
        elif "0" <= ch <= "9":
            out.append(chr(start_digit + ord(ch) - 48))
        else:
            out.append(ch)
    return "".join(out)


def _bubbles(text: str) -> str:
    out = []
    for ch in text:
        if "A" <= ch <= "Z":
            out.append(chr(0x24B6 + ord(ch) - 65))
        elif "a" <= ch <= "z":
            out.append(chr(0x24D0 + ord(ch) - 97))
        else:
            out.append(ch)
    return "".join(out)


def _wide(text: str) -> str:
    return "".join(chr(ord(c) + 0xFEE0) if 0x21 <= ord(c) <= 0x7E else c for c in text)


STYLES = {
    "negrito": lambda t: _shift(t, *_BOLD),
    "mono": lambda t: _shift(t, *_MONO),
    "bolhas": _bubbles,
    "largo": _wide,
    "zap-negrito": lambda t: f"*{t}*",
    "zap-italico": lambda t: f"_{t}_",
    "zap-riscado": lambda t: f"~{t}~",
    "zap-codigo": lambda t: f"```{t}```",
    "inverter": lambda t: t[::-1],
    "espacado": lambda t: " ".join(t),
    "maiusculas": lambda t: t.upper(),
    "minusculas": lambda t: t.lower(),
    "capitalizar": lambda t: t.title(),
}


def setup(reg):
    U = dict(category="utilidades")

    @reg.command("calcular", description="Calculadora segura (+ - * / ^ % parênteses, sqrt, sin, log, fatorial...)",
                 usage="<expressão>", example="calcular 2*(3+4)^2", min_args=1, aliases=("calc", "calcula"), **U)
    def calcular(ctx):
        try:
            result = calculate(ctx.raw)
        except CalcError as exc:
            raise CommandError(str(exc))
        return f"🧮 {ctx.raw[:80]} = *{fmt_number(result, 8)}*"

    @reg.command("converter", description="Converte unidades (comprimento, massa, volume, tempo, dados, temperatura...)",
                 usage="<valor> <de> <para>", example="converter 10 km mi", min_args=3, aliases=("conv",), **U)
    def converter(ctx):
        parts = [a for a in ctx.args if norm(a) not in {"para", "em", "to", "->"}]
        if len(parts) < 3:
            raise CommandError("Use: converter <valor> <de> <para>. Ex.: converter 10 km mi")
        try:
            value = parse_number(parts[0])
            result = convert(value, parts[1], parts[2])
        except ValueError as exc:
            raise CommandError(str(exc) if isinstance(exc, UnitError) else "Valor inválido.")
        return f"📐 {fmt_number(value)} {canon(parts[1])} = *{fmt_number(result, 6)}* {canon(parts[2])}"

    @reg.command("unidades", description="Lista as unidades suportadas pelo conversor", **U)
    def unidades(ctx):
        lines = ["📐 *Unidades suportadas*"]
        for cat, units in all_units().items():
            lines.append(f"• {cat}: {', '.join(units)}")
        lines.append(f"\nAtalhos: {ctx.prefix}km-mi 10 • {ctx.prefix}c-f 25 • {ctx.prefix}gb-mb 2")
        return "\n".join(lines)

    # Atalhos de conversão (km-mi, kg-lb, c-f ...): todos usam o mesmo conversor validado
    for cat, units in all_units().items():
        for a in units:
            for b in units:
                if a != b:
                    reg.add_alias(f"{a}-{b}", "converter", (a, b))

    @reg.command("texto", description="Formata texto: negrito, mono, bolhas, largo, inverter, espacado, maiusculas...",
                 usage="<estilo> <texto>", example="texto negrito Olá mundo", min_args=2, aliases=("fonte",), **U)
    def texto(ctx):
        style = norm(ctx.args[0])
        if style not in STYLES:
            raise CommandError("Estilos: " + ", ".join(STYLES))
        body = ctx.raw[len(ctx.args[0]):].strip()[:400]
        return STYLES[style](body)

    @reg.command("traduzir", description="Traduz um texto (LibreTranslate ou IA, se configurados)",
                 usage="<idioma> <texto>", example="traduzir en bom dia, tudo bem?", min_args=2, cooldown=4,
                 aliases=("tr", "translate"), **U)
    def traduzir(ctx):
        lang = LANGS.get(norm(ctx.args[0]), LANGS.get(ctx.args[0].lower()))
        if not lang:
            raise CommandError("Idioma não reconhecido. Use: " + ", ".join(sorted(set(LANGS.values()))))
        text = ctx.raw[len(ctx.args[0]):].strip()[:1000]
        try:
            if ctx.cfg.translate_configured:
                body = {"q": text, "source": "auto", "target": lang, "format": "text"}
                if ctx.cfg.translate_api_key:
                    body["api_key"] = ctx.cfg.translate_api_key
                data = request_json(ctx.cfg.translate_url + "/translate", data=body)
                return f"🌐 ({LANG_NAMES[lang]}) {data['translatedText']}"
            if ctx.cfg.ai_configured:
                out = ask(ctx.cfg, f"Traduza para {LANG_NAMES[lang]}. Responda só com a tradução:\n\n{text}", max_tokens=500)
                return f"🌐 ({LANG_NAMES[lang]}) {out}"
        except (NetError, AINotConfigured, KeyError) as exc:
            return f"⚠️ Não consegui traduzir agora ({exc if isinstance(exc, NetError) else 'resposta inesperada'})."
        return ("🌐 Nenhum serviço de tradução configurado. O responsável pode definir TRANSLATE_URL "
                "(LibreTranslate) ou as variáveis da IA (AI_*).")

    @reg.command("qr", category="midia", description="Gera um QR Code a partir de um texto ou link (gerado localmente)",
                 usage="<texto>", example="qr https://exemplo.com", min_args=1, cooldown=5)
    def qr(ctx):
        try:
            import segno
        except ImportError:
            return "🖼️ O gerador de QR Code precisa do pacote opcional 'segno'. O responsável deve rodar: pip install segno"
        text = ctx.raw[:300]
        buf = io.BytesIO()
        segno.make(text, error="m").save(buf, kind="png", scale=8, border=2)
        return Reply(text="🔳 Seu QR Code:", image_base64=base64.b64encode(buf.getvalue()).decode())
