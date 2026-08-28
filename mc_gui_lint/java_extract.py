
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ExtractionWarning:
    code: str
    message: str
    line: int | None = None

    def format(self) -> str:
        where = f" line {self.line}" if self.line is not None else ""
        return f"{self.code}{where}: {self.message}"


def _strip_comments(code: str) -> str:
    # Keep newlines so approximate line numbers survive.
    code = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), code, flags=re.S)
    code = re.sub(r"//[^\n]*", "", code)
    return code


def _line_of(code: str, offset: int) -> int:
    return code.count("\n", 0, offset) + 1


def _snake(name: str) -> str:
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return name.lower()


class JavaIntEvaluator:
    """Very small evaluator for integer-ish Java coordinate expressions."""

    def __init__(self, env: dict[str, int] | None = None):
        self.env = dict(env or {})
        self.env.setdefault("leftPos", 0)
        self.env.setdefault("topPos", 0)
        self.env.setdefault("imageWidth", self.env.get("imageWidth", 176))
        self.env.setdefault("imageHeight", self.env.get("imageHeight", 166))

    def eval(self, expr: str) -> int:
        expr = expr.strip()
        expr = re.sub(r"\bthis\.", "", expr)
        expr = re.sub(r"\((?:int|long|short|byte)\)\s*", "", expr)
        expr = re.sub(r"(?<=\d)[lLfFdD]\b", "", expr)
        expr = expr.replace("Math.max", "max").replace("Math.min", "min")

        tree = ast.parse(expr, mode="eval")
        value = self._eval_node(tree.body)
        return int(value)

    def _eval_node(self, node: ast.AST) -> int:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return int(node.value)

        if isinstance(node, ast.Name):
            if node.id not in self.env:
                raise ValueError(f"unknown name {node.id}")
            return int(self.env[node.id])

        if isinstance(node, ast.UnaryOp):
            value = self._eval_node(node.operand)
            if isinstance(node.op, ast.USub):
                return -value
            if isinstance(node.op, ast.UAdd):
                return value
            raise ValueError("unsupported unary operator")

        if isinstance(node, ast.BinOp):
            a = self._eval_node(node.left)
            b = self._eval_node(node.right)
            if isinstance(node.op, ast.Add):
                return a + b
            if isinstance(node.op, ast.Sub):
                return a - b
            if isinstance(node.op, ast.Mult):
                return a * b
            if isinstance(node.op, ast.Div):
                if b == 0:
                    raise ValueError("division by zero")
                # Java integer division truncates toward zero.
                return int(a / b)
            if isinstance(node.op, ast.FloorDiv):
                if b == 0:
                    raise ValueError("division by zero")
                return int(a / b)
            if isinstance(node.op, ast.Mod):
                return a % b
            raise ValueError("unsupported binary operator")

        if isinstance(node, ast.Attribute):
            parts: list[str] = []
            current: ast.AST = node
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
                qualified = ".".join(reversed(parts))
                if qualified in self.env:
                    return int(self.env[qualified])
            raise ValueError(
                f"unknown qualified name {ast.unparse(node) if hasattr(ast, 'unparse') else ast.dump(node)}"
            )

        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            args = [self._eval_node(a) for a in node.args]
            if node.func.id == "max":
                return max(args)
            if node.func.id == "min":
                return min(args)

        raise ValueError(f"unsupported expression: {ast.dump(node, include_attributes=False)}")


def _matching(code: str, open_pos: int, opener: str = "(", closer: str = ")") -> int:
    depth = 0
    quote: str | None = None
    escaped = False
    for i in range(open_pos, len(code)):
        ch = code[i]
        if quote is not None:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            continue

        if ch in ('"', "'"):
            quote = ch
            continue
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return i
    raise ValueError(f"unmatched {opener}")


def _split_args(text: str) -> list[str]:
    result: list[str] = []
    start = 0
    depth = 0
    quote: str | None = None
    escaped = False

    pairs = {")": "(", "]": "[", "}": "{"}
    stack: list[str] = []

    for i, ch in enumerate(text):
        if quote is not None:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            continue

        if ch in ('"', "'"):
            quote = ch
            continue
        if ch in "([{":
            stack.append(ch)
        elif ch in ")]}":
            if stack and stack[-1] == pairs[ch]:
                stack.pop()
        elif ch == "," and not stack:
            result.append(text[start:i].strip())
            start = i + 1

    last = text[start:].strip()
    if last:
        result.append(last)
    return result


def _find_calls(code: str, names: tuple[str, ...]):
    """Yield (name, start, open_paren, close_paren, arg_text)."""
    pattern = re.compile(r"\b(" + "|".join(re.escape(n) for n in names) + r")\s*\(")
    for match in pattern.finditer(code):
        name = match.group(1)
        open_pos = code.find("(", match.start())
        try:
            close_pos = _matching(code, open_pos)
        except ValueError:
            continue
        yield name, match.start(), open_pos, close_pos, code[open_pos + 1:close_pos]


def _state_placeholder(expr: str) -> str | None:
    expr = expr.strip()
    if expr == "title" or expr == "this.title":
        return "{screen_title}"
    if expr == "playerInventoryTitle" or expr == "this.playerInventoryTitle":
        return "{inventory_title}"

    getter = re.fullmatch(r"(?:this\.)?(?:menu\.)?get([A-Z][A-Za-z0-9_]*)\s*\(\s*\)", expr)
    if getter:
        return "{" + _snake(getter.group(1)) + "}"

    method = re.fullmatch(
        r"(?:this\.)?(?:menu\.)?([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*\)",
        expr,
    )
    if method:
        return "{" + _snake(method.group(1)) + "}"

    field = re.fullmatch(r"(?:this\.)?([A-Za-z_][A-Za-z0-9_]*)", expr)
    if field:
        return "{" + _snake(field.group(1)) + "}"
    return None



def _menu_state_placeholder(expr: str) -> str | None:
    """Return a state placeholder only for a no-arg Menu getter/method."""
    expr = expr.strip()

    getter = re.fullmatch(
        r"(?:this\.)?menu\.get([A-Z][A-Za-z0-9_]*)\s*\(\s*\)",
        expr,
    )
    if getter:
        return "{" + _snake(getter.group(1)) + "}"

    method = re.fullmatch(
        r"(?:this\.)?menu\.([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*\)",
        expr,
    )
    if method:
        return "{" + _snake(method.group(1)) + "}"
    return None


