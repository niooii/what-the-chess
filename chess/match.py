from dataclasses import dataclass
from typing import Optional

from chess.player import PlayerState


@dataclass
class Match:
    p1: Optional[PlayerState] = None
    p2: Optional[PlayerState] = None
    move: int = 0
    # TODO!
    board: None = None
