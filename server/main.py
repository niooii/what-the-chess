import asyncio
import json
import os
import sys
import time
from typing import Any, Dict

from chess.player import PlayerState

from .conn import Server


async def main() -> None:
    if not os.getenv("GOOGLE_API_KEY") and len(sys.argv) > 1:
        os.environ["GOOGLE_API_KEY"] = sys.argv[1]
        print(f"Using API key from command line argument")

    server_conn = Server()

    await server_conn.start()


if __name__ == "__main__":
    asyncio.run(main())
