from typing import Optional
from dataclasses import dataclass

@dataclass
class Ruleset:
    def __init__(self, mv_func_str: str, tk_func_str: str):
        ns = {}
        
        exec(mv_func_str, {}, ns)
        exec(tk_func_str, {}, ns)

        #TODO: MUS HAVE SRC FUNCTION BE NAMED "mv_func" and "tk_func" and "move_number"
        self.mv_func = ns["mv_func"]
        self.tk_func = ns["tk_func"]

    jump: bool
    max_range: int

    target_moves: list[tuple[int]]   # function as string
    target_takes: list[tuple[int]]   # function as string

@dataclass
class Piece:
    name: str
    piece_desc: str
    move_desc: str

    rule_sets: list[Ruleset]
    value: int
    move_count: int
    team: int
