from dataclasses import dataclass
from typing import Callable, List, Tuple


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
    # NOTE for most regular pieces (eg. bishop, rook, queen) these function will be the same, but for pieces like the pawn for example, they must be different.

    # a function from the current move number of the piece starting from 1 (not the player's move number)
    # to the list of movement vectors relative to the player's side, which determines where the piece can move to, but not necessarily capture.
    mv_func: Callable[[int], List[Tuple[int, int]]]

    # a function from the current move number of the piece starting from 1 (not the player's move number)
    # to the list of movement vectors relative to the player's side, which determines where the piece can TAKE another, but not necessarily move to.
    tk_func: Callable[[int], List[Tuple[int, int]]]

    # if jump is true, then the piece is a "jump" type, and does not have to worry about 
    # pieces blocking it, unless it cannot take a piece where it lands. 
    # TODO! THIS MAY BE REMOVED LATER, as jump pieces can just be modeled with a movement
    # vector that isn't adjacent to the current tile (e.g. <1, 2>). This is unclear, and
    # will be decided later as more features get added (e.g. pierce, jump depth, etc)
    jump: bool

    # ONLY EFFECTIVE FOR SLIDE TYPES
    # decides the amount of times a slide type piece can apply it's movement vector
    max_range: int

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
