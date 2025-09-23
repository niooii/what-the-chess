import asyncio
import json
import time
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel

from chess.match import Match
from chess.player import PlayerState

from .lobby import Lobby

load_dotenv()


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
> Craft a mirrored two-player strategy ruleset for an 8-by-8 grid world. Each side deploys custom unit types that obey the following framework:
> * Output must be JSON only and validate against the schema {"rulesets": List[Ruleset], "pieces": List[Piece], "starting_pos": List[StartPos]}. Do not include prose outside the JSON. Creating a large amount of unique pieces is encouraged, generally above 6. Unique games with 1/2 pieces must have some mechanic that makes it a fun or interesting game to play, including a unique starting position, unique, never-seen-before abilities for the single/few pieces, etc.
> * A ruleset is either sliding (ray-extended up to `max_range`) or jumping (single hop that ignores blockers). The boolean `jump` selects behaviour.
> * You may compose multiple rulesets for one piece by providing multiple indices in a piece's rulesets: List[int] array. For example, creating a queen that can also jump like a knight.
> * Movement generators `target_moves` and `target_takes` MUST be Python function definitions named `mv_func` and `tk_func`. They accept an integer `n` (the unit’s own action count, starting at 1) and RETURN a List[Tuple[int,int]] of (dx, dy) offsets relative to the owning side’s forward direction (positive y away from the owning player).
> * These functions MUST be valid Python 3 code and MUST compile. Prefer a single-line `return ...` expression after the function header. No imports or external names.
> * These functions MUST NOT reference each other, for example, tk_func cannot call mv_func within it, as they are independently processed.
> * Encode alternating/conditional patterns USING `n` inside `mv_func`/`tk_func` (e.g. parity, thresholds). DO NOT compose multiple rulesets just to alternate; compose rulesets only to combine different behaviours (e.g. add jumps to a slider) or to separate movement vs capture targeting.
> * Sliding offsets are expanded internally according to `max_range`. For a two-step opening advance followed by one-step advances, set `max_range = 1` and return both distances in `mv_func` on the first action, e.g.:
>   def mv_func(n: int): return [(0, m) for m in ([1, 2] if n == 1 else [1])]
>   def tk_func(n: int): return [(-1, 1), (1, 1)]
> * Example of parity-based alternation encoded in one ruleset:
>   def mv_func(n: int): return [(0,1),(0,-1),(1,0),(-1,0)] if n % 2 == 0 else [(1,1),(1,-1),(-1,1),(-1,-1)]
>   def tk_func(n: int): return mv_func(n)
> * `starting_pos` lists placements for one side only; the engine mirrors across the horizontal axis for the opponent. Deviating from the standard chess format is encouraged (E.g. a triangle/trapezoid shaped starting configuration, or an arc, or something strategically challenging) to make the game more interesting or follow the theme better. 
> * This includes generally avoiding a piece on the front rank that just moves forward and captures diagonally, as that is a chess pawn. Be more creative  
> * Honour directionality, blockers, and occupancy typical of grid tactics: slides stop at the first blocker, moves require empty destinations, captures require opponents.
> Name units creatively (avoid classic terms), keep descriptions vivid but mechanics precise and machine-parseable. Prioritize unqiueness, avoiding creating pieces with the same moveset of classical chess, and creating pieces that will lead to fun strategy, balancing those pieces. For example, if there is a piece that is unable to move but can capture pieces, then it should have a wide range of capture. If there is a piece that is unable to capture, then it should have a wide range of movement (e.g. a large circle or something similar, circle rulesets can be made with a slide ruleset, and the appropriate movement vectors). 
> You MUST avoid creating pieces with the same moveset of classical chess at any cost as that ruins uniqueness (for example, a ruleset where a piece moves two times forward on the first turn, and captures one diagonally, which belongs to a pawn in classical chess). 
"""

    async def start(self):
        server = await asyncio.start_server(self.handle_client, "0.0.0.0", 9090)
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
            print(f"Registered new player {packet['name']}")
            await player.player_state.replicate(self, "playermod", exclude_self=False)

        elif mtype == "move":
            from_coord = packet["from"]
            to_coord = packet["to"]

            if player.match and player.match.game:
                success = player.match.game.move_piece(
                    (from_coord[0], from_coord[1]), (to_coord[0], to_coord[1])
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
                    await other_player.send(
                        {"type": "move", "from": from_coord, "to": to_coord}
                    )
                    print("AWFAWAGESSG")

                print("AWFW")

        elif mtype == "matchcreate":
            if player.match is not None:
                return

            match = Match(p1=player.player_state)
            self.matches[player.player_state.id] = match
            player.match = match

            await self.broadcast(
                {"type": "matchcreate", "host_id": player.player_state.id}
            )

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

            await self.broadcast(
                {"type": "matchremove", "host_id": other.player_state.id}
            )

            await player.send(
                {"type": "matchstart", "other_id": other.player_state.id, "team": 1}
            )
            await other.send(
                {"type": "matchstart", "other_id": player.player_state.id, "team": 0}
            )

            try:
                response = self.gemini.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=self.gemini_prompt,
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": ChessConfig,
                    },
                )
                config_json = response.text
            except Exception as exc:
                error_msg = f"Failed to generate match config: {exc}"
                print(error_msg)
                await player.send({"type": "error", "message": error_msg})
                await other.send({"type": "error", "message": error_msg})
                return

            if other.match:
                from chess.Game import Game

                other.match.game = Game.from_config(
                    config_json, [player.player_state, other.player_state]
                )

            await player.send({"type": "matchconfig", "config": config_json})
            await other.send({"type": "matchconfig", "config": config_json})

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
        player_states = [asdict(p.player_state) for p in self.clients.values()]
        await self.send(writer, {"type": "playerlist", "players": player_states})

        # send back all available matches
        match_list = [
            {"host_id": host_id, "host_name": match.p1.name}
            for host_id, match in self.matches.items()
            if match.p2
            is None  # only send matches that are waiting for a second player
        ]
        await self.send(writer, {"type": "matchlist", "matches": match_list})

        await player_state.replicate(self, "playerjoin", exclude_self=False)

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
