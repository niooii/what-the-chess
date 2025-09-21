import asyncio
import json
import time
from dataclasses import asdict
from typing import Any, Dict, Optional

from chess.match import Match
from chess.player import PlayerState

from .lobby import Lobby


# Connection for a signle player
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
        self.match: Optional[Match] = None

    async def send(self, obj: Any) -> None:
        try:
            json_data: str = json.dumps(obj)
            self.writer.write(json_data.encode() + b"\n")
            await self.writer.drain()
        except Exception as e:
            print(f"Failed to send to client: {e}")


class Server:
    def __init__(self) -> None:
        self.clients: Dict[asyncio.StreamWriter, PlayerConnection] = {}
        self.id_to_conn: Dict[int, PlayerConnection] = {}
        # TODO! use match uid instead of player id key, this uses playerid key rn
        self.matches: Dict[int, Match] = {}
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

    async def handle_packet(self, player: PlayerConnection, packet: Dict[str, Any]):
        # change name via a name packet
        mtype = packet["type"]
        if mtype == "name":
            player.player_state.name = packet["name"]
            print(f"Registered new player {packet["name"]}")
            await player.player_state.replicate(
                self, "playermod", exclude_self=False
            )

        elif mtype == "matchcreate":
            if player.match is not None:
                return

            match = Match(p1=player.player_state)
            self.matches[player.player_state.id] = match
            player.match = match

            await self.broadcast({"type": "matchcreate", "host_id": player.player_state.id})

        elif mtype == "matchjoin":
            # if the requesting player is in a match/waiting for a match
            if player.match is not None:
                return
            
            # if the other player this one requested to join doesn't have a match
            joining_id = packet["player_id"]
            other = self.id_to_conn[joining_id]

            if other.match is None:
                return

            # if there is still room in this match
            if other.match.p2 is not None:
                return

            # then we join up

            del self.matches[player.player_state.id]
            player.match = other.match

            await self.broadcast({"type": "matchremove", "host_id": player.player_state.id})

            await player.send({"type": "matchstart", "other_id": other.player_state.id})
            await other.send({"type": "matchstart", "other_id": other.player_state.id})

            # TODO! generate gemini prompt here
            config = {"example": "test"}

            await player.send({"type": "matchconfig", "config": config})
            await other.send({"type": "matchconfig", "other_id": config})

        print(f"Processing packet for {player.player_state.name}: {packet}")


    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        client_addr = writer.get_extra_info("peername")
        print(f"Client connected from {client_addr}")

        self.id += 1

        player_state = PlayerState(name=None, id=self.id, connected_at=time.time())
        player_connection = PlayerConnection(self, writer, player_state)
        self.clients[writer] = player_connection
        self.id_to_conn[player_state.id] = player_connection

        # send back all the other players
        player_states = [
            asdict(p.player_state) for p in self.clients.values()
        ]
        await self.send(writer, {"type": "playerlist", "players": player_states})
        
        await player_state.replicate(
            self, "playerjoin", exclude_self=False
        )

        try:
            while True:
                data = await reader.readline()
                if not data:
                    break

                try:
                    message: Dict[str, Any] = json.loads(data.decode().strip())
                    await self.handle_packet(player_connection, message)
                except json.JSONDecodeError as e:
                    print(f"Invalid JSON from {client_addr}: {e}")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            if writer in self.clients:
                await player_state.replicate(self, "playerleave")
                del self.clients[writer]
                del self.id_to_conn[player_state.id]

            writer.close()
            await writer.wait_closed()
            print(f"Client {client_addr} disconnected")