def _split_top_level_concat(expr: str) -> list[str]:
    """Split a Java expression on top-level ``+`` operators only."""
    parts: list[str] = []
    start = 0
    stack: list[str] = []
    quote: str | None = None
    escaped = False
    pairs = {")": "(", "]": "[", "}": "{"}

    for i, ch in enumerate(expr):
        if quote is not None:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            continue

        if ch in ('"', "'"):
            quote = ch
            continue
        if ch in "([{":
            stack.append(ch)
            continue
        if ch in ")]}":
            if stack and stack[-1] == pairs[ch]:
                stack.pop()
            continue
        if ch == "+" and not stack:
            parts.append(expr[start:i].strip())
            start = i + 1

    parts.append(expr[start:].strip())
    return [part for part in parts if part]


def _extract_dynamic_translation_key_template(expr: str) -> str | None:
    """Extract a safe dynamic translation-key template.

    Accepted form is intentionally narrow: top-level concatenation of Java
    string literals and no-arg Menu accessors, for example::

        "gui.example.formation." + menu.formation()

    becomes ``gui.example.formation.{formation}``.
    """
    parts = _split_top_level_concat(expr.strip())
    if len(parts) < 2:
        return None

    out: list[str] = []
    has_literal = False
    has_state = False
    for part in parts:
        if re.fullmatch(r'"(?:\\.|[^"\\])*"', part, flags=re.S):
            try:
                out.append(str(ast.literal_eval(part)))
            except Exception:
                return None
            has_literal = True
            continue

        placeholder = _menu_state_placeholder(part)
        if placeholder is not None:
            out.append(placeholder)
            has_state = True
            continue

        return None

    if not (has_literal and has_state):
        return None
    return "".join(out)


def _extract_dynamic_translatable_spec(expr: str) -> tuple[str, list[str]] | None:
    """Return (dynamic key template, argument templates) for translatable()."""
    expr = expr.strip()
    tm = re.fullmatch(r"(?:Component\.)?translatable\s*\((.*)\)", expr, flags=re.S)
    if not tm:
        return None

    args = _split_args(tm.group(1))
    if not args:
        return None

    key_template = _extract_dynamic_translation_key_template(args[0])
    if key_template is None:
        return None

    values: list[str] = []
    for arg in args[1:]:
        arg = arg.strip()
        ph = _state_placeholder(arg)
        if ph is not None:
            values.append(ph)
            continue
        if re.fullmatch(r'"(?:\\.|[^"\\])*"', arg, flags=re.S):
            try:
                values.append(str(ast.literal_eval(arg)))
            except Exception:
                values.append(arg.strip('"'))
            continue
        if re.fullmatch(r"-?\d+[lL]?", arg):
            values.append(re.sub(r"[lL]$", "", arg))
            continue
        values.append("{?}")
    return key_template, values


def _extract_translatable_spec(expr: str) -> tuple[str, list[str]] | None:
    """Return (translation key, argument templates) for Component.translatable."""
    expr = expr.strip()
    tm = re.fullmatch(r"(?:Component\.)?translatable\s*\((.*)\)", expr, flags=re.S)
    if not tm:
        return None

    args = _split_args(tm.group(1))
    if not args or not re.fullmatch(r'"(?:\\.|[^"\\])*"', args[0], flags=re.S):
        return None

    try:
        key = ast.literal_eval(args[0])
    except Exception:
        key = args[0].strip('"')

    values: list[str] = []
    for arg in args[1:]:
        arg = arg.strip()
        ph = _state_placeholder(arg)
        if ph is not None:
            values.append(ph)
            continue
        if re.fullmatch(r'"(?:\\.|[^"\\])*"', arg, flags=re.S):
            try:
                values.append(str(ast.literal_eval(arg)))
            except Exception:
                values.append(arg.strip('"'))
            continue
        if re.fullmatch(r"-?\d+[lL]?", arg):
            values.append(re.sub(r"[lL]$", "", arg))
            continue
        values.append("{?}")
    return str(key), values


def _extract_java_string(expr: str) -> str | None:
    expr = expr.strip()

    # Well-known AbstractContainerScreen dynamic fields.
    placeholder = _state_placeholder(expr)
    if placeholder is not None:
        return placeholder

    # Component.literal("...")
    m = re.fullmatch(r"(?:Component\.)?literal\s*\((.*)\)", expr, flags=re.S)
    if m:
        expr = m.group(1).strip()

    # Plain string literal.
    if re.fullmatch(r'"(?:\\.|[^"\\])*"', expr, flags=re.S):
        try:
            return ast.literal_eval(expr)
        except Exception:
            return expr.strip('"')

    # Component.translatable("key", args...). Without a lang file, use the
    # final key segment as a compact approximation and preserve dynamic args.
    tm = re.fullmatch(r"(?:Component\.)?translatable\s*\((.*)\)", expr, flags=re.S)
    if tm:
        args = _split_args(tm.group(1))
        if not args:
            return None
        key = None
        if re.fullmatch(r'"(?:\\.|[^"\\])*"', args[0], flags=re.S):
            try:
                key = ast.literal_eval(args[0])
            except Exception:
                key = args[0].strip('"')
        if key is None:
            dynamic = _extract_dynamic_translation_key_template(args[0])
            if dynamic is not None:
                # Keep a visible deterministic template until locale+state are known.
                return dynamic
            return None
        label = key.rsplit('.', 1)[-1].replace('_', ' ')
        dyn: list[str] = []
        for arg in args[1:]:
            ph = _state_placeholder(arg)
            if ph is not None:
                dyn.append(ph)
            else:
                dyn.append("{?}")
        if dyn:
            return label + ": " + " ".join(dyn)
        return label

    # Useful heuristic for `"Energy: " + menu.getPower() + " FE"`.
    parts = _split_top_level_concat(expr)
    if len(parts) > 1:
        out: list[str] = []
        for part in parts:
            part = part.strip()
            if re.fullmatch(r'"(?:\\.|[^"\\])*"', part, flags=re.S):
                try:
                    out.append(ast.literal_eval(part))
                except Exception:
                    out.append(part.strip('"'))
                continue
            ph = _state_placeholder(part)
            if ph is not None:
                out.append(ph)
                continue
            return None
        return "".join(out)

    return None

def _extract_class_name(code: str) -> str | None:
    match = re.search(
        r"\b(?:public\s+)?(?:final\s+)?(?:class|record)\s+([A-Za-z_]\w*)",
        code,
    )
    return match.group(1) if match else None


