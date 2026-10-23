"""Ferramentas para desenvolvedores (todas determinísticas e seguras: nada é executado)."""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import urllib.parse
import uuid
from datetime import datetime, timezone

from ..core import CommandError
from ..utils import truncate

ALGOS = {"md5": hashlib.md5, "sha1": hashlib.sha1, "sha256": hashlib.sha256, "sha512": hashlib.sha512}


def setup(reg):
    D = dict(category="dev")

    @reg.command("base64", description="Codifica ou decodifica Base64", usage="enc|dec <texto>", example="base64 enc olá",
                 min_args=2, aliases=("b64",), **D)
    def b64(ctx):
        mode, text = ctx.args[0].lower(), ctx.raw[len(ctx.args[0]):].strip()
        if mode in {"enc", "codificar", "e"}:
            return "`" + base64.b64encode(text.encode()).decode() + "`"
        if mode in {"dec", "decodificar", "d"}:
            try:
                return truncate(base64.b64decode(text, validate=True).decode("utf-8"), 1500)
            except (binascii.Error, UnicodeDecodeError, ValueError):
                raise CommandError("Base64 inválido.")
        raise CommandError("Use enc ou dec.")

    @reg.command("hash", description="Calcula hash (md5, sha1, sha256, sha512) de um texto", usage="<algoritmo> <texto>",
                 example="hash sha256 olá", min_args=2, **D)
    def hash_(ctx):
        algo = ctx.args[0].lower()
        if algo not in ALGOS:
            raise CommandError("Algoritmos: " + ", ".join(ALGOS))
        text = ctx.raw[len(ctx.args[0]):].strip()
        return f"`{ALGOS[algo](text.encode()).hexdigest()}`"

    @reg.command("json", description="Valida e formata um JSON", usage="<json>", example='json {"a":1}', min_args=1,
                 aliases=("jsonformat",), **D)
    def json_(ctx):
        try:
            data = json.loads(ctx.raw)
        except ValueError as exc:
            raise CommandError(f"JSON inválido: {exc}")
        return "```" + truncate(json.dumps(data, indent=2, ensure_ascii=False), 1500) + "```"

    @reg.command("uuid", description="Gera um UUID v4", **D)
    def uuid_(ctx):
        return f"`{uuid.uuid4()}`"

    @reg.command("urlcodificar", description="Codifica um texto para URL", usage="<texto>", min_args=1,
                 aliases=("urlenc",), **D)
    def urlenc(ctx):
        return "`" + urllib.parse.quote(ctx.raw, safe="") + "`"

    @reg.command("urldecodificar", description="Decodifica um texto de URL", usage="<texto>", min_args=1,
                 aliases=("urldec",), **D)
    def urldec(ctx):
        return urllib.parse.unquote(ctx.raw)[:1500]

    @reg.command("timestamp", description="Converte timestamp Unix <-> data (UTC); sem argumento mostra o atual",
                 usage="[número|AAAA-MM-DD]", example="timestamp 1700000000", **D)
    def timestamp(ctx):
        if not ctx.args:
            return f"🕒 Timestamp atual: `{int(ctx.now)}`"
        arg = ctx.args[0]
        if arg.isdigit():
            n = int(arg)
            if n > 10**11:
                n //= 1000
            try:
                return "📅 " + datetime.fromtimestamp(n, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            except (OverflowError, OSError, ValueError):
                raise CommandError("Timestamp fora do intervalo.")
        try:
            dt = datetime.strptime(arg, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            raise CommandError("Use um número ou AAAA-MM-DD.")
        return f"🕒 `{int(dt.timestamp())}`"

    @reg.command("binario", description="Converte número decimal em binário/hexadecimal e vice-versa",
                 usage="<número> [bin|hex|dec]", example="binario 255 bin", min_args=1, aliases=("bin",), **D)
    def binario(ctx):
        raw = ctx.args[0].lower()
        try:
            if raw.startswith("0x"):
                n = int(raw, 16)
            elif raw.startswith("0b"):
                n = int(raw, 2)
            else:
                n = int(raw)
        except ValueError:
            raise CommandError("Número inválido (use decimal, 0x... ou 0b...).")
        if abs(n) > 10**18:
            raise CommandError("Número grande demais.")
        return f"🔢 dec: {n} • bin: {bin(n)} • hex: {hex(n)} • oct: {oct(n)}"

    @reg.command("cor", category="midia", description="Converte cor HEX <-> RGB", usage="<#rrggbb | r g b>",
                 example="cor #ff8800", min_args=1)
    def cor(ctx):
        if len(ctx.args) == 3 and all(a.isdigit() and 0 <= int(a) <= 255 for a in ctx.args):
            r, g, b = map(int, ctx.args)
            return f"🎨 rgb({r}, {g}, {b}) = #{r:02x}{g:02x}{b:02x}"
        m = re.fullmatch(r"#?([0-9a-fA-F]{6})", ctx.args[0])
        if not m:
            raise CommandError("Use #rrggbb ou três números 0-255.")
        h = m.group(1)
        return f"🎨 #{h.lower()} = rgb({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)})"

    @reg.command("contar", description="Conta caracteres, palavras e linhas de um texto", usage="<texto>", min_args=1,
                 aliases=("count",), **D)
    def contar(ctx):
        t = ctx.raw
        return f"🔤 {len(t)} caracteres • {len(t.split())} palavras • {t.count(chr(10)) + 1} linha(s)"

    @reg.command("slug", description="Transforma um texto em slug de URL", usage="<texto>", example="slug Olá Mundo!",
                 min_args=1, **D)
    def slug(ctx):
        from ..utils import norm
        return "`" + re.sub(r"[^a-z0-9]+", "-", norm(ctx.raw)).strip("-") + "`"
