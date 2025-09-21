import asyncio
import json
import os
import time
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field

from chess.match import Match
from chess.player import PlayerState

from .lobby import Lobby

load_dotenv()

DEFAULT_CONFIG = """{"rulesets": [{"jump": false, "target_moves": "def mv_func(n: int): return [(0, 1), (0, 2)] if n == 1 else [(0, 1)]", "target_takes": "def tk_func(n: int): return [(-1, 1), (1, 1)]", "max_range": 1}, {"jump": false, "target_moves": "def mv_func(n: int): return [(0, 1), (0, -1), (1, 0), (-1, 0)]", "target_takes": "def tk_func(n: int): return [(0, 1), (0, -1), (1, 0), (-1, 0)]", "max_range": 7}, {"jump": false, "target_moves": "def mv_func(n: int): return [(1, 1), (1, -1), (-1, 1), (-1, -1)]", "target_takes": "def tk_func(n: int): return [(1, 1), (1, -1), (-1, 1), (-1, -1)]", "max_range": 7}, {"jump": true, "target_moves": "def mv_func(n: int): return [(1, 2), (1, -2), (-1, 2), (-1, -2), (2, 1), (2, -1), (-2, 1), (-2, -1)]", "target_takes": "def tk_func(n: int): return [(1, 2), (1, -2), (-1, 2), (-1, -2), (2, 1), (2, -1), (-2, 1), (-2, -1)]", "max_range": 1}, {"jump": true, "target_moves": "def mv_func(n: int): return [(0,1),(0,-1),(1,0),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)]", "target_takes": "def tk_func(n: int): return [(0,1),(0,-1),(1,0),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)]", "max_range": 1}, {"jump": false, "target_moves": "def mv_func(n: int): return [(0,1),(0,-1),(1,0),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)]", "target_takes": "def tk_func(n: int): return [(0,1),(0,-1),(1,0),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)]", "max_range": 2}], "pieces": [{"name": "Spirit Scout", "desc": "A nimble, forward-moving piece that advances steadily, but can only capture diagonally.", "move_desc": "Moves one square forward, or two squares forward on its first move. Captures one square diagonally forward.", "rulesets": [0]}, {"name": "Glimmer Rook", "desc": "An ethereal piece moving in straight lines, leaving a shimmering trail.", "move_desc": "Moves any number of squares horizontally or vertically.", "rulesets": [1]}, {"name": "Shadow Bishop", "desc": "A cryptic piece darting across the diagonals, always staying on its chosen color.", "move_desc": "Moves any number of squares diagonally.", "rulesets": [2]}, {"name": "Stalker Knight", "desc": "A sneaky, unpredictable jumper, striking from unexpected angles.", "move_desc": "Jumps in an 'L' shape: two squares in one cardinal direction, then one square perpendicularly.", "rulesets": [3]}, {"name": "Phantom Queen", "desc": "The most powerful piece, combining the swiftness of the Glimmer Rook and the cunning of the Shadow Bishop.", "move_desc": "Moves any number of squares horizontally, vertically, or diagonally.", "rulesets": [1, 2]}, {"name": "King Sovereign", "desc": "The royal piece, whose safety is paramount. It moves slowly but deliberately.", "move_desc": "Moves one square in any direction (horizontally, vertically, or diagonally).", "rulesets": [4]}, {"name": "Mystic Charger", "desc": "A guardian with limited reach but surprising mobility, combining a short slide with a knight's jump.", "move_desc": "Moves up to two squares in any direction (horizontally, vertically, or diagonally), AND also jumps like a Stalker Knight.", "rulesets": [5, 3]}], "starting_pos": [{"x": 0, "y": 1, "piece": 0}, {"x": 1, "y": 1, "piece": 0}, {"x": 2, "y": 1, "piece": 0}, {"x": 3, "y": 1, "piece": 0}, {"x": 4, "y": 1, "piece": 0}, {"x": 5, "y": 1, "piece": 0}, {"x": 6, "y": 1, "piece": 0}, {"x": 7, "y": 1, "piece": 0}, {"x": 0, "y": 0, "piece": 1}, {"x": 7, "y": 0, "piece": 1}, {"x": 1, "y": 0, "piece": 6}, {"x": 6, "y": 0, "piece": 6}, {"x": 2, "y": 0, "piece": 2}, {"x": 5, "y": 0, "piece": 2}, {"x": 3, "y": 0, "piece": 4}, {"x": 4, "y": 0, "piece": 5}]}"""