def _extract_public_static_final_int_constants(
    code: str,
    class_name: str | None = None,
    base_env: dict[str, int] | None = None,
) -> dict[str, int]:
    """Extract safe cross-class primitive compile-time constants.

    Only ``public static final`` integral primitives are considered. Values are
    evaluated with ``JavaIntEvaluator`` so literals and expressions composed of
    already-resolved constants are supported, while method calls and runtime
    fields remain unresolved. Returned keys include both ``FIELD`` and, when a
    class name is known, ``ClassName.FIELD``.
    """
    pattern = re.compile(
        r"\bpublic\s+static\s+final\s+"
        r"(?:int|long|short|byte)\s+([A-Za-z_]\w*)\s*=\s*([^;]+);"
    )
    declarations = [(m.group(1), m.group(2).strip()) for m in pattern.finditer(code)]
    env = dict(base_env or {})
    resolved: dict[str, int] = {}

    # Multiple passes allow constants to reference earlier/later constants in
    # the same class without interpreting arbitrary Java execution.
    for _ in range(max(1, len(declarations) + 1)):
        changed = False
        evaluator = JavaIntEvaluator(env)
        for name, expr in declarations:
            if name in resolved:
                continue
            try:
                value = evaluator.eval(expr)
            except Exception:
                continue
            resolved[name] = value
            env[name] = value
            if class_name:
                env[f"{class_name}.{name}"] = value
            changed = True
        if not changed:
            break

    result: dict[str, int] = {}
    for name, value in resolved.items():
        result[name] = value
        if class_name:
            result[f"{class_name}.{name}"] = value
    return result


def _parse_assignments(code: str, evaluator: JavaIntEvaluator) -> None:
    # A few passes allow later locals to depend on earlier locals.
    patterns = [
        re.compile(r"\b(?:final\s+)?(?:int|short|byte|long)\s+([A-Za-z_]\w*)\s*=\s*([^;]+);"),
        re.compile(r"\b(?:this\.)?(imageWidth|imageHeight|titleLabelX|titleLabelY|inventoryLabelX|inventoryLabelY)\s*=\s*([^;]+);"),
    ]
    for _ in range(4):
        changed = False
        for pattern in patterns:
            for m in pattern.finditer(code):
                name, expr = m.group(1), m.group(2)
                try:
                    value = evaluator.eval(expr)
                except Exception:
                    continue
                if evaluator.env.get(name) != value:
                    evaluator.env[name] = value
                    changed = True
        if not changed:
            break


def _parse_simple_for_header(header: str, evaluator: JavaIntEvaluator):
    # Supports: for (int i = 0; i < 9; i++)
    m = re.fullmatch(
        r"\s*(?:int\s+)?([A-Za-z_]\w*)\s*=\s*([^;]+)\s*;\s*"
        r"\1\s*(<|<=)\s*([^;]+)\s*;\s*"
        r"(?:\1\+\+|\+\+\1|\1\s*\+=\s*1)\s*",
        header,
        flags=re.S,
    )
    if not m:
        return None
    var, start_expr, op, end_expr = m.groups()
    try:
        start = evaluator.eval(start_expr)
        end = evaluator.eval(end_expr)
    except Exception:
        return None
    if op == "<=":
        end += 1
    return var, range(start, end)



def _skip_ws(code: str, pos: int) -> int:
    while pos < len(code) and code[pos].isspace():
        pos += 1
    return pos


def _statement_end(code: str, start: int) -> int:
    """Return exclusive end of one Java statement starting at *start*.

    Supports blocks, nested for-statements and ordinary semicolon-terminated
    statements. This is intentionally small but enough for slot layout loops.
    """
    start = _skip_ws(code, start)
    if start >= len(code):
        return start

    if code[start] == "{":
        return _matching(code, start, "{", "}") + 1

    if re.match(r"for\b", code[start:]):
        open_paren = code.find("(", start)
        if open_paren < 0:
            return start
        close_paren = _matching(code, open_paren)
        return _statement_end(code, close_paren + 1)

    stack: list[str] = []
    quote: str | None = None
    escaped = False
    pairs = {")": "(", "]": "[", "}": "{"}

    for i in range(start, len(code)):
        ch = code[i]
        if quote is not None:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            continue

        if ch in ('"', "'"):
            quote = ch
            continue
        if ch in "([{":
            stack.append(ch)
            continue
        if ch in ")]}":
            if stack and stack[-1] == pairs[ch]:
                stack.pop()
            continue
        if ch == ";" and not stack:
            return i + 1

    return len(code)

def _extract_single_slot_call(
    code: str,
    call_start: int,
    arg_text: str,
    evaluator: JavaIntEvaluator,
    warnings: list[ExtractionWarning],
    line_offset: int,
) -> dict[str, Any] | None:
    args0 = _split_args(arg_text)
    if not args0:
        return None
    expr = args0[0]
    new_m = re.search(r"\bnew\s+([A-Za-z_][\w.]*)\s*\(", expr)
    if not new_m:
        warnings.append(
            ExtractionWarning(
                "UNRESOLVED_SLOT",
                f"addSlot argument not recognized: {expr.strip()[:120]}",
                line_offset + _line_of(code, call_start),
            )
        )
        return None

    open_pos = expr.find("(", new_m.start())
    try:
        close_pos = _matching(expr, open_pos)
    except ValueError:
        return None
    ctor_args = _split_args(expr[open_pos + 1:close_pos])
    if len(ctor_args) < 3:
        warnings.append(
            ExtractionWarning(
                "UNRESOLVED_SLOT",
                f"slot constructor has too few arguments: {expr.strip()[:120]}",
                line_offset + _line_of(code, call_start),
            )
        )
        return None

    try:
        x = evaluator.eval(ctor_args[-2])
        y = evaluator.eval(ctor_args[-1])
    except Exception as exc:
        warnings.append(
            ExtractionWarning(
                "UNRESOLVED_SLOT_COORDINATE",
                f"{ctor_args[-2]!r}, {ctor_args[-1]!r}: {exc}",
                line_offset + _line_of(code, call_start),
            )
        )
        return None

    return {
        # Actual menu index is assigned later from addSlot execution order.
        "declared_index_expr": ctor_args[-3] if len(ctor_args) >= 4 else None,
        "x": x,
        "y": y,
        "w": 16,
        "h": 16,
        "_line": line_offset + _line_of(code, call_start),
    }


