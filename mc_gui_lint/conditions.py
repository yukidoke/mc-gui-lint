from __future__ import annotations

import ast
import re
from typing import Any


def _snake(name: str) -> str:
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return name.lower()


def normalize_java_condition(expr: str) -> str | None:
    """Translate a deliberately small Java boolean expression into a safe IR.

    Supported forms are intended for GUI visibility checks, for example::

        menu.isWorking()
        menu.getPower() > 0
        !menu.isBroken() && menu.getPower() > 0

    The returned expression contains only Python-style literals/operators and
    simple state names. Unsupported Java syntax returns ``None`` rather than
    guessing.
    """

    text = expr.strip()
    if not text:
        return None

    # Common Screen/Menu no-argument state accessors.
    text = re.sub(
        r"\b(?:this\.)?menu\s*\.\s*get([A-Z][A-Za-z0-9_]*)\s*\(\s*\)",
        lambda m: _snake(m.group(1)),
        text,
    )
    text = re.sub(
        r"\b(?:this\.)?menu\s*\.\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*\)",
        lambda m: _snake(m.group(1)),
        text,
    )
    text = re.sub(
        r"\b(?:this\.)?get([A-Z][A-Za-z0-9_]*)\s*\(\s*\)",
        lambda m: _snake(m.group(1)),
        text,
    )
    text = re.sub(
        r"\bthis\s*\.\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*\)",
        lambda m: _snake(m.group(1)),
        text,
    )
    text = re.sub(
        r"\b((?:is|has|can|should)[A-Z][A-Za-z0-9_]*)\s*\(\s*\)",
        lambda m: _snake(m.group(1)),
        text,
    )

    # Simple fields are useful for Screens that mirror Menu state locally.
    text = re.sub(
        r"\b(?:this\.)?menu\s*\.\s*([A-Za-z_][A-Za-z0-9_]*)\b",
        lambda m: _snake(m.group(1)),
        text,
    )
    text = re.sub(
        r"\bthis\s*\.\s*([A-Za-z_][A-Za-z0-9_]*)\b",
        lambda m: _snake(m.group(1)),
        text,
    )

    text = text.replace("&&", " and ").replace("||", " or ")
    text = re.sub(r"!(?!=)", " not ", text)
    text = re.sub(r"\btrue\b", "True", text, flags=re.I)
    text = re.sub(r"\bfalse\b", "False", text, flags=re.I)
    text = re.sub(r"\bnull\b", "None", text)
    text = re.sub(r"(?<=\d)[lLfFdD]\b", "", text)
    text = re.sub(r"\s+", " ", text).strip()

    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError:
        return None
    if not _condition_ast_supported(tree):
        return None
    return text


def _condition_ast_supported(tree: ast.AST) -> bool:
    allowed = (
        ast.Expression,
        ast.BoolOp,
        ast.And,
        ast.Or,
        ast.UnaryOp,
        ast.Not,
        ast.USub,
        ast.UAdd,
        ast.Compare,
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
        ast.Name,
        ast.Load,
        ast.Constant,
        ast.BinOp,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
    )
    return all(isinstance(node, allowed) for node in ast.walk(tree))


def bind_numeric_constants(expr: str, env: dict[str, int | float]) -> str:
    """Replace normalized condition names that are known numeric constants."""

    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return expr

    class Binder(ast.NodeTransformer):
        def visit_Name(self, node: ast.Name) -> ast.AST:
            value = env.get(node.id)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return ast.copy_location(ast.Constant(value=value), node)
            return node

    bound = Binder().visit(tree)
    ast.fix_missing_locations(bound)
    try:
        return ast.unparse(bound.body)
    except Exception:
        return expr


def condition_names(expr: str) -> set[str]:
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return set()
    return {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}


def evaluate_state_condition(expr: str, state: dict[str, Any]) -> bool | None:
    """Evaluate a normalized visibility expression against state.

    Missing state is intentionally reported as ``None``. Callers should keep
    the element visible in that case so static analysis never hides content on
    the basis of an assumption.
    """

    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return None
    if not _condition_ast_supported(tree):
        return None
    if any(name not in state for name in condition_names(expr)):
        return None
    try:
        return bool(_eval_node(tree.body, state))
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _eval_node(node: ast.AST, state: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return state[node.id]
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            for child in node.values:
                if not bool(_eval_node(child, state)):
                    return False
            return True
        for child in node.values:
            if bool(_eval_node(child, state)):
                return True
        return False
    if isinstance(node, ast.UnaryOp):
        value = _eval_node(node.operand, state)
        if isinstance(node.op, ast.Not):
            return not bool(value)
        if isinstance(node.op, ast.USub):
            return -value
        if isinstance(node.op, ast.UAdd):
            return +value
        raise ValueError("unsupported unary operator")
    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, state)
        right = _eval_node(node.right, state)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, (ast.Div, ast.FloorDiv)):
            if right == 0:
                raise ZeroDivisionError
            if isinstance(left, int) and isinstance(right, int):
                return int(left / right)
            return left / right
        if isinstance(node.op, ast.Mod):
            return left % right
        raise ValueError("unsupported binary operator")
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, state)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval_node(comparator, state)
            if isinstance(op, ast.Eq):
                ok = left == right
            elif isinstance(op, ast.NotEq):
                ok = left != right
            elif isinstance(op, ast.Lt):
                ok = left < right
            elif isinstance(op, ast.LtE):
                ok = left <= right
            elif isinstance(op, ast.Gt):
                ok = left > right
            elif isinstance(op, ast.GtE):
                ok = left >= right
            else:
                raise ValueError("unsupported comparison")
            if not ok:
                return False
            left = right
        return True
    raise ValueError("unsupported condition node")
