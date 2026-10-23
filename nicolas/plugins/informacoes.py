"""Informações: data/hora, clima, dicionário, Wikipédia, CEP e dados do grupo."""
from __future__ import annotations

import re
import urllib.parse
from datetime import date, datetime, timedelta, timezone

from ..core import CommandError
from ..net import NetError, request_json
from ..utils import fmt_duration, local_dt, truncate

DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]
SIGNOS = [
    ((3, 21), (4, 19), "♈ Áries"), ((4, 20), (5, 20), "♉ Touro"), ((5, 21), (6, 20), "♊ Gêmeos"),
    ((6, 21), (7, 22), "♋ Câncer"), ((7, 23), (8, 22), "♌ Leão"), ((8, 23), (9, 22), "♍ Virgem"),
    ((9, 23), (10, 22), "♎ Libra"), ((10, 23), (11, 21), "♏ Escorpião"), ((11, 22), (12, 21), "♐ Sagitário"),
    ((12, 22), (12, 31), "♑ Capricórnio"), ((1, 1), (1, 19), "♑ Capricórnio"), ((1, 20), (2, 18), "♒ Aquário"),
    ((2, 19), (3, 20), "♓ Peixes"),
]
WMO = {0: "céu limpo ☀️", 1: "predominantemente limpo 🌤️", 2: "parcialmente nublado ⛅", 3: "nublado ☁️",
       45: "neblina 🌫️", 48: "neblina com geada 🌫️", 51: "garoa fraca 🌦️", 53: "garoa 🌦️", 55: "garoa forte 🌧️",
       61: "chuva fraca 🌦️", 63: "chuva 🌧️", 65: "chuva forte 🌧️", 71: "neve fraca 🌨️", 73: "neve 🌨️",
       75: "neve forte ❄️", 80: "pancadas de chuva fracas 🌦️", 81: "pancadas de chuva 🌧️", 82: "pancadas fortes ⛈️",
       95: "trovoadas ⛈️", 96: "trovoadas com granizo ⛈️", 99: "trovoadas com granizo forte ⛈️"}
DATE_RE = re.compile(r"^(\d{1,2})/(\d{1,2})(?:/(\d{4}))?$")


def _parse_date(text: str, need_year: bool = False):
    m = DATE_RE.match(text.strip())
    if not m:
        raise CommandError("Use o formato DD/MM/AAAA (ou DD/MM).")
    d, mo, y = int(m[1]), int(m[2]), m[3]
    if need_year and not y:
        raise CommandError("Informe também o ano: DD/MM/AAAA.")
    try:
        return date(int(y) if y else 2000, mo, d), bool(y)
    except ValueError:
        raise CommandError("Essa data não existe.") from None


def zodiac(day: int, month: int) -> str:
    for (m1, d1), (m2, d2), name in SIGNOS:
        if (month, day) >= (m1, d1) and (month, day) <= (m2, d2):
            return name
    return "?"