def _extract_slots_recursive(
    code: str,
    base_env: dict[str, int],
    warnings: list[ExtractionWarning],
    line_offset: int = 0,
) -> list[dict[str, Any]]:
    """Extract addSlot calls in execution/source order, expanding simple for loops."""
    slots: list[dict[str, Any]] = []
    evaluator = JavaIntEvaluator(base_env)
    _parse_assignments(code, evaluator)

    token = re.compile(r"\b(for\s*\(|addSlot\s*\()")
    pos = 0
    while True:
        m = token.search(code, pos)
        if not m:
            break

        if m.group(1).startswith("for"):
            open_paren = code.find("(", m.start())
            try:
                close_paren = _matching(code, open_paren)
            except ValueError:
                pos = m.end()
                continue

            header = code[open_paren + 1:close_paren]
            parsed = _parse_simple_for_header(header, evaluator)

            body_start = _skip_ws(code, close_paren + 1)
            if body_start >= len(code):
                pos = close_paren + 1
                continue

            try:
                body_end = _statement_end(code, body_start)
            except ValueError:
                warnings.append(
                    ExtractionWarning(
                        "UNRESOLVED_FOR",
                        "could not determine for-loop body",
                        line_offset + _line_of(code, m.start()),
                    )
                )
                pos = close_paren + 1
                continue

            if parsed is None:
                warnings.append(
                    ExtractionWarning(
                        "UNRESOLVED_FOR",
                        f"unsupported for-loop header: {header.strip()}",
                        line_offset + _line_of(code, m.start()),
                    )
                )
                pos = body_end
                continue

            var, values = parsed

            if code[body_start] == "{":
                body = code[body_start + 1:body_end - 1]
                body_content_start = body_start + 1
            else:
                body = code[body_start:body_end]
                body_content_start = body_start

            body_line_offset = line_offset + _line_of(code, body_content_start) - 1
            for value in values:
                env = dict(evaluator.env)
                env[var] = value
                slots.extend(_extract_slots_recursive(body, env, warnings, body_line_offset))

            pos = body_end
            continue

        # addSlot(...)
        open_paren = code.find("(", m.start())
        try:
            close_paren = _matching(code, open_paren)
        except ValueError:
            pos = m.end()
            continue
        arg_text = code[open_paren + 1:close_paren]
        slot = _extract_single_slot_call(
            code, m.start(), arg_text, evaluator, warnings, line_offset
        )
        if slot is not None:
            slots.append(slot)
        pos = close_paren + 1

    return slots


@dataclass
class JavaMethod:
    name: str
    params: list[tuple[str, str]]
    body: str
    body_start: int
    body_end: int


def _extract_methods(code: str) -> dict[str, list[JavaMethod]]:
    methods: dict[str, list[JavaMethod]] = {}
    pattern = re.compile(
        r"\b(?:public|protected|private)?\s*(?:static\s+)?(?:final\s+)?"
        r"(?:void|int|long|boolean|float|double|[A-Za-z_][A-Za-z0-9_<>?,. ]*)\s+"
        r"([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)\s*\{",
        flags=re.S,
    )
    for m in pattern.finditer(code):
        name = m.group(1)
        brace = code.find("{", m.end() - 1)
        try:
            close = _matching(code, brace, "{", "}")
        except ValueError:
            continue
        raw_params = _split_args(m.group(2))
        params: list[tuple[str, str]] = []
        for raw in raw_params:
            raw = raw.strip()
            if not raw:
                continue
            bits = raw.replace("final ", "").split()
            if len(bits) >= 2:
                params.append((" ".join(bits[:-1]), bits[-1]))
        methods.setdefault(name, []).append(
            JavaMethod(name, params, code[brace + 1:close], brace + 1, close)
        )
    return methods


def _inside_method(methods: dict[str, list[JavaMethod]], name: str, offset: int) -> bool:
    return any(m.body_start <= offset < m.body_end for m in methods.get(name, []))


def _extract_slot_frames_from_screen(
    code: str,
    evaluator: JavaIntEvaluator,
    warnings: list[ExtractionWarning],
) -> list[dict[str, Any]]:
    methods = _extract_methods(code)
    entries = methods.get("renderBg") or []
    if not entries:
        return []

    frames: list[dict[str, Any]] = []

    def walk(body: str, env: dict[str, int], line_offset: int, stack: tuple[str, ...]) -> None:
        local_eval = JavaIntEvaluator(env)
        _parse_assignments(body, local_eval)
        helper_names = [n for n in methods if n not in stack]
        names = sorted(set(["drawSlot"] + helper_names), key=len, reverse=True)
        token = re.compile(r"\b(for\s*\(|(?:" + "|".join(re.escape(n) for n in names) + r")\s*\()")
        pos = 0
        while True:
            m = token.search(body, pos)
            if not m:
                break
            token_text = m.group(1)
            if token_text.startswith("for"):
                open_paren = body.find("(", m.start())
                try:
                    close_paren = _matching(body, open_paren)
                except ValueError:
                    pos = m.end()
                    continue
                header = body[open_paren + 1:close_paren]
                parsed = _parse_simple_for_header(header, local_eval)
                body_start = _skip_ws(body, close_paren + 1)
                try:
                    body_end = _statement_end(body, body_start)
                except Exception:
                    pos = close_paren + 1
                    continue
                if parsed is None:
                    warnings.append(
                        ExtractionWarning(
                            "UNRESOLVED_SCREEN_FOR",
                            f"unsupported screen for-loop: {header.strip()}",
                            line_offset + _line_of(body, m.start()),
                        )
                    )
                    pos = body_end
                    continue
                var, values = parsed
                if body[body_start] == "{":
                    nested = body[body_start + 1:body_end - 1]
                    nested_start = body_start + 1
                else:
                    nested = body[body_start:body_end]
                    nested_start = body_start
                nested_line_offset = line_offset + _line_of(body, nested_start) - 1
                for value in values:
                    nested_env = dict(local_eval.env)
                    nested_env[var] = value
                    walk(nested, nested_env, nested_line_offset, stack)
                pos = body_end
                continue

            name = re.match(r"([A-Za-z_]\w*)", token_text).group(1)
            open_paren = body.find("(", m.start())
            try:
                close_paren = _matching(body, open_paren)
            except ValueError:
                pos = m.end()
                continue
            args = _split_args(body[open_paren + 1:close_paren])
            source_line = line_offset + _line_of(body, m.start())

            if name == "drawSlot":
                if len(args) >= 3:
                    try:
                        x = local_eval.eval(args[-2])
                        y = local_eval.eval(args[-1])
                        frames.append(
                            {
                                "type": "slot_frame",
                                "x": x,
                                "y": y,
                                "w": 18,
                                "h": 18,
                                "expected_inset": {"x": 1, "y": 1},
                                "source_line": source_line,
                            }
                        )
                    except Exception as exc:
                        warnings.append(
                            ExtractionWarning(
                                "UNRESOLVED_SLOT_FRAME",
                                f"could not evaluate drawSlot position: {exc}",
                                source_line,
                            )
                        )
                pos = close_paren + 1
                continue

            overloads = methods.get(name) or []
            if overloads and name not in stack:
                method = next((x for x in overloads if len(x.params) == len(args)), overloads[0])
                child_env = dict(local_eval.env)
                for (ptype, pname), arg in zip(method.params, args):
                    if re.search(r"\b(?:int|long|short|byte)\b", ptype):
                        try:
                            child_env[pname] = local_eval.eval(arg)
                        except Exception:
                            pass
                method_line = _line_of(code, method.body_start)
                walk(method.body, child_env, method_line - 1, stack + (name,))
            pos = close_paren + 1

    entry = entries[0]
    walk(entry.body, evaluator.env, _line_of(code, entry.body_start) - 1, ("renderBg",))
    return frames



