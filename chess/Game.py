from Board import Board
from Ruleset import Piece

class Game:
    '''
    collect pieces per game
    '''

    def __init__(self, Player):
        self.players = list(Player)
        self.board = Board(size=8)      # pass in potential hazard and other flags
        # self.pieces = 