"""Conquistas, medalhas, missões diárias e loja virtual (economia 100% recreativa)."""
from __future__ import annotations

ACHIEVEMENTS = {
    "primeiros_passos": ("🌱 Primeiros passos", "Enviou a primeira mensagem no grupo."),
    "tagarela": ("💬 Tagarela", "Enviou 100 mensagens em um grupo."),
    "veterano": ("🎖️ Veterano", "Chegou ao nível 5."),
    "pontual": ("⏰ Pontual", "Resgatou a primeira recompensa diária."),
    "fiel": ("🔥 Fiel", "Resgatou a recompensa diária 7 dias seguidos."),
    "rico": ("💎 Rico virtual", "Juntou 1.000 moedas virtuais."),
    "sabichao": ("🧠 Sabichão", "Acertou uma pergunta do quiz."),
    "mestre_velha": ("❌ Mestre da velha", "Venceu uma partida de jogo da velha."),
    "adivinhador": ("🔮 Adivinhador", "Acertou o número secreto."),
    "comprador": ("🛍️ Comprador", "Fez a primeira compra na loja."),
    "missionario": ("📜 Missionário", "Resgatou uma missão diária."),
}

DAILY_MISSIONS = [
    # id, descrição, chave de progresso, meta, recompensa
    ("msgs20", "Enviar 20 mensagens", "msgs", 20, 50),
    ("cmds5", "Usar 5 comandos", "cmds", 5, 40),
    ("quiz1", "Acertar 1 pergunta do quiz", "quiz", 1, 60),
]

SHOP = {
    "pao": ("🥖 Pão quentinho", 30, "Item colecionável."),
    "trofeu": ("🏆 Troféu", 500, "Para exibir no perfil."),
    "coroa": ("👑 Coroa", 2000, "Item raro de coleção."),
    "gato": ("🐱 Gatinho virtual", 300, "Um companheiro fofo."),
    "foguete": ("🚀 Foguete", 1200, "Item colecionável."),
    "titulo_lenda": ("🌟 Título: Lenda", 800, "Libera o título 'Lenda' (.titulo Lenda)."),
    "titulo_mestre": ("🎓 Título: Mestre", 600, "Libera o título 'Mestre' (.titulo Mestre)."),
}
TITLES = {"Lenda": "titulo_lenda", "Mestre": "titulo_mestre"}


def award(db, uid: str, key: str, now: float) -> str:
    """Concede a conquista e devolve o aviso (ou string vazia se já tinha)."""
    if key in ACHIEVEMENTS and db.grant_achievement(uid, key, now):
        name, _ = ACHIEVEMENTS[key]
        return f"🏅 Conquista desbloqueada: {name}!"
    return ""