def _resolve_bound_expression(expr: str, expression_env: dict[str, str]) -> str:
    """Resolve a helper parameter when the whole expression is that parameter.

    This is intentionally conservative. It is used for non-numeric values such
    as a ``Component label`` passed into a button helper. Numeric parameters are
    handled by ``JavaIntEvaluator`` instead.
    """
    current = expr.strip()
    seen: set[str] = set()
    for _ in range(4):
        if current in seen:
            break
        seen.add(current)
        if not re.fullmatch(r"[A-Za-z_]\w*", current):
            break
        replacement = expression_env.get(current)
        if replacement is None:
            break
        current = replacement.strip()
    return current


def _resolve_button_text_expression(
    expr: str,
    expression_env: dict[str, str],
) -> str:
    """Resolve safe helper-bound values used by a button label.

    Whole-expression forwarding (``Button.builder(label, ...)``) was already
    supported by :func:`_resolve_bound_expression`.  This adds the equally
    common ``Component.literal(label)`` form, including top-level string
    concatenations whose individual terms are helper parameters.

    The substitution is intentionally syntax-directed: only identifiers that
    are already present in ``expression_env`` are replaced.  No arbitrary Java
    method calls or runtime string expressions are evaluated.
    """
    current = _resolve_bound_expression(expr, expression_env)

    literal = re.fullmatch(
        r"((?:Component\.)?literal)\s*\((.*)\)",
        current,
        flags=re.S,
    )
    if literal is None:
        return current

    args = _split_args(literal.group(2))
    if len(args) != 1:
        return current

    parts = _split_top_level_concat(args[0])
    if not parts:
        return current

    resolved_parts = [
        _resolve_bound_expression(part, expression_env)
        for part in parts
    ]
    inner = " + ".join(resolved_parts)
    return f"{literal.group(1)}({inner})"


def _button_relevant_methods(
    methods: dict[str, list[JavaMethod]],
    max_depth: int = 3,
) -> set[str]:
    """Return methods that directly or transitively contain a Button.builder.

    The fixed-point expansion is depth-limited so arbitrary call graphs are not
    interpreted. This exists only to identify small UI helper chains.
    """
    relevant = {
        name
        for name, overloads in methods.items()
        if any(re.search(r"\bButton\s*\.\s*builder\s*\(", method.body) for method in overloads)
    }
    for _ in range(max_depth):
        before = set(relevant)
        for name, overloads in methods.items():
            if name in relevant:
                continue
            for method in overloads:
                if any(
                    re.search(rf"\b{re.escape(target)}\s*\(", method.body)
                    for target in relevant
                ):
                    relevant.add(name)
                    break
        if relevant == before:
            break
    return relevant


