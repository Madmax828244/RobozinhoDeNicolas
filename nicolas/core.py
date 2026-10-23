"""Estruturas de dados trocadas entre a ponte da plataforma e o bot."""
from __future__ import annotations

from dataclasses import dataclass, field, fields


@dataclass
class Message:
    chat_id: str
    sender: str
    text: str = ""
    is_group: bool = True
    sender_name: str = ""
    sender_is_admin: bool = False
    bot_is_admin: bool = False
    bot_id: str = ""
    mentioned: list = field(default_factory=list)
    quoted_sender: str | None = None
    message_id: str = ""
    timestamp: float = 0.0
    group_name: str = ""
    group_admins: list = field(default_factory=list)
    group_size: int = 0
    from_me: bool = False
    media: list = field(default_factory=list)  # [{kind: audio|image, mime, data (base64), seconds}]
    esperto_job: object = field(default=None, repr=False, compare=False)

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in names})


@dataclass
class Event:
    """Entrada/saída de participantes."""
    type: str  # "join" | "leave"
    chat_id: str
    users: list = field(default_factory=list)
    group_name: str = ""
    bot_is_admin: bool = False
    group_admins: list = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Event":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in names})


@dataclass
class Reply:
    text: str = ""
    mentions: list = field(default_factory=list)
    actions: list = field(default_factory=list)
    image_base64: str | None = None
    audio_base64: str | None = None
    audio_mimetype: str = "audio/ogg; codecs=opus"
    ptt: bool = True
    quote: bool = True

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "mentions": list(self.mentions),
            "actions": list(self.actions),
            "image_base64": self.image_base64,
            "audio_base64": self.audio_base64,
            "audio_mimetype": self.audio_mimetype,
            "ptt": self.ptt,
            "quote": self.quote,
        }


class CommandError(Exception):
    """Erro amigável: a mensagem é mostrada ao usuário."""
