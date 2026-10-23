"""Registro de comandos: categorias, aliases, busca e detecção de duplicados."""
from __future__ import annotations

import difflib
import importlib
import pkgutil
from dataclasses import dataclass, field
from typing import Callable

from .utils import norm

ROLE_MEMBER, ROLE_MOD, ROLE_ADMIN, ROLE_OWNER = 0, 1, 2, 3
ROLE_NAMES = {0: "membro", 1: "moderador", 2: "administrador", 3: "dono"}

CATEGORIES = {
    "sistema": "⚙️ Sistema",
    "admin": "🛡️ Administração",
    "diversao": "🎉 Diversão",
    "jogos": "🎮 Jogos",
    "ia": "🧠 Inteligência Artificial",
    "utilidades": "🧰 Utilidades",
    "economia": "💰 Economia virtual",
    "perfil": "👤 Perfil e ranking",
    "personalizacao": "🎨 Personalização",
    "informacoes": "ℹ️ Informações",
    "midia": "🖼️ Mídia",
    "produtividade": "📝 Produtividade",
    "seguranca": "🔐 Segurança",
    "dev": "💻 Desenvolvedores",
}
PROTECTED_MODULES = {"sistema", "admin"}


class DuplicateCommandError(Exception):
    pass


@dataclass
class Command:
    name: str
    handler: Callable
    category: str
    description: str
    usage: str = ""
    example: str = ""
    aliases: tuple = ()
    min_role: int = ROLE_MEMBER
    group_only: bool = False
    min_args: int = 0
    cooldown: float = 0.0
    subcategory: str = ""
    module: str = ""
    hidden: bool = False


class Registry:
    def __init__(self):
        self.commands: dict[str, Command] = {}
        # alias -> (nome do comando, argumentos pré-definidos)
        self.aliases: dict[str, tuple[str, tuple]] = {}
        self.current_module = ""

    # ------------------------------------------------------------- registro
    def _claim(self, name: str) -> str:
        key = norm(name)
        if key in self.commands or key in self.aliases:
            raise DuplicateCommandError(f"nome duplicado: '{key}'")
        return key

    def register(self, cmd: Command) -> Command:
        if cmd.category not in CATEGORIES:
            raise ValueError(f"categoria desconhecida: {cmd.category}")
        cmd.name = self._claim(cmd.name)
        cmd.module = cmd.module or self.current_module
        self.commands[cmd.name] = cmd
        for alias in cmd.aliases:
            self.add_alias(alias, cmd.name)
        return cmd

    def command(self, name: str, *, category: str, description: str, **kw):
        def deco(fn):
            self.register(Command(name=name, handler=fn, category=category, description=description,
                                  aliases=tuple(kw.pop("aliases", ())), **kw))
            return fn
        return deco

    def add_alias(self, alias: str, target: str, preset: tuple = ()) -> None:
        key = self._claim(alias)
        if norm(target) not in self.commands:
            raise ValueError(f"comando alvo inexistente: {target}")
        self.aliases[key] = (norm(target), tuple(preset))

    # ---------------------------------------------------------------- busca
    def resolve(self, name: str):
        """Retorna (Command, argumentos_pré-definidos) ou None."""
        key = norm(name)
        if key in self.commands:
            return self.commands[key], ()
        if key in self.aliases:
            target, preset = self.aliases[key]
            return self.commands[target], preset
        return None

    def suggest(self, name: str, limit: int = 3) -> list[str]:
        pool = list(self.commands) + [a for a, (t, p) in self.aliases.items() if not p]
        return difflib.get_close_matches(norm(name), pool, n=limit, cutoff=0.6)

    def search(self, query: str, limit: int = 15) -> list[Command]:
        q = norm(query).strip()
        if not q:
            return []
        scored = []
        for cmd in self.commands.values():
            names = [cmd.name, *[norm(a) for a in cmd.aliases]]
            score = 0
            if q == cmd.name or q in names:
                score = 100
            elif any(n.startswith(q) for n in names):
                score = 80
            elif any(q in n for n in names):
                score = 60
            elif q in norm(cmd.description):
                score = 40
            elif q in norm(cmd.category) or q in norm(cmd.subcategory):
                score = 20
            if score:
                scored.append((-score, cmd.name, cmd))
        scored.sort(key=lambda t: t[:2])
        return [c for _, _, c in scored[:limit]]

    # ------------------------------------------------------------ estatística
    def by_category(self, include_hidden: bool = False) -> dict[str, list[Command]]:
        out: dict[str, list[Command]] = {}
        for cmd in sorted(self.commands.values(), key=lambda c: c.name):
            if cmd.hidden and not include_hidden:
                continue
            out.setdefault(cmd.category, []).append(cmd)
        return {k: out[k] for k in CATEGORIES if k in out}

    def modules(self) -> dict[str, list[Command]]:
        out: dict[str, list[Command]] = {}
        for cmd in self.commands.values():
            out.setdefault(cmd.module, []).append(cmd)
        return out

    def counts(self) -> dict:
        extra = sum(1 for a, (t, p) in self.aliases.items() if p)
        simple = len(self.aliases) - extra
        return {
            "comandos": len(self.commands),
            "aliases": simple,
            "atalhos": extra,
            "total_nomes": len(self.commands) + len(self.aliases),
        }

    def validate(self) -> list[str]:
        problems = []
        for cmd in self.commands.values():
            if not cmd.description.strip():
                problems.append(f"{cmd.name}: sem descrição")
            if not callable(cmd.handler):
                problems.append(f"{cmd.name}: handler inválido")
        for alias, (target, _) in self.aliases.items():
            if target not in self.commands:
                problems.append(f"alias {alias}: alvo '{target}' não existe")
        return problems


def load_plugins(registry: Registry | None = None, package: str = "nicolas.plugins", only: list | None = None) -> Registry:
    """Descobre e carrega automaticamente todo módulo do pacote de plugins que tenha setup(reg)."""
    registry = registry or Registry()
    pkg = importlib.import_module(package)
    for info in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda i: i.name):
        if info.name.startswith("_") or (only and info.name not in only):
            continue
        mod = importlib.import_module(f"{package}.{info.name}")
        setup = getattr(mod, "setup", None)
        if setup is None:
            continue
        registry.current_module = info.name
        setup(registry)
    registry.current_module = ""
    return registry