def _extract_buttons_from_screen(
    code: str,
    evaluator: JavaIntEvaluator,
    warnings: list[ExtractionWarning],
    max_depth: int = 3,
) -> list[dict[str, Any]]:
    """Extract buttons from ``init`` and small helper chains.

    Supported helper expansion is deliberately narrow:

    * helper calls must resolve to a method declared in the same Screen class;
    * integer arguments are evaluated using the existing coordinate evaluator;
    * non-integer parameters may be forwarded as whole expressions (notably a
      ``Component`` label);
    * recursion is capped by ``max_depth``;
    * unresolved helper arguments produce a warning instead of speculative
      execution.

    This allows natural code such as ``addButton(x, y, label)`` without making
    the linter an arbitrary Java interpreter.
    """
    methods = _extract_methods(code)
    relevant = _button_relevant_methods(methods, max_depth=max_depth)
    buttons: list[dict[str, Any]] = []

    def parse_button_builder(
        body: str,
        start: int,
        local_eval: JavaIntEvaluator,
        expression_env: dict[str, str],
        line_offset: int,
        origin_line: int | None,
        helper_name: str | None,
    ) -> int:
        open_builder = body.find("(", start)
        try:
            close_builder = _matching(body, open_builder)
        except ValueError:
            return start + 1

        builder_args = _split_args(body[open_builder + 1:close_builder])
        try:
            statement_end = _statement_end(body, start)
        except Exception:
            statement_end = min(len(body), close_builder + 800)

        chain = body[close_builder + 1:statement_end]
        bounds_match = re.search(r"\.\s*bounds\s*\(", chain)
        if not bounds_match:
            return max(close_builder + 1, statement_end)

        open_bounds = close_builder + 1 + chain.find("(", bounds_match.start())
        try:
            close_bounds = _matching(body, open_bounds)
        except ValueError:
            return max(close_builder + 1, statement_end)

        bounds_args = _split_args(body[open_bounds + 1:close_bounds])
        source_line = origin_line or (line_offset + _line_of(body, start))
        if len(bounds_args) != 4:
            warnings.append(
                ExtractionWarning(
                    "UNRESOLVED_BUTTON_BOUNDS",
                    f"Button.bounds expected 4 arguments, got {len(bounds_args)}",
                    source_line,
                )
            )
            return max(close_bounds + 1, statement_end)

        try:
            x, y, w, h = [local_eval.eval(value) for value in bounds_args]
        except Exception as exc:
            context = f" through helper {helper_name}()" if helper_name else ""
            warnings.append(
                ExtractionWarning(
                    "UNRESOLVED_BUTTON_BOUNDS",
                    f"could not evaluate Button.bounds{context}: {exc}",
                    source_line,
                )
            )
            return max(close_bounds + 1, statement_end)

        text_expr = builder_args[0] if builder_args else ""
        text_expr = _resolve_button_text_expression(text_expr, expression_env)
        text = _extract_java_string(text_expr) if text_expr else ""
        text = text or (f"⟦{text_expr.strip()[:60]}⟧" if text_expr else "")

        button: dict[str, Any] = {
            "type": "button",
            "x": x,
            "y": y,
            "w": w,
            "h": h,
            "text": text,
            "click_bounds": {"x": x, "y": y, "w": w, "h": h},
            "source_line": source_line,
        }
        if helper_name:
            button["helper"] = helper_name
            button["helper_source_line"] = line_offset + _line_of(body, start)

        translatable = _extract_translatable_spec(text_expr)
        if translatable is not None:
            button["translation_key"], button["translation_args"] = translatable
        else:
            dynamic_translatable = _extract_dynamic_translatable_spec(text_expr)
            if dynamic_translatable is not None:
                button["translation_key_template"], button["translation_args"] = dynamic_translatable

        buttons.append(button)
        return max(close_bounds + 1, statement_end)

    def walk(
        body: str,
        env: dict[str, int],
        expression_env: dict[str, str],
        line_offset: int,
        stack: tuple[str, ...],
        depth: int,
        origin_line: int | None = None,
    ) -> None:
        local_eval = JavaIntEvaluator(env)
        _parse_assignments(body, local_eval)

        helper_names = sorted(
            [name for name in relevant if name not in stack],
            key=len,
            reverse=True,
        )
        helper_part = (
            r"|(?:" + "|".join(re.escape(name) for name in helper_names) + r")\s*\("
            if helper_names
            else ""
        )
        token = re.compile(
            r"\b(for\s*\(|Button\s*\.\s*builder\s*\(" + helper_part + r")"
        )

        pos = 0
        while True:
            match = token.search(body, pos)
            if not match:
                break
            token_text = match.group(1)

            if token_text.startswith("for"):
                open_paren = body.find("(", match.start())
                try:
                    close_paren = _matching(body, open_paren)
                except ValueError:
                    pos = match.end()
                    continue
                header = body[open_paren + 1:close_paren]
                parsed = _parse_simple_for_header(header, local_eval)
                body_start = _skip_ws(body, close_paren + 1)
                try:
                    body_end = _statement_end(body, body_start)
                except Exception:
                    pos = close_paren + 1
                    continue
                if parsed is None:
                    warnings.append(
                        ExtractionWarning(
                            "UNRESOLVED_BUTTON_FOR",
                            f"unsupported button helper for-loop: {header.strip()}",
                            origin_line or (line_offset + _line_of(body, match.start())),
                        )
                    )
                    pos = body_end
                    continue

                var, values = parsed
                if body[body_start] == "{":
                    nested = body[body_start + 1:body_end - 1]
                    nested_start = body_start + 1
                else:
                    nested = body[body_start:body_end]
                    nested_start = body_start
                nested_offset = line_offset + _line_of(body, nested_start) - 1
                for value in values:
                    child_env = dict(local_eval.env)
                    child_env[var] = value
                    walk(
                        nested,
                        child_env,
                        dict(expression_env),
                        nested_offset,
                        stack,
                        depth,
                        origin_line,
                    )
                pos = body_end
                continue

            if token_text.startswith("Button"):
                pos = parse_button_builder(
                    body,
                    match.start(),
                    local_eval,
                    expression_env,
                    line_offset,
                    origin_line,
                    stack[-1] if len(stack) > 1 else None,
                )
                continue

            helper_name_match = re.match(r"([A-Za-z_]\w*)", token_text)
            if helper_name_match is None:
                pos = match.end()
                continue
            helper_name = helper_name_match.group(1)
            call_line = origin_line or (line_offset + _line_of(body, match.start()))

            if depth >= max_depth:
                warnings.append(
                    ExtractionWarning(
                        "UNRESOLVED_BUTTON_HELPER_DEPTH",
                        f"button helper expansion exceeded depth {max_depth}: {helper_name}()",
                        call_line,
                    )
                )
                open_paren = body.find("(", match.start())
                try:
                    pos = _matching(body, open_paren) + 1
                except ValueError:
                    pos = match.end()
                continue

            open_paren = body.find("(", match.start())
            try:
                close_paren = _matching(body, open_paren)
            except ValueError:
                pos = match.end()
                continue
            args = _split_args(body[open_paren + 1:close_paren])
            overloads = methods.get(helper_name) or []
            method = next((item for item in overloads if len(item.params) == len(args)), None)
            if method is None:
                warnings.append(
                    ExtractionWarning(
                        "UNRESOLVED_BUTTON_HELPER",
                        f"no matching helper overload for {helper_name}({len(args)} args)",
                        call_line,
                    )
                )
                pos = close_paren + 1
                continue

            child_env = dict(local_eval.env)
            child_expression_env = dict(expression_env)
            unresolved_numeric: list[str] = []
            for (ptype, pname), raw_arg in zip(method.params, args):
                arg = _resolve_bound_expression(raw_arg, expression_env)
                child_expression_env[pname] = arg
                if re.search(r"\b(?:int|long|short|byte)\b", ptype):
                    try:
                        child_env[pname] = local_eval.eval(arg)
                    except Exception:
                        unresolved_numeric.append(f"{pname}={arg}")

            if unresolved_numeric:
                warnings.append(
                    ExtractionWarning(
                        "UNRESOLVED_BUTTON_HELPER_ARGUMENT",
                        f"could not evaluate numeric argument(s) for {helper_name}(): "
                        + ", ".join(unresolved_numeric),
                        call_line,
                    )
                )

            walk(
                method.body,
                child_env,
                child_expression_env,
                _line_of(code, method.body_start) - 1,
                stack + (helper_name,),
                depth + 1,
                call_line,
            )
            pos = close_paren + 1

    entries = methods.get("init") or []
    if entries:
        entry = entries[0]
        walk(
            entry.body,
            evaluator.env,
            {},
            _line_of(code, entry.body_start) - 1,
            ("init",),
            0,
        )
    else:
        # Preserve the old broad behavior for unusual Screens without init().
        # Helpers are not expanded from this fallback root.
        relevant.clear()
        walk(code, evaluator.env, {}, 0, ("<root>",), 0)

    return buttons

def _java_argb(expr: str) -> list[int]:
    try:
        raw = int(expr.strip().replace("_", ""), 0) & 0xFFFFFFFF
        alpha = (raw >> 24) & 0xFF
        if raw <= 0xFFFFFF:
            alpha = 0xFF
        return [(raw >> 16) & 0xFF, (raw >> 8) & 0xFF, raw & 0xFF, alpha]
    except Exception:
        return [90, 90, 90, 255]


