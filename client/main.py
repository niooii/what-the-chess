import asyncio
import json
import sys
from typing import Any, Callable, Dict, List, Optional, Awaitable
from chess.player import PlayerState
from client.conn import ClientConnection
from client.game import ClientGame


players: Dict[int, PlayerState] = {}


async def main() -> None:
    server_ip = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    connection = ClientConnection(server_ip)
    await connection.start()
    game = ClientGame(connection)
    await game.run()


if __name__ == "__main__":
    asyncio.run(main())
