import asyncio
from typing import Any, Dict, List

import pygame

from chess.player import PlayerState
from client.conn import ClientConnection


class ClientGame:
    def __init__(self, conn: ClientConnection):
        self.conn = conn
        self.players: List[PlayerState] = []
        pass

    async def game_loop(self):
        await self.conn.send({"type": "name", "name": "Testuser"})

    async def handle_packet(self, message: Dict[str, Any]):
        mtype = message["type"]

        # AAAAH too lazy to make good rn
        if mtype == "playerjoin":
            player: PlayerState = PlayerState(**message["player"])
            self.players[player.id] = player
            print(f"New player joined the server: {player.name}:{player.id}")
        elif mtype == "playerleave":
            player: PlayerState = PlayerState(**message["player"])
            print(f"{player.name}:{player.id} left the server")
            del self.players[player.id]

    async def run(self):
        await asyncio.gather(self.conn.listen(self.handle_packet), self.game_loop())
