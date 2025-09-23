import json
import math
from dataclasses import dataclass
from typing import Optional

from chess.Ruleset import Piece, Ruleset


class Board:
    def __init__(self, size: int = 8):
        self.size = size
        self.board: list[list[Optional[Piece]]] = [
            [None for _ in range(self.size)] for _ in range(self.size)
        ]

    '''
    Piece manipulation
    '''

    def get_piece(self, pos: tuple[int, int]) -> Optional[Piece]:
        return self.board[pos[0]][pos[1]]

    def set_piece(self, row: int, col: int, piece : Optional[Piece]) -> bool:
        if row >= self.size or col >= self.size or row < 0 or col < 0: 
            return False

        self.board[row][col] = piece
        return True
    
    def move_piece(self, from_pos: tuple[int, int], to_pos: tuple[int, int]) -> Optional[Piece]:
        piece = self.get_piece(from_pos)
        killed_piece = self.get_piece(to_pos)

        if piece is None:
            return None

        self.set_piece(to_pos[0], to_pos[1], piece)
        self.set_piece(from_pos[0], from_pos[1], None)

        return killed_piece

    '''
    Game logic
    '''

    def get_valid_actions(self, piece_pos: tuple[int, int]) -> Optional[list[tuple[int, int]]]:
        valid_actions: list[tuple[int, int]] = []

        # Check if current square is a piece or not
        # None in this case means it is NOT a piece
        if self.get_piece(piece_pos) is None:
            return None
        piece: Piece = self.get_piece(piece_pos)
        team: int = piece.team

        flip_actions: bool = False

        if team % 2 == 1:
            flip_actions = True

        # Check for bounds
        if not (0 <= piece_pos[0] < self.size and 0 <= piece_pos[1] < self.size):
            return None

        for rule_set in piece.rule_sets:
            # First compute take at initial pos
            tk_dir_vecs_raw = rule_set.tk_func(piece.move_count + 1)
            mv_dir_vecs_raw = rule_set.mv_func(piece.move_count + 1)

            tk_dir_vecs: list[tuple[int, int]] = self._normalise_vectors(tk_dir_vecs_raw)
            mv_dir_vecs: list[tuple[int, int]] = self._normalise_vectors(mv_dir_vecs_raw)

            if flip_actions:
                mv_dir_vecs = [(-x, -y) for (x, y) in mv_dir_vecs]
                tk_dir_vecs = [(-x, -y) for (x, y) in tk_dir_vecs]

            # Extend moves to max range
            #TODO: FUTURE ME OPTIMIZE THIS BRO

            for dir_vec in tk_dir_vecs:
                if rule_set.jump:
                    # Jumping pieces move exactly to their targets
                    take: tuple[int, int] = self.add_vec(dir_vec, piece_pos)
                    if take not in valid_actions and self.is_valid_take(piece, take):
                        valid_actions.append(take)
                else:
                    # Sliding pieces move along direction until blocked
                    i: int = 1
                    while i <= rule_set.max_range:
                        take: tuple[int, int] = self.add_vec(self.scale_vec(dir_vec, i), piece_pos)
                        if not (0 <= take[0] < self.size and 0 <= take[1] < self.size):
                            break  # Out of bounds

                        if not self._is_path_clear(piece_pos, take):
                            break  # Another piece is in the way

                        target_piece = self.get_piece(take)
                        if target_piece is None:
                            i += 1
                            continue

                        if (
                            take not in valid_actions
                            and target_piece.team != piece.team
                        ):
                            valid_actions.append(take)

                        break  # Stop after encountering any piece

            for dir_vec in mv_dir_vecs:
                if rule_set.jump:
                    # Jumping pieces move exactly to their targets
                    move: tuple[int, int] = self.add_vec(dir_vec, piece_pos)
                    if move not in valid_actions and self.is_valid_move(piece, move):
                        valid_actions.append(move)
                else:
                    # Sliding pieces move along direction until blocked
                    i: int = 1
                    blocked: bool = False
                    while i <= rule_set.max_range and not blocked:
                        move: tuple[int, int] = self.add_vec(self.scale_vec(dir_vec, i), piece_pos)
                        if not (0 <= move[0] < self.size and 0 <= move[1] < self.size):
                            break  # Out of bounds
                        if not self._is_path_clear(piece_pos, move):
                            blocked = True
                        elif move not in valid_actions and self.is_valid_move(piece, move):
                            valid_actions.append(move)
                        else:
                            blocked = True  # stop extending in this direction
                        i += 1

        return valid_actions
        
    def is_valid_take(self, curr_piece: Piece, pos: tuple[int, int]) -> bool:
        # Check in bounds
        if not (0 <= pos[0] < self.size and 0 <= pos[1] < self.size):
            return False
    
        # Check for occupied square
        target_piece = self.get_piece(pos)
        if target_piece is None:
            return False

        # Check team
        if curr_piece.team == target_piece.team:
            return False
    
        return True


    def is_valid_move(self, curr_piece: Piece, pos: tuple[int, int]) -> bool:
        # Check in bounds
        if not (0 <= pos[0] < self.size and 0 <= pos[1] < self.size):
            return False
    
        # Check for non-occupied square
        if self.get_piece(pos) is not None:
            return False

        return True
    
    '''
    Helper Functions
    '''

    def _normalise_vectors(self, vectors: Optional[list[tuple[int, int]]]) -> list[tuple[int, int]]:
        """Convert (x, y) offsets from configs into (row, col) board deltas."""
        if not vectors:
            return []

        normalised: list[tuple[int, int]] = []
        for vec in vectors:
            if not isinstance(vec, (tuple, list)) or len(vec) != 2:
                continue
            x, y = int(vec[0]), int(vec[1])
            normalised.append((y, x))
        return normalised

    def add_vec(self, a: tuple[int, int], b: tuple[int, int]) -> tuple[int, int]:
        return (a[0] + b[0], a[1] + b[1])

    def scale_vec(self, v: tuple[int, int], k: int) -> tuple[int, int]:
        return (v[0] * k, v[1] * k)

    def _is_path_clear(self, start: tuple[int, int], end: tuple[int, int]) -> bool:
        """Ensure no pieces block a non-jumping move between start and end (exclusive)."""
        delta_row = end[0] - start[0]
        delta_col = end[1] - start[1]

        steps = math.gcd(abs(delta_row), abs(delta_col))
        if steps <= 1:
            return True

        step_row = delta_row // steps
        step_col = delta_col // steps

        current_row, current_col = start
        for _ in range(steps - 1):
            current_row += step_row
            current_col += step_col
            if self.get_piece((current_row, current_col)) is not None:
                return False

        return True

    @classmethod
    def from_config(cls, config_json: str) -> 'Board':
        config = json.loads(config_json)

        # Create rulesets
        rulesets = []
        for ruleset_data in config["rulesets"]:
            ruleset = Ruleset(
                mv_func_str=ruleset_data["target_moves"],
                tk_func_str=ruleset_data["target_takes"]
            )
            ruleset.jump = ruleset_data["jump"]
            ruleset.max_range = ruleset_data["max_range"]
            rulesets.append(ruleset)

        # Create piece templates
        piece_templates = []
        for piece_data in config["pieces"]:
            piece_rulesets = [rulesets[i] for i in piece_data["rulesets"]]
            piece_template = {
                "name": piece_data["name"],
                "piece_desc": piece_data["desc"],
                "move_desc": piece_data["move_desc"],
                "rule_sets": piece_rulesets,
                "value": 10,  # default value
                "move_count": 0
            }
            piece_templates.append(piece_template)

        # Create board
        board = cls(size=8)

        # Place pieces for both teams
        for start_pos in config["starting_pos"]:
            x, y = start_pos["x"], start_pos["y"]
            piece_template = piece_templates[start_pos["piece"]]

            # Team 0 (bottom side)
            piece_team0 = Piece(
                name=piece_template["name"],
                piece_desc=piece_template["piece_desc"],
                move_desc=piece_template["move_desc"],
                rule_sets=piece_template["rule_sets"],
                value=piece_template["value"],
                move_count=piece_template["move_count"],
                team=0
            )
            board.set_piece(y, x, piece_team0)

            # Team 1 (top side, mirrored)
            piece_team1 = Piece(
                name=piece_template["name"],
                piece_desc=piece_template["piece_desc"],
                move_desc=piece_template["move_desc"],
                rule_sets=piece_template["rule_sets"],
                value=piece_template["value"],
                move_count=piece_template["move_count"],
                team=1
            )
            mirrored_y = 7 - y
            board.set_piece(mirrored_y, x, piece_team1)

        return board