def _progress_from_fill(
    code: str,
    args: list[str],
    evaluator: JavaIntEvaluator,
    source_line: int,
) -> dict[str, Any] | None:
    if len(args) < 5:
        return None
    x2 = args[2].strip()
    var_match = re.search(r"\+\s*([A-Za-z_]\w*)\s*$", x2)
    if not var_match:
        return None
    width_var = var_match.group(1)
    assign = re.search(rf"\bint\s+{re.escape(width_var)}\s*=\s*([^;]+);", code)
    if not assign:
        return None
    expr = assign.group(1).strip()
    pm = re.fullmatch(
        r"([A-Za-z_]\w*)\s*<=\s*0\s*\?\s*0\s*:\s*Math\.min\(\s*(\d+)\s*,\s*"
        r"(?:this\.)?menu\.([A-Za-z_]\w*)\(\)\s*\*\s*(\d+)\s*/\s*\1\s*\)",
        expr,
    )
    if not pm:
        return None
    denom_var, max_width_s, value_method, multiplier_s = pm.groups()
    denom_assign = re.search(
        rf"\bint\s+{re.escape(denom_var)}\s*=\s*(?:this\.)?menu\.([A-Za-z_]\w*)\(\)\s*;",
        code,
    )
    if not denom_assign:
        return None
    try:
        x = evaluator.eval(args[0])
        y = evaluator.eval(args[1])
        y2 = evaluator.eval(args[3])
    except Exception:
        return None
    return {
        "type": "progress",
        "x": x,
        "y": y,
        "w": int(max_width_s),
        "h": abs(y2 - y),
        "value": "state." + _snake(value_method),
        "max": "state." + _snake(denom_assign.group(1)),
        "style": "fill",
        "color": _java_argb(args[4]),
        "source_line": source_line,
    }


