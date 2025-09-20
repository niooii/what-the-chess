from typing import Callable, Optional, List, Tuple

class Ruleset:
    value: int
    jump: bool
    target_moves: Optional[str] = None   # function as string
    target_takes: Optional[str] = None   # function as string

    def compile_functions(self):
        """Compile string functions into callables at runtime."""
        if self.target_moves:
            local_env = {}
            exec(self.target_moves, {}, local_env)
            self.target_moves = local_env["move_func"]

        if self.target_takes:
            local_env = {}
            exec(self.target_takes, {}, local_env)
            self.target_takes = local_env["take_func"]

    def get_moves(self, position):
        if callable(self.target_moves):
            return self.target_moves(position)
        return []

    def get_takes(self, position):
        if callable(self.target_takes):
            return self.target_takes(position)
        return []
    
class Ruleset_Test:
    value: int
    jump: bool
    target_moves: Tuple[int, int]
    target_takes: Tuple[int, int]

class Piece:
    name: str
    piece_desc: str
    move_desc: str

    rule_sets: List[Ruleset_Test]
    max_range: 1
    move_count: int
    team: int