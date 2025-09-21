import asyncio
import json
from typing import Any, Callable, Dict, List, Optional, Awaitable
from chess.player import PlayerState
from client.conn import ClientConnection
from client.game import ClientGame


players: Dict[int, PlayerState] = {}


async def main() -> None:
    connection = ClientConnection()
    await connection.start()
    game = ClientGame(connection)
    await game.run()


if __name__ == "__main__":
    asyncio.run(main())
