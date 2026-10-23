"""Jogos individuais e multiplayer. Recompensas são moedas virtuais, com teto diário."""
from __future__ import annotations

from ..achievements import award
from ..core import CommandError
from ..data import CHARADAS, QUIZ
from ..registry import ROLE_ADMIN
from ..utils import norm, num, tag

DAILY_GAME_CAP = 300  # teto de moedas ganhas em jogos por dia (evita exploração)
QUIZ_TIMEOUT = 60
VELHA_TIMEOUT = 600
KEYCAPS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
LINES = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]


def reward_game(ctx, uid: str, amount: int, kind: str) -> int:
    """Paga a recompensa respeitando o teto diário. Retorna o valor realmente pago."""
    earned = ctx.db.get_progress(uid, ctx.today).get("ganho_jogos", 0)
    pay = max(0, min(amount, DAILY_GAME_CAP - earned))
    if pay:
        ctx.db.add_coins(uid, pay, f"jogo:{kind}", ctx.now)
        ctx.db.add_progress(uid, ctx.today, "ganho_jogos", pay)
    return pay


def _reward_text(paid: int, wanted: int) -> str:
    if paid == wanted:
        return f"+{paid} moedas virtuais"
    return f"+{paid} moedas virtuais (teto diário de jogos atingido)" if paid else "sem moedas (teto diário de jogos atingido)"


def render_board(board) -> str:
    cells = [("❌" if c == "x" else "⭕" if c == "o" else KEYCAPS[i]) for i, c in enumerate(board)]
    return "\n".join("".join(cells[r * 3:(r + 1) * 3]) for r in range(3))


def winner_of(board):
    for a, b, c in LINES:
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]
    return "empate" if all(board) else None


