import asyncio
import json
from typing import Any, Awaitable, Callable, Dict, List, Optional

from chess.player import PlayerState


class ClientConnection:
    def __init__(self, server_ip: str = "localhost") -> None:
        self.server_ip = server_ip
        self.writer: Optional[asyncio.StreamWriter] = None
        self.reader: Optional[asyncio.StreamReader] = None
        self.connected: bool = False

    async def start(self) -> None:
        try:
            self.reader, self.writer = await asyncio.open_connection(self.server_ip, 9090)
            self.connected = True
            print(f"Connected to server at {self.server_ip}")
        except Exception as e:
            print(f"Error connecting to {self.server_ip}: {e}")
            self.connected = False

    async def listen(
        self, on_recv: Callable[[dict[str, Any]], Awaitable[None]]
    ) -> None:
        if not self.connected or not self.reader:
            print("Not connected to server")
            return

        try:
            while self.connected:
                data = await self.reader.readline()
                if not data:
                    break

                try:
                    message: dict[str, Any] = json.loads(data.decode().strip())
                    await on_recv(message)
                except json.JSONDecodeError as e:
                    print(f"Failed to parse JSON: {e}")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            self.connected = False
            if self.writer:
                self.writer.close()
                await self.writer.wait_closed()
            print("Disconnected from server")

    async def send(self, obj: Any) -> None:
        if not self.connected or not self.writer:
            print("Not connected to server")
            return

        try:
            json_data: str = json.dumps(obj)
            self.writer.write(json_data.encode() + b"\n")
            await self.writer.drain()
            # print(f"Sent message {json_data}")
        except Exception as e:
            print(f"Failed to send message: {e}")
