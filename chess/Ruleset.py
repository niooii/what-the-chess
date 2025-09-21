from typing import Optional
from dataclasses import dataclass

class Ruleset:
    def __init__(self, mv_func_str: str, tk_func_str: str):
        ns = {}

        exec(mv_func_str, {}, ns)
        exec(tk_func_str, {}, ns)

        self.mv_func = ns["mv_func"]
        self.tk_func = ns["tk_func"]
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
