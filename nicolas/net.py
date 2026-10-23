"""Cliente HTTP mínimo (stdlib) com limites de tempo e tamanho."""
from __future__ import annotations

import json
import ipaddress
import urllib.error
import urllib.parse
import urllib.request

MAX_BYTES = 1_000_000
USER_AGENT = "RoboNicolas/1.0 (+bot de grupos)"


class NetError(Exception):
    """Falha de rede/serviço externo. A mensagem é segura para exibir (sem segredos)."""

    def __init__(self, message: str = "", status: int | None = None):
        super().__init__(message)
        self.status = status  # código HTTP, quando houver


def _is_local(url: str) -> bool:
    host = urllib.parse.urlparse(url).hostname or ""
    return host in {"localhost", "127.0.0.1", "::1"}


def _is_private_ip(url: str) -> bool:
    host = urllib.parse.urlparse(url).hostname or ""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local


def request_json(url: str, *, data=None, headers: dict | None = None, timeout: float = 12, method: str | None = None,
                 max_bytes: int = MAX_BYTES, allow_insecure_private: bool = False):
    """HTTPS por padrão. HTTP é aceito em loopback; IPs privados exigem opt-in explícito."""
    parsed = urllib.parse.urlparse(url)
    local_http = parsed.scheme == "http" and _is_local(url)
    private_http = parsed.scheme == "http" and allow_insecure_private and _is_private_ip(url)
    if parsed.scheme != "https" and not (local_http or private_http):
        if parsed.scheme == "http" and _is_private_ip(url):
            raise NetError("API HTTP na rede local bloqueada; reconfigure com --permitir-http-rede somente se confiar na rede.")
        raise NetError("Somente conexões HTTPS são permitidas, exceto APIs locais autorizadas.")
    body = json.dumps(data).encode() if data is not None else None
    hdrs = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if body is not None:
        hdrs["Content-Type"] = "application/json"
    hdrs.update(headers or {})
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(max_bytes + 1)
    except urllib.error.HTTPError as exc:
        raise NetError(f"o serviço respondeu com erro HTTP {exc.code}", exc.code) from None
    except TimeoutError:
        raise NetError("o serviço demorou demais para responder") from None
    except (urllib.error.URLError, OSError):
        raise NetError("não foi possível conectar ao serviço") from None
    if len(raw) > max_bytes:
        raise NetError("resposta grande demais")
    try:
        return json.loads(raw)
    except ValueError:
        raise NetError("resposta inválida do serviço") from None


def post_multipart(url: str, *, fields: dict, file_field: str, filename: str, content: bytes, mime: str,
                   headers: dict | None = None, timeout: float = 60, max_bytes: int = MAX_BYTES):
    """POST multipart/form-data (usado para enviar áudio à transcrição). Devolve o JSON da resposta."""
    import uuid
    if urllib.parse.urlparse(url).scheme != "https":
        raise NetError("Somente conexões HTTPS são permitidas.")
    boundary = uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
                 f"Content-Type: {mime}\r\n\r\n".encode() + content + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    hdrs = {"User-Agent": USER_AGENT, "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}"}
    hdrs.update(headers or {})
    req = urllib.request.Request(url, data=b"".join(parts), headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(max_bytes + 1)
    except urllib.error.HTTPError as exc:
        raise NetError(f"o serviço respondeu com erro HTTP {exc.code}", exc.code) from None
    except TimeoutError:
        raise NetError("o serviço demorou demais para responder") from None
    except (urllib.error.URLError, OSError):
        raise NetError("não foi possível conectar ao serviço") from None
    try:
        return json.loads(raw)
    except ValueError:
        raise NetError("resposta inválida do serviço") from None


def request_bytes(url: str, *, data=None, headers: dict | None = None, timeout: float = 60,
                  max_bytes: int = 15_000_000) -> bytes:
    """POST JSON que devolve BYTES (ex.: áudio de uma API de voz). Somente HTTPS."""
    if urllib.parse.urlparse(url).scheme != "https":
        raise NetError("Somente conexões HTTPS são permitidas.")
    hdrs = {"User-Agent": USER_AGENT, "Content-Type": "application/json"}
    hdrs.update(headers or {})
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(max_bytes + 1)
    except urllib.error.HTTPError as exc:
        raise NetError(f"o serviço respondeu com erro HTTP {exc.code}", exc.code) from None
    except TimeoutError:
        raise NetError("o serviço demorou demais para responder") from None
    except (urllib.error.URLError, OSError):
        raise NetError("não foi possível conectar ao serviço") from None
    if len(raw) > max_bytes or not raw:
        raise NetError("resposta de áudio inválida")
    return raw
