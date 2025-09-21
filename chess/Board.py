from Ruleset import Piece, Ruleset
from typing import Optional
from dataclasses import dataclass

class Board:
    def __init__(self, size: int = 8):
        self.size = size
        self.board = list[list[Optional[Piece]]] = [
        [None for _ in range(self.size)] for _ in range(size)
    ]

    '''
    Piece manipulation
    '''

    def get_piece(self, pos: tuple[int]) -> Optional[Piece]:
        return self.board[pos[0]][pos[1]]

    def set_piece(self, row: int, col: int, piece : Optional[Piece]) -> bool:
        if row > self.size or col > self.size: 
            return False

        self.board[row][col] = piece
        return True
    
    def move_piece(self, row: int, col: int) -> bool:

        return True

    '''
    Game logic
    '''

    def get_valid_actions(self, piece_pos: tuple[int]) -> Optional[list[tuple[int]]]:
        valid_actions = list[tuple[int]]

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
            return False

        for rule_set in piece.rule_sets:
            # First compute take at initial pos
            tk_dir_vecs: list[tuple[int]] = rule_set.tk_func[piece.move_count]
            mv_dir_vecs: list[tuple[int]] = rule_set.mv_func[piece.move_count]

            if flip_actions:
                mv_dir_vecs = [(-x, -y) for (x, y) in mv_dir_vecs]
                tk_dir_vecs = [(-x, -y) for (x, y) in tk_dir_vecs]

            # Extend moves to max range
            #TODO: FUTURE ME OPTIMIZE THIS BRO

            for dir_vec in tk_dir_vecs:
                i: int = 1
                while i < rule_set.max_range:
                    take: tuple[int] = self.add_vec(self.scale_vec(dir_vec, (i,i)), piece_pos)

                    # Check duplicate
                    if take not in valid_actions and self.is_valid_take(piece, take):
                        valid_actions.append(take)

                    i += 1  # increment inside each direction

            for dir_vec in mv_dir_vecs:
                i: int = 1
                blocked: bool = False
                while i < rule_set.max_range and not blocked:
                    move: tuple[int] = self.add_vec(self.scale_vec(dir_vec, (i,i)), piece_pos)

                    if move not in valid_actions and self.is_valid_move(piece, move):
                        valid_actions.append(move)
                    else:
                        if not rule_set.jump:
                            blocked = True  # stop extending in this direction
                    i += 1

        return valid_actions
        
    def is_valid_take(self, curr_piece: Piece, pos: tuple[int]) -> bool:
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


    def is_valid_move(self, curr_piece: Piece, pos: tuple[int]) -> bool:
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

    def add_vec(a: tuple[int, int], b: tuple[int, int]) -> tuple[int, int]:
        return (a[0] + b[0], a[1] + b[1])

    def scale_vec(v: tuple[int, int], k: int) -> tuple[int, int]:
        return (v[0] * k, v[1] * k)
