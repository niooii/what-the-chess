import asyncio
import json
import time
from typing import Any, Dict

from chess.player import PlayerState

from .conn import Server


async def main() -> None:
    server_conn = Server()

    await server_conn.start()


if __name__ == "__main__":
    asyncio.run(main())
