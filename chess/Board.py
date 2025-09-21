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
    
    # def move_piece(self, row: int, col: int) -> bool:

    '''
    Game logic
    '''

    def get_valid_actions(self, piece_pos: tuple[int]) -> Optional[list[tuple[int]]]:
        valid_actions = list[tuple[int]]

        # Check if current square is a piece or not
        # None in this case means it is NOT a piece
        if not isinstance(self.get_piece(piece_pos), Piece):
            return None
        piece: Piece = self.get_piece(piece_pos)

        # Check for bounds
        if piece_pos[0] > self.size or piece_pos[1] > self.size:
            return None

        for rule_set in piece.rule_sets:
            # First compute take at initial pos
            tk_dir_vecs: list[tuple[int]] = rule_set.tk_func[piece.move_count]
            mv_dir_vecs: list[tuple[int]] = rule_set.mv_func[piece.move_count]

            # Extend moves to max range
            #TODO: FUTURE ME OPTIMIZE THIS BRO
            i: int = 1
            while i < rule_set.max_range:
                
                # Take 
                for dir_vec in tk_dir_vecs:
                    if not dir_vec * i in valid_actions:
                        valid_actions.append(dir_vec * i)
                # Move
                for dir_vec in mv_dir_vecs:
                    move: tuple[int] = dir_vec * i

                    # Check duplicates
                    if move * i in valid_actions: 
                        continue

                    # Check valid move
                    if not self.is_valid_move(move):
                        if not rule_set.jump:
                            break
                        continue

                    dir_vec
            

        # Compute move

        # Check for teams
        

        return []
        
    def is_valid_take(self, curr_piece: Piece, pos: tuple[int]) -> bool:
        # Check in bound
        if pos[0] > self.size or pos[1] > self.size:
            return False
        
        # Check for occupied square
        if isinstance(self.get_piece(pos), None):
            return False
        target_piece: Piece = self.get_piece(pos)

        # Check team
        if curr_piece.team == target_piece.team:
            return False
        
        return True

    def is_valid_move(self, curr_piece: Piece, pos: tuple[int]) -> bool:
        # Check in bound
        if pos[0] > self.size or pos[1] > self.size:
            return False
        
        # Check for non-occupied square
        if isinstance(self.get_piece(pos), Piece):
            return False

        return True