# structured schema for gemini
class Ruleset(BaseModel):
    jump: bool
    target_moves: str
    target_takes: str
    max_range: int
class Piece(BaseModel):
    name: str
    desc: str
    move_desc: str
    rulesets: List[int]

class StartPos(BaseModel):
    x: int
    y: int
    piece: int  # index into pieces

class ChessConfig(BaseModel):
    rulesets: List[Ruleset]
    pieces: List[Piece]
    starting_pos: List[StartPos]

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
        
        self.gemini = genai.Client()
        self.gemini_prompt = """
> Generate a fun and random chess variant, that takes place on an 8x8 chessboard. The structure of pawns on the front rank does not need to be followed. You must deviate from classical chess structure in favor of creativity, and do not include any classical chess pieces.
> * Output must follow the `ChessGame` schema.
> * Each ruleset is either **jumping** (knight-like) or **sliding** (bishop/rook/queen-like). Sliding rules respect `max_range`.
> * `target_moves` and `target_takes` are Python functions mapping `move_num → List[Tuple[int,int]]`. For pawns, moves differ from takes; for most pieces they match. usually, these will be the same (eg. bishop, rook, queen), but this will differ for pawns e.g. target_moves(1) -> [(0, 1), (0, 2)], target_moves(...) -> [(0,1)], target_takes(...) -> [(-1, 1), (1, 1)]. The direction vectors are relative to the side the player is on. These functions should be defined in working python code, with the name of the target_moves function in code being def mv_func(n: int)..., and target_takes being tk_func... Incorporate unique mechanics based on the current move number of the piece, an example is an oscilating piece that moves on a different axis based on whether the num is even or odd, etc. The function must be on ONE LINE such that it does not encounter any parsing errors when loading, or contain explicit newline characters.
> * Direction vectors are **relative to the player’s side**: each player sees their pieces starting at the bottom.
> * `pieces` reference rulesets by index, and multiple movesets can be composed into one piece, including mixing jumping and sliding.
> * `starting_pos` maps `(x,y)` → piece index. Only needs to be defined for a single side, as it will be mirrored on the other side.
> * ``
> Be creative with names, descriptions, and moves."""


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
        print(f"Processing packet for {player.player_state.name}: {packet}")
        if mtype == "name":
            player.player_state.name = packet["name"]
            print(f"Registered new player {packet["name"]}")
            await player.player_state.replicate(
                self, "playermod", exclude_self=False
            )

        elif mtype == "move":
            from_coord = packet["from"]
            to_coord = packet["to"]

            if player.match and player.match.game:
                success = player.match.game.move_piece(
                    (from_coord[0], from_coord[1]),
                    (to_coord[0], to_coord[1])
                )

                print(f"{player.match.p1.name}")
                print(f"{player.match.p2.name}")
                # Find the other player in the match and echo the move
                other_player = None
                if player.match.p1 and player.match.p1.id != player.player_state.id:
                    other_player = self.id_to_conn.get(player.match.p1.id)
                elif player.match.p2 and player.match.p2.id != player.player_state.id:
                    other_player = self.id_to_conn.get(player.match.p2.id)

                print("got it")
                if other_player:
                    await other_player.send({
                        "type": "move",
                        "from": from_coord,
                        "to": to_coord
                    })
                    print("AWFAWAGESSG");

                print("AWFW")



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

            del self.matches[other.player_state.id]
            player.match = other.match
            player.match.p2 = player.player_state


            await self.broadcast({"type": "matchremove", "host_id": other.player_state.id})

            await player.send({"type": "matchstart", "other_id": other.player_state.id, "team": 1})
            await other.send({"type": "matchstart", "other_id": player.player_state.id, "team": 0})

            response = self.gemini.models.generate_content(
                model="gemini-2.5-flash",
                contents=self.gemini_prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": ChessConfig,
                },
            )

            config = response.text
            # config = DEFAULT_CONFIG
            print(config)

            if other.match:
                from chess.Game import Game
                other.match.game = Game.from_config(config, [player.player_state, other.player_state])

            await player.send({"type": "matchconfig", "config": config})
            await other.send({"type": "matchconfig", "config": config})


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

        # send back all available matches
        match_list = [
            {"host_id": host_id, "host_name": match.p1.name}
            for host_id, match in self.matches.items()
            if match.p2 is None  # only send matches that are waiting for a second player
        ]
        await self.send(writer, {"type": "matchlist", "matches": match_list})

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