def setup(reg):
    I = dict(category="informacoes")

    @reg.command("hora", description="Mostra a hora atual (Brasília ou outro fuso, ex.: +9)", usage="[fuso]",
                 example="hora +9", aliases=("horas",), **I)
    def hora(ctx):
        now = local_dt(ctx.now, ctx.cfg.tz_offset)
        lines = [f"🕒 Brasília/local: *{now.strftime('%H:%M:%S')}* ({DIAS[now.weekday()]})"]
        if ctx.args:
            raw = ctx.args[0].lower().replace("utc", "").replace("gmt", "") or "0"
            try:
                off = float(raw.replace(",", "."))
            except ValueError:
                raise CommandError("Use um fuso como +9, -5 ou utc.")
            if not -12 <= off <= 14:
                raise CommandError("Fuso fora do intervalo (-12 a +14).")
            other = local_dt(ctx.now, off)
            lines.append(f"🌍 UTC{off:+g}: *{other.strftime('%H:%M:%S')}* ({DIAS[other.weekday()]})")
        return "\n".join(lines)

    @reg.command("data", description="Mostra a data de hoje por extenso", **I)
    def data(ctx):
        n = local_dt(ctx.now, ctx.cfg.tz_offset)
        return f"📅 Hoje é {DIAS[n.weekday()]}, {n.day} de {MESES[n.month - 1]} de {n.year}."

    @reg.command("diasate", description="Quantos dias faltam para uma data", usage="<DD/MM[/AAAA]>",
                 example="diasate 25/12", min_args=1, **I)
    def diasate(ctx):
        target, has_year = _parse_date(ctx.args[0])
        today = local_dt(ctx.now, ctx.cfg.tz_offset).date()
        if not has_year:
            target = target.replace(year=today.year)
            if target < today:
                try:
                    target = target.replace(year=today.year + 1)
                except ValueError:
                    target = target.replace(year=today.year + 1, day=28)
        diff = (target - today).days
        if diff == 0:
            return "🎉 É hoje!"
        return f"📆 {'Faltam' if diff > 0 else 'Passaram'} *{abs(diff)}* dia(s) para {target.strftime('%d/%m/%Y')}."

    @reg.command("idade", description="Calcula a idade a partir da data de nascimento", usage="<DD/MM/AAAA>",
                 example="idade 15/03/1995", min_args=1, **I)
    def idade(ctx):
        born, _ = _parse_date(ctx.args[0], need_year=True)
        today = local_dt(ctx.now, ctx.cfg.tz_offset).date()
        if born > today:
            raise CommandError("Essa data está no futuro.")
        years = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        return f"🎂 Idade: *{years}* anos ({(today - born).days} dias de vida)."

    @reg.command("signo", description="Descobre o signo pela data de nascimento", usage="<DD/MM>", example="signo 15/03",
                 min_args=1, **I)
    def signo(ctx):
        d, _ = _parse_date(ctx.args[0])
        return f"🔮 Signo: *{zodiac(d.day, d.month)}*"

    @reg.command("tempo", description="Previsão do tempo para uma cidade (serviço Open-Meteo)", usage="<cidade>",
                 example="tempo São Paulo", min_args=1, cooldown=5, aliases=("clima", "previsao"), **I)
    def tempo(ctx):
        if not ctx.cfg.weather_enabled:
            return "🌦️ O módulo de clima está desabilitado (WEATHER_ENABLED=0)."
        city = ctx.raw[:60]
        try:
            geo = request_json("https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode(
                {"name": city, "count": 1, "language": "pt", "format": "json"}))
            places = geo.get("results") or []
            if not places:
                return f"🔎 Não encontrei a cidade '{city}'."
            p = places[0]
            fc = request_json("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
                "latitude": p["latitude"], "longitude": p["longitude"], "timezone": "auto", "forecast_days": 3,
                "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"}))
            cur, day = fc["current"], fc["daily"]
        except (NetError, KeyError) as exc:
            return f"⚠️ Não consegui consultar o clima agora ({exc if isinstance(exc, NetError) else 'resposta inesperada'})."
        where = ", ".join(x for x in (p.get("name"), p.get("admin1"), p.get("country")) if x)
        lines = [f"🌦️ *{where}*",
                 f"Agora: {cur['temperature_2m']}°C (sensação {cur['apparent_temperature']}°C), {WMO.get(cur['weather_code'], 'condição variável')}",
                 f"Umidade {cur['relative_humidity_2m']}% • vento {cur['wind_speed_10m']} km/h", ""]
        for i in range(len(day["time"])):
            d = datetime.strptime(day["time"][i], "%Y-%m-%d")
            lines.append(f"• {d.strftime('%d/%m')} ({DIAS[d.weekday()][:3]}): {day['temperature_2m_min'][i]}° a "
                         f"{day['temperature_2m_max'][i]}°, {WMO.get(day['weather_code'][i], 'variável')}, "
                         f"chuva {day['precipitation_probability_max'][i]}%")
        return "\n".join(lines)

    @reg.command("dicionario", description="Significado de uma palavra (dictionaryapi.dev)", usage="<palavra>",
                 example="dicionario saudade", min_args=1, cooldown=4, aliases=("significado", "dic"), **I)
    def dicionario(ctx):
        word = ctx.args[0].lower()[:40]
        if not re.fullmatch(r"[a-zà-ú\-]+", word):
            raise CommandError("Informe uma única palavra, só com letras.")
        try:
            data = request_json("https://api.dictionaryapi.dev/api/v2/entries/pt-BR/" + urllib.parse.quote(word))
            meanings = data[0]["meanings"]
        except NetError as exc:
            return f"📖 Não encontrei '{word}' agora ({exc})."
        except (KeyError, IndexError, TypeError):
            return f"📖 Não encontrei '{word}' no dicionário."
        lines = [f"📖 *{word}*"]
        for m in meanings[:3]:
            defs = m.get("definitions") or []
            if defs:
                lines.append(f"• ({m.get('partOfSpeech', '—')}) {truncate(defs[0].get('definition', ''), 220)}")
        return "\n".join(lines)

    @reg.command("wiki", description="Resumo da Wikipédia em português", usage="<assunto>", example="wiki Machado de Assis",
                 min_args=1, cooldown=5, aliases=("pesquisar", "buscaweb"), **I)
    def wiki(ctx):
        if not ctx.cfg.web_enabled:
            return "🌐 A pesquisa na web está desabilitada (WEB_SEARCH_ENABLED=0)."
        query = ctx.raw[:80]
        try:
            res = request_json("https://pt.wikipedia.org/w/rest.php/v1/search/title?" + urllib.parse.urlencode(
                {"q": query, "limit": 1}))
            pages = res.get("pages") or []
            if not pages:
                return f"🔎 Nada encontrado para '{query}'."
            title = pages[0]["title"]
            summ = request_json("https://pt.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title.replace(" ", "_")))
            extract = summ.get("extract", "")
        except (NetError, KeyError) as exc:
            return f"⚠️ Não consegui pesquisar agora ({exc if isinstance(exc, NetError) else 'resposta inesperada'})."
        url = (summ.get("content_urls") or {}).get("desktop", {}).get("page", "")
        return f"📚 *{title}*\n{truncate(extract, 700)}\n{url}".strip()

    @reg.command("cep", description="Consulta um CEP brasileiro (ViaCEP)", usage="<cep>", example="cep 01001000",
                 min_args=1, cooldown=5, **I)
    def cep(ctx):
        digits = re.sub(r"\D", "", ctx.args[0])
        if len(digits) != 8:
            raise CommandError("O CEP precisa ter 8 dígitos.")
        try:
            data = request_json(f"https://viacep.com.br/ws/{digits}/json/")
        except NetError as exc:
            return f"⚠️ Não consegui consultar o CEP agora ({exc})."
        if data.get("erro"):
            return "🔎 CEP não encontrado."
        return (f"📮 *{digits[:5]}-{digits[5:]}*\n{data.get('logradouro', '')} - {data.get('bairro', '')}\n"
                f"{data.get('localidade', '')}/{data.get('uf', '')}")

    @reg.command("grupo", description="Informações do grupo atual", group_only=True, aliases=("infogrupo",), **I)
    def grupo(ctx):
        g = ctx.group
        return "\n".join([
            f"👥 *{ctx.msg.group_name or 'Grupo'}*",
            f"Participantes: {ctx.msg.group_size or 'desconhecido'} • administradores: {len(ctx.msg.group_admins)}",
            f"Regras: {'definidas' if g['rules'] else 'não definidas'} • prefixo: {ctx.prefix}",
            f"Módulos desativados: {', '.join(g['disabled_modules']) or 'nenhum'}",
        ])

    @reg.command("admins", description="Lista os administradores do grupo", group_only=True, **I)
    def admins(ctx):
        if not ctx.msg.group_admins:
            return "ℹ️ Não recebi a lista de administradores deste grupo."
        from ..utils import tag
        return ctx.reply("🛡️ *Administradores*\n" + "\n".join(f"• {tag(a)}" for a in ctx.msg.group_admins[:40]),
                         mentions=list(ctx.msg.group_admins[:40]))

    @reg.command("uptime", description="Há quanto tempo o bot está online", **I)
    def uptime(ctx):
        return f"⏱️ Online há {fmt_duration(ctx.bot.clock() - ctx.bot.stats['started'])}."