def _default_state_and_presets(elements: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    keys: set[str] = set()
    for e in elements:
        text = str(e.get("text", ""))
        keys.update(re.findall(r"\{([A-Za-z_]\w*)\}", text))
        for name in ("value", "max"):
            value = e.get(name)
            if isinstance(value, str) and value.startswith("state."):
                keys.add(value[6:])

    state: dict[str, Any] = {}
    for key in sorted(keys):
        if key == "screen_title":
            state[key] = "Title"
        elif key == "inventory_title":
            state[key] = "Inventory"
        elif "duration" in key:
            state[key] = 1000
        else:
            state[key] = 0

    presets: dict[str, Any] = {}
    progress_key = next((k for k in keys if "progress" in k), None)
    duration_key = next((k for k in keys if "duration" in k), None)
    power_key = next((k for k in keys if "power" in k), None)
    if progress_key or power_key:
        empty: dict[str, Any] = {}
        building: dict[str, Any] = {}
        almost: dict[str, Any] = {}
        if progress_key and duration_key:
            empty.update({progress_key: 0, duration_key: 1000})
            building.update({progress_key: 500, duration_key: 1000})
            almost.update({progress_key: 999, duration_key: 1000})
        if power_key:
            empty[power_key] = 0
            building[power_key] = 16
            almost[power_key] = 2147483647
        presets = {
            "empty": {"state": empty},
            "building": {"state": building},
            "almost_finished": {"state": almost},
        }
    return state, presets

def extract_java(
    screen_path: str | Path,
    menu_path: str | Path | None = None,
) -> dict[str, Any]:
    screen_path = Path(screen_path)
    raw_screen = screen_path.read_text(encoding="utf-8")
    screen_code = _strip_comments(raw_screen)
    warnings: list[ExtractionWarning] = []

    # Cross-class constants are intentionally limited to the explicitly supplied
    # Menu source. This covers natural references such as
    # FleetCommandMenu.BUTTON_FORMATION without searching or executing an
    # arbitrary source tree.
    menu_code: str | None = None
    menu_class_name: str | None = None
    external_constants: dict[str, int] = {}
    if menu_path is not None:
        menu_path = Path(menu_path)
        raw_menu = menu_path.read_text(encoding="utf-8")
        menu_code = _strip_comments(raw_menu)
        menu_class_name = _extract_class_name(menu_code)
        external_constants.update(
            _extract_public_static_final_int_constants(menu_code, menu_class_name)
        )

    screen_class_name = _extract_class_name(screen_code)
    screen_constants = _extract_public_static_final_int_constants(
        screen_code, screen_class_name, external_constants
    )

    evaluator = JavaIntEvaluator({
        "imageWidth": 176,
        "imageHeight": 166,
        **external_constants,
        **screen_constants,
    })
    evaluator.env.update({
        "titleLabelX": 8,
        "titleLabelY": 6,
        "inventoryLabelX": 8,
        "inventoryLabelY": 72,
    })
    _parse_assignments(screen_code, evaluator)

    image_width = evaluator.env.get("imageWidth", 176)
    image_height = evaluator.env.get("imageHeight", 166)
    if "inventoryLabelY" not in evaluator.env:
        evaluator.env["inventoryLabelY"] = image_height - 94

    methods = _extract_methods(screen_code)
    elements: list[dict[str, Any]] = []
    counters: dict[str, int] = {}

    def next_id(kind: str) -> str:
        counters[kind] = counters.get(kind, 0) + 1
        return f"{kind}_{counters[kind]}"

    # Expand Screen drawSlot(...) helpers into first-class slot_frame elements.
    frames = _extract_slot_frames_from_screen(screen_code, evaluator, warnings)
    for frame in frames:
        frame["id"] = next_id("slot_frame")
        elements.append(frame)

    # graphics.fill / guiGraphics.fill. Fills inside drawSlot are represented by
    # slot_frame and therefore skipped to avoid duplicate rendering/warnings.
    for _, start, _, _, arg_text in _find_calls(screen_code, ("fill",)):
        prefix = screen_code[max(0, start - 24):start]
        if not re.search(r"(?:guiGraphics|graphics)\s*\.\s*$", prefix):
            continue
        if _inside_method(methods, "drawSlot", start):
            continue

        args = _split_args(arg_text)
        if len(args) < 5:
            continue
        try:
            x1 = evaluator.eval(args[0])
            y1 = evaluator.eval(args[1])
            x2 = evaluator.eval(args[2])
            y2 = evaluator.eval(args[3])
        except Exception as exc:
            progress = _progress_from_fill(screen_code, args, evaluator, _line_of(screen_code, start))
            if progress is not None:
                progress["id"] = next_id("progress")
                elements.append(progress)
                continue
            warnings.append(
                ExtractionWarning(
                    "UNRESOLVED_FILL",
                    f"could not evaluate fill bounds: {exc}",
                    _line_of(screen_code, start),
                )
            )
            continue

        elements.append(
            {
                "type": "fill",
                "id": next_id("fill"),
                "x": min(x1, x2),
                "y": min(y1, y2),
                "w": abs(x2 - x1),
                "h": abs(y2 - y1),
                "color": _java_argb(args[4]),
                "source_line": _line_of(screen_code, start),
            }
        )

    # blit destination bounds only.
    for _, start, _, _, arg_text in _find_calls(screen_code, ("blit",)):
        prefix = screen_code[max(0, start - 30):start]
        if not re.search(r"(?:guiGraphics|graphics)\s*\.\s*$", prefix):
            continue
        args = _split_args(arg_text)
        if len(args) < 7:
            warnings.append(ExtractionWarning("UNRESOLVED_BLIT", f"unsupported blit overload with {len(args)} arguments", _line_of(screen_code, start)))
            continue
        try:
            x = evaluator.eval(args[1]); y = evaluator.eval(args[2]); w = evaluator.eval(args[5]); h = evaluator.eval(args[6])
        except Exception as exc:
            warnings.append(ExtractionWarning("UNRESOLVED_BLIT", f"could not evaluate blit destination bounds: {exc}", _line_of(screen_code, start)))
            continue
        elements.append({"type":"blit","id":next_id("blit"),"x":x,"y":y,"w":w,"h":h,"texture":args[0].strip(),"source_line":_line_of(screen_code,start)})

    # drawString / drawCenteredString.
    for name, start, _, _, arg_text in _find_calls(screen_code, ("drawString", "drawCenteredString")):
        prefix = screen_code[max(0, start - 30):start]
        if not re.search(r"(?:guiGraphics|graphics)\s*\.\s*$", prefix):
            continue
        args = _split_args(arg_text)
        if len(args) < 4:
            continue
        text_expr = args[1]
        text = _extract_java_string(text_expr)
        if text is None:
            text = f"⟦{text_expr.strip()[:80]}⟧"
            warnings.append(ExtractionWarning("APPROXIMATED_TEXT", f"text expression kept as placeholder: {text_expr.strip()[:120]}", _line_of(screen_code, start)))
        try:
            x = evaluator.eval(args[2]); y = evaluator.eval(args[3])
        except Exception as exc:
            warnings.append(ExtractionWarning("UNRESOLVED_TEXT_COORDINATE", f"could not evaluate text position: {exc}", _line_of(screen_code, start)))
            continue
        element = {"type":"text","id":next_id("text"),"x":x,"y":y,"text":text,"source_line":_line_of(screen_code,start)}
        translatable = _extract_translatable_spec(text_expr)
        if translatable is not None:
            element["translation_key"], element["translation_args"] = translatable
        else:
            dynamic_translatable = _extract_dynamic_translatable_spec(text_expr)
            if dynamic_translatable is not None:
                element["translation_key_template"], element["translation_args"] = dynamic_translatable
        if len(args) >= 5:
            element["color"] = _java_argb(args[4])
        if name == "drawCenteredString":
            element["align"] = "center"
        elements.append(element)

    # Button.builder(...).bounds(...) including small helper chains from init().
    extracted_buttons = _extract_buttons_from_screen(screen_code, evaluator, warnings)
    for button in extracted_buttons:
        button["id"] = next_id("button")
        elements.append(button)

    menu_slots: list[dict[str, Any]] = []
    if menu_path is not None and menu_code is not None:
        menu_eval = JavaIntEvaluator(external_constants)
        _parse_assignments(menu_code, menu_eval)
        menu_slots = _extract_slots_recursive(menu_code, menu_eval.env, warnings)
        for ordinal, slot in enumerate(menu_slots):
            slot["index"] = ordinal
            slot["name"] = f"slot_{ordinal}"
            slot.pop("declared_index_expr", None)

        # Associate each drawn frame with the actual Menu slot. Exact coordinate
        # matching is preferred; remaining frames fall back to execution order so
        # a mismatch is still reported instead of silently disappearing.
        coord_to_slots: dict[tuple[int, int], list[int]] = {}
        for slot in menu_slots:
            coord_to_slots.setdefault((slot["x"], slot["y"]), []).append(slot["index"])
        used: set[int] = set()
        frame_elements = [e for e in elements if e.get("type") == "slot_frame"]
        for ordinal, frame in enumerate(frame_elements):
            expected = (frame["x"] + 1, frame["y"] + 1)
            candidates = [idx for idx in coord_to_slots.get(expected, []) if idx not in used]
            if candidates:
                idx = candidates[0]
            elif ordinal < len(menu_slots):
                idx = menu_slots[ordinal]["index"]
            else:
                continue
            frame["menu_slot"] = idx
            used.add(idx)

    for slot in menu_slots:
        slot.pop("_line", None)

    state, presets = _default_state_and_presets(elements)

    return {
        "screen": {"image_width": image_width, "image_height": image_height},
        "viewport": {"width": 1280, "height": 720, "gui_scale": 3},
        "state": state,
        "widgets": {},
        "slots": {},
        "elements": elements,
        "menu_slots": menu_slots,
        "presets": presets,
        "_extraction": {
            "screen_source": str(screen_path),
            "menu_source": str(menu_path) if menu_path is not None else None,
            "slot_frames": len([e for e in elements if e.get("type") == "slot_frame"]),
            "menu_slots": len(menu_slots),
            "warnings": [w.format() for w in warnings],
        },
    }

def extract_menu_java(menu_path: str | Path) -> dict[str, Any]:
    """Extract a Menu.java without requiring a Screen.java.

    The preview canvas is inferred from the furthest slot plus the conventional
    8px right/bottom margin. This intentionally yields 176x166 / 176x179 for
    common vanilla-style layouts when their slots use the usual coordinates.
    """
    menu_path = Path(menu_path)
    raw_menu = menu_path.read_text(encoding="utf-8")
    menu_code = _strip_comments(raw_menu)
    warnings: list[ExtractionWarning] = []

    evaluator = JavaIntEvaluator()
    _parse_assignments(menu_code, evaluator)
    menu_slots = _extract_slots_recursive(menu_code, evaluator.env, warnings)

    for ordinal, slot in enumerate(menu_slots):
        slot["index"] = ordinal
        slot["name"] = f"slot_{ordinal}"
        slot.pop("declared_index_expr", None)
        slot.pop("_line", None)

    if menu_slots:
        image_width = max(slot["x"] + slot["w"] for slot in menu_slots) + 8
        image_height = max(slot["y"] + slot["h"] for slot in menu_slots) + 8
    else:
        image_width = 176
        image_height = 166

    return {
        "screen": {
            "image_width": image_width,
            "image_height": image_height,
        },
        "viewport": {
            "width": 1280,
            "height": 720,
            "gui_scale": 3,
        },
        "state": {},
        "widgets": {},
        "slots": {},
        "elements": [],
        "menu_slots": menu_slots,
        "_extraction": {
            "screen_source": None,
            "menu_source": str(menu_path),
            "mode": "menu-only",
            "warnings": [w.format() for w in warnings],
        },
    }
