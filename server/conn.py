import asyncio
import json
import time
from dataclasses import asdict
from typing import Any, Dict, Optional

from chess.player import PlayerState

from .lobby import Lobby


class PlayerConnection:
    def __init__(
        self,
        # server connection type
        server,
        writer: asyncio.StreamWriter,
        player_state: PlayerState,
    ):
        self.writer = writer
        self.server = server
        self.player_state = player_state
        # current game
        game: Optional[Any] = None

    async def send(self, obj: Any) -> None:
        try:
            json_data: str = json.dumps(obj)
            self.writer.write(json_data.encode() + b"\n")
            await self.writer.drain()
        except Exception as e:
            print(f"Failed to send to client: {e}")

    async def process_packet(self, packet: Dict[str, Any]) -> None:
        if self.player_state.name is None:
            # only accept a name packet
            if packet["type"] == "name":
                self.player_state.name = packet["name"]
                self.player_state.id = self.server.id
                print(f"Registered new player {packet["name"]}")
                await self.player_state.replicate(
                    self.server, "playerjoin", exclude_self=False
                )
                # send back all the other players
                player_states = [
                    asdict(p.player_state) for p in self.server.clients.values()
                ]
                await self.send({"type": "playerlist", "players": player_states})
            return
        print(f"Processing packet for {self.player_state.name}: {packet}")


class ServerConnection:
    def __init__(self) -> None:
        self.clients: Dict[asyncio.StreamWriter, PlayerConnection] = {}
        self.id = 0

    async def start(self):
        server = await asyncio.start_server(self.handle_client, "localhost", 25455)
        addr = server.sockets[0].getsockname()
        print(f"Server started on {addr[0]}:{addr[1]}")

        async with server:
            await server.serve_forever()

    async def send(self, writer: asyncio.StreamWriter, obj: Any) -> None:
        try:
            json_data: str = json.dumps(obj)
            writer.write(json_data.encode() + b"\n")
            await writer.drain()
        except Exception as e:
            print(f"Failed to send to client: {e}")

    async def broadcast(self, obj: Any, exclude_id: int = 0) -> None:
        disconnected = []
        for writer, player_connection in self.clients.items():
            try:
                if player_connection.player_state.id != exclude_id:
                    await player_connection.send(obj)
            except Exception:
                disconnected.append(writer)

        for writer in disconnected:
            del self.clients[writer]

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        client_addr = writer.get_extra_info("peername")
        print(f"Client connected from {client_addr}")

        self.id += 1

        player_state = PlayerState(name=None, connected_at=time.time())
        player_connection = PlayerConnection(self, writer, player_state)
        self.clients[writer] = player_connection

        try:
            while True:
                data = await reader.readline()
                if not data:
                    break

                try:
                    message: Dict[str, Any] = json.loads(data.decode().strip())
                    await player_connection.process_packet(message)
                except json.JSONDecodeError as e:
                    print(f"Invalid JSON from {client_addr}: {e}")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            if writer in self.clients:
                await player_state.replicate(self, "playerleave")
                del self.clients[writer]

            writer.close()
            await writer.wait_closed()
            print(f"Client {client_addr} disconnected")
