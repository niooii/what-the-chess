from dataclasses import dataclass
from typing import Optional


def _normalise_func(src: str) -> str:
    src = src.strip()
    if not src.startswith("def "):
        return src

    colon_idx = -1
    depth = 0
    for idx, ch in enumerate(src):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth = max(depth - 1, 0)
        elif ch == ':' and depth == 0:
            colon_idx = idx
            break

    if colon_idx == -1:
        return src

    header = src[:colon_idx + 1].rstrip()
    body = src[colon_idx + 1 :].strip()
    if not body:
        return header

    body = body.replace("\r\n", "\n").replace("\r", "\n")
    if "\n" not in body:
        return header + "\n    " + body

    lines = body.split("\n")

    normalised_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped == "":
            normalised_lines.append("")
            continue

        if not line.startswith((" ", "\t")):
            normalised_lines.append("    " + stripped)
        else:
            normalised_lines.append("    " + line)

    return header + "\n" + "\n".join(normalised_lines)


class Ruleset:
    def __init__(self, mv_func_str: str, tk_func_str: str):
        mv_ns: dict[str, object] = {}
        exec(_normalise_func(mv_func_str), {}, mv_ns)
        user_callables = [obj for name, obj in mv_ns.items() if callable(obj) and not name.startswith('__')]
        self.mv_func = user_callables[0]

        tk_ns: dict[str, object] = {}
        exec(_normalise_func(tk_func_str), {}, tk_ns)
        user_callables = [obj for name, obj in tk_ns.items() if callable(obj) and not name.startswith('__')]
        self.tk_func = user_callables[0]
        self.jump = False
        self.max_range = 1

@dataclass
class Piece:
    name: str
    piece_desc: str
    move_desc: str

    rule_sets: list[Ruleset]
    value: int
    move_count: int
    team: int
