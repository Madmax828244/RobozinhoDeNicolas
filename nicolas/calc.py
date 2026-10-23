"""Calculadora segura: interpreta a expressão via AST (nunca usa eval/exec)."""
from __future__ import annotations

import ast
import math
import operator
import re

MAX_LEN = 200
OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
}
FUNCS = {
    "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "log": math.log, "log10": math.log10, "log2": math.log2, "abs": abs,
    "round": round, "floor": math.floor, "ceil": math.ceil, "exp": math.exp,
    "fatorial": math.factorial, "factorial": math.factorial,
}
CONSTS = {"pi": math.pi, "e": math.e, "tau": math.tau}


class CalcError(ValueError):
    pass


def _prepare(expr: str) -> str:
    s = expr.strip().lower()
    s = s.replace("×", "*").replace("÷", "/").replace("^", "**").replace("π", "pi")
    s = re.sub(r"(?<=\d),(?=\d)", ".", s)
    s = re.sub(r"(?<=\d)\s*x\s*(?=\d)", "*", s)
    s = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"(\1/100)", s)
    return s


def calculate(expr: str):
    if not expr or len(expr) > MAX_LEN:
        raise CalcError("Expressão vazia ou longa demais (máx. 200 caracteres).")
    try:
        tree = ast.parse(_prepare(expr), mode="eval")
    except SyntaxError:
        raise CalcError("Não entendi a expressão. Exemplo: 2*(3+4)/5") from None

    def ev(node, depth=0):
        if depth > 40:
            raise CalcError("Expressão complexa demais.")
        if isinstance(node, ast.Expression):
            return ev(node.body, depth + 1)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise CalcError("Só números são permitidos.")
            return node.value
        if isinstance(node, ast.Name):
            if node.id in CONSTS:
                return CONSTS[node.id]
            raise CalcError(f"'{node.id}' não é reconhecido.")
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            v = ev(node.operand, depth + 1)
            return -v if isinstance(node.op, ast.USub) else v
        if isinstance(node, ast.BinOp):
            left, right = ev(node.left, depth + 1), ev(node.right, depth + 1)
            if isinstance(node.op, ast.Pow):
                if abs(right) > 1000 or (isinstance(left, int) and isinstance(right, int)
                                         and right > 0 and left != 0 and abs(left).bit_length() * right > 4000):
                    raise CalcError("Potência grande demais.")
                return left ** right
            op = OPS.get(type(node.op))
            if not op:
                raise CalcError("Operador não permitido.")
            return op(left, right)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCS and not node.keywords:
            if len(node.args) > 2:
                raise CalcError("Argumentos demais.")
            args = [ev(a, depth + 1) for a in node.args]
            if node.func.id in {"fatorial", "factorial"}:
                if len(args) != 1 or args[0] != int(args[0]) or not 0 <= args[0] <= 500:
                    raise CalcError("Fatorial: use um inteiro de 0 a 500.")
                return math.factorial(int(args[0]))
            return FUNCS[node.func.id](*args)
        raise CalcError("Expressão não permitida.")

    try:
        result = ev(tree)
    except ZeroDivisionError:
        raise CalcError("Divisão por zero.") from None
    except (ValueError, OverflowError, TypeError):
        raise CalcError("Não foi possível calcular isso (valor fora do domínio ou grande demais).") from None
    return result
