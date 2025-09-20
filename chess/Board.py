from Ruleset import Piece
from typing import Optional
from dataclasses import dataclass

@dataclass
class Board:
    size: int
    # board: list[list[Optional[Piece]]] = [
    #     [None for _ in range(self.size)] for _ in range(size)
    # ]

    def get_piece(self, row: int, col: int) -> Optional[Piece]:
        return self.board[row][col]

    def set_piece(self, row: int, col: int, piece : Optional[Piece]) -> bool:

        self.board[row][col] = piece
    
    # def move_piece(self, row: int, col: int) ->