def setup(reg):
    J = dict(category="jogos")

    # ------------------------------------------------------------------ quiz
    @reg.command("quiz", description="Pergunta de conhecimentos gerais (todos podem responder)", aliases=("pergunta",),
                 cooldown=3, **J)
    def quiz(ctx):
        state = ctx.db.game_get(ctx.chat, "quiz")
        if state and ctx.now - state["ts"] < QUIZ_TIMEOUT:
            q, opts = QUIZ[state["q"]][0], state["opts"]
        else:
            idx = ctx.bot.rng.randrange(len(QUIZ))
            q, options, correct = QUIZ[idx]
            order = list(range(4))
            ctx.bot.rng.shuffle(order)
            opts = [options[i] for i in order]
            state = {"q": idx, "opts": opts, "correct": order.index(correct), "ts": ctx.now, "tried": []}
            ctx.db.game_set(ctx.chat, "quiz", state, ctx.now)
        lines = ["🧠 *Quiz!*", q, ""] + [f"{'abcd'[i]}) {o}" for i, o in enumerate(opts)]
        lines.append(f"\nResponda com *{ctx.prefix}resp a|b|c|d* em até {QUIZ_TIMEOUT}s. Vale 15 moedas virtuais!")
        return "\n".join(lines)

    @reg.command("resp", description="Responde ao quiz atual", usage="a|b|c|d", example="resp b", min_args=1,
                 aliases=("r",), **J)
    def resp(ctx):
        state = ctx.db.game_get(ctx.chat, "quiz")
        if not state:
            return f"ℹ️ Não há quiz ativo. Use {ctx.prefix}quiz."
        letter = norm(ctx.args[0])[:1]
        if letter not in "abcd" or len(norm(ctx.args[0])) != 1:
            raise CommandError("Responda com a, b, c ou d.")
        right = QUIZ[state["q"]][1][QUIZ[state["q"]][2]]
        if ctx.now - state["ts"] > QUIZ_TIMEOUT:
            ctx.db.game_del(ctx.chat, "quiz")
            return f"⌛ Tempo esgotado! A resposta era *{right}*."
        me = num(ctx.sender)
        if me in state["tried"]:
            return "🙅 Você já tentou nesta pergunta. Aguarde a próxima!"
        if "abcd".index(letter) == state["correct"]:
            ctx.db.game_del(ctx.chat, "quiz")
            paid = reward_game(ctx, ctx.sender, 15, "quiz")
            ctx.db.add_xp(ctx.chat, ctx.sender, 10)
            ctx.db.add_progress(ctx.sender, ctx.today, "quiz")
            note = award(ctx.db, ctx.sender, "sabichao", ctx.now)
            text = f"✅ {tag(ctx.sender)} acertou! A resposta era *{right}*. {_reward_text(paid, 15)} e +10 XP."
            return ctx.reply(text + (f"\n{note}" if note else ""), mentions=[ctx.sender])
        state["tried"].append(me)
        ctx.db.game_set(ctx.chat, "quiz", state, ctx.now)
        return ctx.reply(f"❌ {tag(ctx.sender)}, não foi essa. Os outros ainda podem tentar!", mentions=[ctx.sender])

    # ------------------------------------------------------------ adivinhação
    @reg.command("adivinhar", description="Inicia o jogo de adivinhar o número secreto", usage="[máximo 10-1000]",
                 example="adivinhar 100", cooldown=30, **J)
    def adivinhar(ctx):
        state = ctx.db.game_get(ctx.chat + ":" + num(ctx.sender), "adivinhar")
        if state and ctx.now - state["ts"] < 600:
            return f"🔮 Você já tem um jogo ativo (1 a {state['max']}). Use {ctx.prefix}chute <número>."
        top = 100
        if ctx.args:
            if not ctx.args[0].isdigit() or not 10 <= int(ctx.args[0]) <= 1000:
                raise CommandError("O máximo deve ser um número de 10 a 1000.")
            top = int(ctx.args[0])
        ctx.db.game_set(ctx.chat + ":" + num(ctx.sender), "adivinhar",
                        {"n": ctx.bot.rng.randint(1, top), "max": top, "tries": 0, "ts": ctx.now}, ctx.now)
        return f"🔮 Pensei em um número de 1 a {top}. Você tem 10 chutes! Use *{ctx.prefix}chute <número>*."

    @reg.command("chute", description="Dá um palpite no jogo de adivinhação", usage="<número>", example="chute 42",
                 min_args=1, **J)
    def chute(ctx):
        key = ctx.chat + ":" + num(ctx.sender)
        state = ctx.db.game_get(key, "adivinhar")
        if not state:
            return f"ℹ️ Você não tem jogo ativo. Use {ctx.prefix}adivinhar."
        try:
            guess = int(ctx.args[0])
        except ValueError:
            raise CommandError("Informe um número inteiro.")
        state["tries"] += 1
        if guess == state["n"]:
            ctx.db.game_del(key, "adivinhar")
            want = max(10, 50 - 5 * state["tries"])
            paid = reward_game(ctx, ctx.sender, want, "adivinhar")
            note = award(ctx.db, ctx.sender, "adivinhador", ctx.now)
            return f"🎉 Acertou em {state['tries']} tentativa(s)! Era *{state['n']}*. {_reward_text(paid, want)}." + (f"\n{note}" if note else "")
        if state["tries"] >= 10:
            ctx.db.game_del(key, "adivinhar")
            return f"💥 Acabaram os chutes! O número era *{state['n']}*."
        ctx.db.game_set(key, "adivinhar", state, ctx.now)
        hint = "maior ⬆️" if guess < state["n"] else "menor ⬇️"
        return f"O número secreto é {hint}. Chutes restantes: {10 - state['tries']}."

    # -------------------------------------------------------- pedra/papel/tesoura
    @reg.command("ppt", description="Pedra, papel e tesoura contra o bot", usage="pedra|papel|tesoura",
                 example="ppt pedra", min_args=1, aliases=("pedrapapeltesoura",), **J)
    def ppt(ctx):
        names = {"pedra": "🪨", "papel": "📄", "tesoura": "✂️"}
        mine = norm(ctx.args[0])
        if mine not in names:
            raise CommandError("Escolha pedra, papel ou tesoura.")
        bot = ctx.bot.rng.choice(list(names))
        beats = {"pedra": "tesoura", "papel": "pedra", "tesoura": "papel"}
        if mine == bot:
            result = "🤝 Empate!"
        elif beats[mine] == bot:
            result = "🎉 Você venceu!"
        else:
            result = "😎 Eu venci!"
        return f"Você: {names[mine]}  ×  Eu: {names[bot]}\n{result}"

    # ----------------------------------------------------------------- charadas
    @reg.command("charada", description="Propõe uma charada ou enigma", aliases=("enigma",), cooldown=3, **J)
    def charada(ctx):
        state = ctx.db.game_get(ctx.chat, "charada")
        if not state or ctx.now - state["ts"] > 600:
            q, a = ctx.bot.rng.choice(CHARADAS)
            state = {"q": q, "a": a, "ts": ctx.now}
            ctx.db.game_set(ctx.chat, "charada", state, ctx.now)
        return f"🧩 *Charada*\n{state['q']}\n\nResponda com *{ctx.prefix}rc <resposta>* ou desista com *{ctx.prefix}revelar*."

    @reg.command("rc", description="Responde à charada atual", usage="<resposta>", example="rc buraco", min_args=1, **J)
    def rc(ctx):
        state = ctx.db.game_get(ctx.chat, "charada")
        if not state:
            return f"ℹ️ Não há charada ativa. Use {ctx.prefix}charada."
        guess = norm(ctx.raw).strip(" ?!.")
        answer = norm(state["a"])
        if guess == answer or (len(guess) >= 4 and (guess in answer or answer in guess)):
            ctx.db.game_del(ctx.chat, "charada")
            paid = reward_game(ctx, ctx.sender, 15, "charada")
            return ctx.reply(f"✅ {tag(ctx.sender)} acertou! Era *{state['a']}*. {_reward_text(paid, 15)}.",
                             mentions=[ctx.sender])
        return "❌ Não é isso. Tente de novo!"

    @reg.command("revelar", description="Revela a resposta da charada atual", **J)
    def revelar(ctx):
        state = ctx.db.game_get(ctx.chat, "charada")
        if not state:
            return "ℹ️ Não há charada ativa."
        ctx.db.game_del(ctx.chat, "charada")
        return f"🔓 A resposta era: *{state['a']}*."

    # -------------------------------------------------------------- jogo da velha
    @reg.command("velha", description="Jogo da velha multiplayer: desafie alguém", usage="@usuário | cancelar",
                 example="velha @5511999999999", group_only=True, **J)
    def velha(ctx):
        state = ctx.db.game_get(ctx.chat, "velha")
        active = state is not None and ctx.now - state["updated"] < VELHA_TIMEOUT
        if ctx.args and norm(ctx.args[0]) in {"cancelar", "parar"}:
            if not state:
                return "ℹ️ Não há partida em andamento."
            players = {num(state["x"]), num(state["o"])}
            if num(ctx.sender) not in players and ctx.role < ROLE_ADMIN:
                raise CommandError("Só os jogadores ou administradores podem cancelar.")
            ctx.db.game_del(ctx.chat, "velha")
            return "🛑 Partida cancelada."
        if active:
            return f"⏳ Já há uma partida em andamento:\n{render_board(state['board'])}\nVez de {tag(state['x'] if state['turn'] == 'x' else state['o'])}."
        opp = ctx.target()
        if not opp:
            raise CommandError(f"Marque quem você quer desafiar. Ex.: {ctx.prefix}velha @5511999999999")
        if num(opp) == num(ctx.sender):
            raise CommandError("Você não pode jogar contra si mesmo.")
        if num(opp) == num(ctx.msg.bot_id):
            raise CommandError("Eu só assisto! Chame uma pessoa.")
        state = {"board": [""] * 9, "x": ctx.sender, "o": opp, "turn": "x", "updated": ctx.now}
        ctx.db.game_set(ctx.chat, "velha", state, ctx.now)
        return ctx.reply(f"❌⭕ *Jogo da velha*\n{tag(ctx.sender)} (❌) vs {tag(opp)} (⭕)\n\n{render_board(state['board'])}\n\n"
                         f"Vez de {tag(ctx.sender)}. Jogue com *{ctx.prefix}jogar 1-9*.", mentions=[ctx.sender, opp])

    @reg.command("jogar", description="Faz uma jogada no jogo da velha", usage="<1-9>", example="jogar 5", min_args=1,
                 group_only=True, **J)
    def jogar(ctx):
        state = ctx.db.game_get(ctx.chat, "velha")
        if not state:
            return f"ℹ️ Não há partida. Use {ctx.prefix}velha @usuário."
        turn_player = state["x"] if state["turn"] == "x" else state["o"]
        if num(ctx.sender) not in {num(state["x"]), num(state["o"])}:
            raise CommandError("Você não está nesta partida.")
        if num(ctx.sender) != num(turn_player):
            raise CommandError("Ainda não é a sua vez.")
        if not ctx.args[0].isdigit() or not 1 <= int(ctx.args[0]) <= 9:
            raise CommandError("Escolha uma casa de 1 a 9.")
        pos = int(ctx.args[0]) - 1
        if state["board"][pos]:
            raise CommandError("Essa casa já está ocupada.")
        state["board"][pos] = state["turn"]
        result = winner_of(state["board"])
        board = render_board(state["board"])
        if result in ("x", "o"):
            ctx.db.game_del(ctx.chat, "velha")
            paid = reward_game(ctx, ctx.sender, 25, "velha")
            note = award(ctx.db, ctx.sender, "mestre_velha", ctx.now)
            return ctx.reply(f"{board}\n\n🏆 {tag(ctx.sender)} venceu! {_reward_text(paid, 25)}." + (f"\n{note}" if note else ""),
                             mentions=[ctx.sender])
        if result == "empate":
            ctx.db.game_del(ctx.chat, "velha")
            return f"{board}\n\n🤝 Empate!"
        state["turn"] = "o" if state["turn"] == "x" else "x"
        state["updated"] = ctx.now
        ctx.db.game_set(ctx.chat, "velha", state, ctx.now)
        nxt = state["x"] if state["turn"] == "x" else state["o"]
        return ctx.reply(f"{board}\n\nVez de {tag(nxt)}.", mentions=[nxt])
