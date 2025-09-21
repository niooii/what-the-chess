from chess.Board import Board
from chess.Ruleset import Piece
from typing import List, Optional

class Game:
    def __init__(self, players: List):
        self.players = players
        self.board = Board(size=8)
        self.white_taken: List[Piece] = []
        self.black_taken: List[Piece] = []
        self.current_turn = 0

    def move_piece(
        self,
        from_pos: tuple[int, int],
        to_pos: tuple[int, int],
        *,
        validate: bool = True,
    ) -> bool:
        piece = self.board.get_piece(from_pos)
        if piece is None:
            return False

        mover_team = piece.team

        if validate and mover_team != self.current_turn:
            return False

        if validate:
            valid_moves = self.board.get_valid_actions(from_pos)
            if valid_moves is None or to_pos not in valid_moves:
                return False

        killed_piece = self.board.move_piece(from_pos, to_pos)

        if killed_piece is not None:
            if killed_piece.team == 0:
                self.white_taken.append(killed_piece)
            else:
                self.black_taken.append(killed_piece)

        piece.move_count += 1
        self.current_turn = 1 - mover_team
        return True

    def get_current_player(self) -> str:
        return "white" if self.current_turn == 0 else "black"

    def get_taken_pieces(self, team: str) -> List[Piece]:
        if team.lower() == "white":
            return self.white_taken
        elif team.lower() == "black":
            return self.black_taken
        else:
            return []

    @classmethod
    def from_config(cls, config_json: str, players: List):
        game = cls(players)
        game.board = Board.from_config(config_json)
        return game
