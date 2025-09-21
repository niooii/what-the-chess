import asyncio
import json
from typing import Any, Callable, Dict, List, Optional, Awaitable
from chess.player import PlayerState
from client.conn import ClientConnection


players: Dict[int, PlayerState] = {}


async def handle_message(message: dict[str, Any]) -> None:
    mtype = message["type"]

    # AAAAH too lazy to make good rn
    if mtype == "playerjoin":
        player: PlayerState = PlayerState(**message["player"])
        players[player.id] = player
        print(f"New player joined the server: {player.name}:{player.id}")
    elif mtype == "playerleave":
        player: PlayerState = PlayerState(**message["player"])
        print(f"{player.name}:{player.id} left the server")
        del players[player.id]


async def game(conn: ClientConnection):
    await conn.send({"type": "name", "name": "Testuser"})


async def main() -> None:
    connection = ClientConnection()
    await connection.start()
    await asyncio.gather(connection.listen(handle_message), game(conn=connection))


if __name__ == "__main__":
    asyncio.run(main())
