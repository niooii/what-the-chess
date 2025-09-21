import asyncio
import math
from typing import Any, Dict, List, Optional

import pygame
import pygame_gui

from chess.Game import Game
from chess.match import Match
from chess.player import PlayerState
from client.conn import ClientConnection

pygame.init()

WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
FPS = 60

COLORS = {
    "bg_dark": (28, 32, 38),
    "bg_light": (45, 52, 64),
    "accent": (94, 129, 172),
    "accent_light": (129, 161, 193),
    "text": (236, 239, 244),
    "text_muted": (144, 152, 165),
    "input_bg": (67, 76, 94),
    "button_hover": (76, 86, 106),
}

IMAGESDICT = {"lavatile": pygame.image.load("resources/lava.png"),
              "grasstile": pygame.image.load("resources/grass.png")}


class ClientGame:
    def __init__(self, conn: ClientConnection):
        self.conn = conn
        self.players: Dict[int, PlayerState] = {}

        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Chess • Game")
        self.clock = pygame.time.Clock()
        self.running = True

        self.ui_manager = pygame_gui.UIManager((WINDOW_WIDTH, WINDOW_HEIGHT))

        # for animation
        self.time_accumulator = 0
        self.title_pulse = 0

        # bunch of game state
        self.in_lobby = True
        self.player_name = ""
        self.connected = False
        self.available_matches = {}
        self.game_state = "lobby"  # lobby, vs_screen, game
        self.opponent_name = ""
        self.opponent_id = None
        self.grid_size = 8  # configurable grid size
        self.hovered_tile = None  # (x, y) tuple or None
        self.selected_tile = None  # (x, y) tuple or None for piece selection
        self.valid_moves = []  # list of valid moves for selected piece
        self.game: Optional[Game] = None
        self.current_match: Optional[Match] = None
        self.my_team = 0  # 0 for white (host), 1 for black (joiner)

        self.create_lobby_ui()

    def create_lobby_ui(self):
        input_rect = pygame.Rect(
            WINDOW_WIDTH // 2 - 200, WINDOW_HEIGHT // 2 + 50, 400, 50
        )
        self.name_input = pygame_gui.elements.UITextEntryLine(
            relative_rect=input_rect,
            manager=self.ui_manager,
            placeholder_text="Enter your name...",
        )

        # connect button
        button_rect = pygame.Rect(
            WINDOW_WIDTH // 2 - 100, WINDOW_HEIGHT // 2 + 120, 200, 50
        )
        self.connect_button = pygame_gui.elements.UIButton(
            relative_rect=button_rect, text="Join Game", manager=self.ui_manager
        )

        # status label
        status_rect = pygame.Rect(
            WINDOW_WIDTH // 2 - 200, WINDOW_HEIGHT // 2 + 190, 400, 30
        )
        self.status_label = pygame_gui.elements.UILabel(
            relative_rect=status_rect,
            text="Choose your name!",
            manager=self.ui_manager,
        )

        # player count in top left (initially hidden)
        self.player_count_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(20, 20, 300, 30),
            text="",
            manager=self.ui_manager,
        )
        self.player_count_label.hide()

        # create match button (hidden initially)
        self.create_match_button = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(
                WINDOW_WIDTH // 2 - 100, WINDOW_HEIGHT // 2 + 50, 200, 40
            ),
            text="Host Match",
            manager=self.ui_manager,
        )
        self.create_match_button.hide()

        # match list area
        self.match_buttons = {}  # will store {host_id: button}

    def draw_title_and_decorations(self):
        font_large = pygame.font.Font(None, 72)
        font_medium = pygame.font.Font(None, 36)

        # slightly animated title with pulse
        pulse_scale = 1 + math.sin(self.title_pulse) * 0.02
        title_text = font_large.render("Dimensia CHESS", True, COLORS["text"])
        title_rect = title_text.get_rect()

        # scale the title
        scaled_width = int(title_rect.width * pulse_scale)
        scaled_height = int(title_rect.height * pulse_scale)
        scaled_title = pygame.transform.scale(title_text, (scaled_width, scaled_height))
        scaled_rect = scaled_title.get_rect(
            center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 150)
        )

        self.screen.blit(scaled_title, scaled_rect)

        # the main subtitle (either default subtitle or connected as blank)
        if self.connected:
            subtitle_text = f"Connected as {self.player_name}"
        else:
            subtitle_text = "What're the rules again!??!?!?!??!"

        subtitle = font_medium.render(subtitle_text, True, COLORS["text_muted"])
        subtitle_rect = subtitle.get_rect(
            center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 80)
        )
        self.screen.blit(subtitle, subtitle_rect)

        if self.connected:
            rooms_font = pygame.font.Font(None, 28)
            rooms_text = rooms_font.render("rooms", True, COLORS["accent_light"])
            rooms_rect = rooms_text.get_rect(
                center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 10)
            )
            self.screen.blit(rooms_text, rooms_rect)

        # decorative lines around title
        line_y = WINDOW_HEIGHT // 2 - 20
        pygame.draw.line(
            self.screen,
            COLORS["accent"],
            (WINDOW_WIDTH // 2 - 300, line_y),
            (WINDOW_WIDTH // 2 + 300, line_y),
            2,
        )

    def handle_gui_events(self, event):
        self.ui_manager.process_events(event)

        if event.type == pygame.QUIT:
            self.running = False

        elif event.type == pygame_gui.UI_BUTTON_PRESSED:
            if event.ui_element == self.connect_button:
                self.player_name = self.name_input.get_text()
                if self.player_name.strip():
                    asyncio.create_task(self.send_player_name())
            elif event.ui_element == self.create_match_button:
                asyncio.create_task(self.create_match())
            else:
                # check if it's a match button
                for host_id, button in self.match_buttons.items():
                    if event.ui_element == button:
                        asyncio.create_task(self.join_match(host_id))
                        break

        elif event.type == pygame_gui.UI_TEXT_ENTRY_FINISHED:
            if event.ui_element == self.name_input:
                self.player_name = event.text
                if self.player_name.strip():
                    asyncio.create_task(self.send_player_name())

        elif event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = pygame.mouse.get_pos()

            if self.game_state == "game" and hasattr(self, "board_x"):
                # check if click is within the board
                if (
                    self.board_x <= mouse_pos[0] <= self.board_x + self.board_size
                    and self.board_y <= mouse_pos[1] <= self.board_y + self.board_size
                ):

                    # calculate which tile was clicked
                    col = (mouse_pos[0] - self.board_x) // self.square_size
                    display_row = (mouse_pos[1] - self.board_y) // self.square_size

                    # ensure coordinates are within bounds
                    if 0 <= col < self.grid_size and 0 <= display_row < self.grid_size:
                        print("BRANCH 1: Within bounds")
                        # Convert display row back to logical board row
                        logical_row = self.grid_size - 1 - display_row
                        clicked_pos = (logical_row, col)
                        print(f"BRANCH 2: Clicked at logical_row={logical_row}, col={col}, pos={clicked_pos}")

                        if self.game is None:
                            print("BRANCH 3: Game is None!")
                            return

                        print("BRANCH 4: Game exists, getting piece")
                        piece = self.game.board.get_piece(clicked_pos)
                        print(f"BRANCH 5: Piece at {clicked_pos}: {piece}")

                        if self.selected_tile is None:
                            print("BRANCH 6: No piece currently selected")
                            # No piece selected, try to select this tile
                            if piece is not None:
                                print(f"BRANCH 7: Found piece: {piece.name}, team: {piece.team}")
                                # Only select our own pieces
                                if piece.team == self.my_team:
                                    print(f"BRANCH 8: OUR PIECE! Selecting piece at {clicked_pos}")
                                    self.selected_tile = clicked_pos
                                    self.valid_moves = self.game.board.get_valid_actions(clicked_pos) or []
                                    print(f"BRANCH 9: Selected tile set to: {self.selected_tile}")
                                    print(f"BRANCH 10: Valid moves: {self.valid_moves}")
                                else:
                                    print(f"BRANCH 11: Enemy piece, team {piece.team}, not our team {self.my_team}")
                            else:
                                print("BRANCH 12: No piece at clicked position")
                        else:
                            print(f"BRANCH 13: Piece already selected: {self.selected_tile}")
                            # Piece is selected
                            if clicked_pos in self.valid_moves:
                                print("BRANCH 14: Valid move - applying locally then sending to server")
                                # Apply move locally first
                                success = self.game.move_piece(self.selected_tile, clicked_pos)
                                if success:
                                    # Update match move counter
                                    if self.current_match:
                                        self.current_match.move += 1
                                    # Send to server
                                    asyncio.create_task(self.send_move(self.selected_tile, clicked_pos))
                                self.selected_tile = None
                                self.valid_moves = []
                            else:
                                print("BRANCH 15: Not a valid move, checking other options")
                                # Check if clicking on another piece to select
                                if self.game and self.game.board.get_piece(clicked_pos):
                                    print("BRANCH 16: Clicking on another piece")
                                    piece = self.game.board.get_piece(clicked_pos)
                                    if piece.team == self.my_team:
                                        print("BRANCH 17: Selecting new piece")
                                        # Select new piece
                                        self.selected_tile = clicked_pos
                                        self.valid_moves = self.game.board.get_valid_actions(clicked_pos) or []
                                    else:
                                        print("BRANCH 18: Enemy piece - deselecting")
                                        # Deselect
                                        self.selected_tile = None
                                        self.valid_moves = []
                                else:
                                    print("BRANCH 19: Empty square - deselecting")
                                    # Empty square - deselect
                                    self.selected_tile = None
                                    self.valid_moves = []
                    else:
                        print("BRANCH 20: Click outside bounds")

        elif event.type == pygame.MOUSEMOTION:
            if self.game_state == "game" and hasattr(self, "board_x"):
                mouse_pos = pygame.mouse.get_pos()

                # check if mouse is within the board
                if (
                    self.board_x <= mouse_pos[0] <= self.board_x + self.board_size
                    and self.board_y <= mouse_pos[1] <= self.board_y + self.board_size
                ):

                    # calculate which tile is being hovered
                    col = (mouse_pos[0] - self.board_x) // self.square_size
                    display_row = (mouse_pos[1] - self.board_y) // self.square_size

                    # ensure coordinates are within bounds
                    if 0 <= col < self.grid_size and 0 <= display_row < self.grid_size:
                        # Convert display row back to logical board row
                        logical_row = self.grid_size - 1 - display_row
                        self.hovered_tile = (col, logical_row)
                    else:
                        self.hovered_tile = None
                else:
                    self.hovered_tile = None
            else:
                self.hovered_tile = None

    async def create_match(self):
        self.my_team = 0  # Host is white (team 0)
        print(f"TEAM: Set my_team to {self.my_team} (host)")
        # Create local match with self as p1
        current_player = None
        for player in self.players.values():
            if player.name == self.player_name:
                current_player = player
                break
        if current_player:
            self.current_match = Match(p1=current_player, p2=None, move=0, game=None)
            print(f"MATCH: Created match as host: {self.current_match}")
        await self.conn.send({"type": "matchcreate"})

    async def join_match(self, host_id):
        self.my_team = 1  # Joiner is black (team 1)
        print(f"TEAM: Set my_team to {self.my_team} (joiner)")
        await self.conn.send({"type": "matchjoin", "player_id": host_id})

    async def send_move(self, from_pos, to_pos):
        await self.conn.send({
            "type": "move",
            "from": [from_pos[0], from_pos[1]],
            "to": [to_pos[0], to_pos[1]]
        })

    async def send_player_name(self):
        if not self.player_name.strip():
            self.status_label.set_text("Please enter a name first")
            return

        self.status_label.set_text("Sending name...")
        self.connect_button.disable()

        await self.conn.send({"type": "name", "name": self.player_name})
        self.connected = True
        self.status_label.hide()
        self.name_input.hide()
        self.connect_button.hide()
        self.player_count_label.show()
        self.create_match_button.show()
        self.update_player_count()

    def update_player_count(self):
        player_count = len(self.players)
        self.player_count_label.set_text(f"Players online: {player_count}")

    def update_match_buttons(self):
        if not self.connected or self.game_state != "lobby":
            return

        # remove buttons for matches that no longer exist
        to_remove = []
        for host_id, button in self.match_buttons.items():
            if host_id not in self.available_matches:
                button.kill()
                to_remove.append(host_id)
        for host_id in to_remove:
            del self.match_buttons[host_id]

        # create buttons for new matches
        y_offset = WINDOW_HEIGHT // 2 + 100
        for i, (host_id, host_name) in enumerate(self.available_matches.items()):
            if host_id not in self.match_buttons:
                button_rect = pygame.Rect(
                    WINDOW_WIDTH // 2 - 150, y_offset + i * 50, 300, 40
                )
                button = pygame_gui.elements.UIButton(
                    relative_rect=button_rect,
                    text=f"Join {host_name}",
                    manager=self.ui_manager,
                )
                self.match_buttons[host_id] = button

    # the loading screen p much
    def draw_vs_screen(self):
        font_large = pygame.font.Font(None, 72)
        vs_text = f"{self.player_name} VS {self.opponent_name}"
        text_surface = font_large.render(vs_text, True, COLORS["text"])
        text_rect = text_surface.get_rect(
            center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2)
        )
        self.screen.blit(text_surface, text_rect)

    def draw_chess_board(self):
        board_size = 600
        board_x = (WINDOW_WIDTH - board_size) // 2
        board_y = (WINDOW_HEIGHT - board_size) // 2
        square_size = board_size // self.grid_size

        # store board position for click detection
        self.board_x = board_x
        self.board_y = board_y
        self.board_size = board_size
        self.square_size = square_size

        # draw checkerboard (flipped so row 0 at bottom)
        for row in range(self.grid_size):
            for col in range(self.grid_size):
                color = COLORS["bg_light"] if (row + col) % 2 == 0 else COLORS["accent"]
                display_row = self.grid_size - 1 - row  # flip vertically
                square_rect = pygame.Rect(
                    board_x + col * square_size,
                    board_y + display_row * square_size,
                    square_size,
                    square_size,
                )
                pygame.draw.rect(self.screen, color, square_rect)

        # draw valid move highlights (red squares)
        for move_pos in self.valid_moves:
            move_row, move_col = move_pos
            display_row = self.grid_size - 1 - move_row  # flip vertically
            move_rect = pygame.Rect(
                board_x + move_col * square_size,
                board_y + display_row * square_size,
                square_size,
                square_size,
            )
            pygame.draw.rect(self.screen, (255, 100, 100), move_rect, 3)

        # draw selection outline (selected piece border)
        if self.selected_tile:
            selected_row, selected_col = self.selected_tile
            display_row = self.grid_size - 1 - selected_row  # flip vertically
            selected_rect = pygame.Rect(
                board_x + selected_col * square_size,
                board_y + display_row * square_size,
                square_size,
                square_size,
            )
            pygame.draw.rect(self.screen, COLORS["accent"], selected_rect, 3)

        # draw hover outline
        if self.hovered_tile:
            hover_col, hover_row = self.hovered_tile
            display_row = self.grid_size - 1 - hover_row  # flip vertically
            hover_rect = pygame.Rect(
                board_x + hover_col * square_size,
                board_y + display_row * square_size,
                square_size,
                square_size,
            )
            pygame.draw.rect(self.screen, COLORS["text"], hover_rect, 2)

        # draw pieces
        if self.game and self.game.board:
            piece_font = pygame.font.Font(None, 24)
            piece_count = 0
            for row in range(self.grid_size):
                for col in range(self.grid_size):
                    piece = self.game.board.get_piece((row, col))
                    if piece is not None:
                        piece_count += 1
                        piece_text = piece.name[:4].upper()
                        color = COLORS["accent_light"] if piece.team == 0 else COLORS["text_muted"]
                        text_surface = piece_font.render(piece_text, True, color)
                        display_row = self.grid_size - 1 - row  # flip vertically
                        text_rect = text_surface.get_rect(
                            center=(
                                board_x + col * square_size + square_size // 2,
                                board_y + display_row * square_size + square_size // 2
                            )
                        )
                        self.screen.blit(text_surface, text_rect)
            if piece_count == 0:
                print("No pieces found on board!")

        # draw border
        pygame.draw.rect(
            self.screen,
            COLORS["text"],
            pygame.Rect(board_x - 2, board_y - 2, board_size + 4, board_size + 4),
            2,
        )

        # player names
        font = pygame.font.Font(None, 36)

        # you at bottom right
        you_text = font.render("YOU", True, COLORS["accent_light"])
        you_rect = you_text.get_rect(
            bottomright=(board_x + board_size + 120, board_y + board_size + 40)
        )
        self.screen.blit(you_text, you_rect)

        # opponent name (top left)
        opp_text = font.render(self.opponent_name, True, COLORS["text_muted"])
        opp_rect = opp_text.get_rect(topleft=(board_x - 120, board_y - 40))
        self.screen.blit(opp_text, opp_rect)

    def render_gui(self, time_delta):
        # clear screen w the color thing
        self.screen.fill(COLORS["bg_dark"])

        if self.game_state == "lobby":
            self.draw_title_and_decorations()
            self.update_match_buttons()
        elif self.game_state == "vs_screen":
            self.draw_vs_screen()
        elif self.game_state == "game":
            self.draw_chess_board()

        self.ui_manager.draw_ui(self.screen)

        pygame.display.flip()

    async def game_loop(self):
        while self.running:
            time_delta = self.clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                self.handle_gui_events(event)

            # update UI manager
            self.ui_manager.update(time_delta)
            self.time_accumulator += time_delta
            self.title_pulse += time_delta * 2

            self.render_gui(time_delta)

            await asyncio.sleep(0.001)

        pygame.quit()

    async def handle_packet(self, message: Dict[str, Any]):
        mtype = message["type"]

        if mtype == "playerjoin":
            player: PlayerState = PlayerState(**message["player"])
            self.players[player.id] = player
            print(f"New player joined the server: {player.name}:{player.id}")

            if self.connected:
                self.update_player_count()

        elif mtype == "playerleave":
            player: PlayerState = PlayerState(**message["player"])
            print(f"{player.name}:{player.id} left the server")
            if player.id in self.players:
                del self.players[player.id]

            # remove from available matches if they were hosting
            if player.id in self.available_matches:
                del self.available_matches[player.id]

            if self.connected:
                self.update_player_count()

        elif mtype == "playermod":
            player: PlayerState = PlayerState(**message["player"])
            self.players[player.id] = player

        elif mtype == "playerlist":
            # update playerlist
            self.players.update(
                {pd["id"]: PlayerState(**pd) for pd in message["players"]}
            )

            if self.connected:
                self.update_player_count()

        elif mtype == "matchcreate":
            host_id = message["host_id"]
            if host_id in self.players:
                host_name = self.players[host_id].name
                self.available_matches[host_id] = host_name

        elif mtype == "matchlist":
            self.available_matches.update(
                {md["host_id"]: md["host_name"] for md in message["matches"]}
            )

        elif mtype == "matchremove":
            host_id = message["host_id"]
            if host_id in self.available_matches:
                del self.available_matches[host_id]

        elif mtype == "matchstart":
            other_id = message["other_id"]
            if other_id in self.players:
                self.opponent_name = self.players[other_id].name
                self.opponent_id = other_id
                self.game_state = "vs_screen"

                # Update current match with both players
                current_player = None
                other_player = self.players[other_id]
                for player in self.players.values():
                    if player.name == self.player_name:
                        current_player = player
                        break

                if current_player:
                    if self.my_team == 0:  # Host
                        self.current_match = Match(p1=current_player, p2=other_player, move=0, game=None)
                        print(f"MATCH: Updated match as host with both players: {self.current_match}")
                    else:  # Joiner
                        self.current_match = Match(p1=other_player, p2=current_player, move=0, game=None)
                        print(f"MATCH: Created match as joiner with both players: {self.current_match}")

                # HIDE HTE LOBBY UI STUFF
                self.create_match_button.hide()

                # hide all match buttons
                for button in self.match_buttons.values():
                    button.hide()

                asyncio.create_task(self.vs_screen_timer())

        elif mtype == "matchconfig":
            # recieved match config and start the game
            config_json = message.get("config", "{}")
            players = [self.players[self.opponent_id]] if self.opponent_id else []
            print(f"Creating game with config: {config_json[:100]}...")
            self.game = Game.from_config(config_json, players)
            print(f"Game created: {self.game}")
            print(f"Game board: {self.game.board}")

            # Store game in current match
            if self.current_match:
                self.current_match.game = self.game
                print(f"Match updated with game: {self.current_match}")

            self.game_state = "game"
            print("Game started with config:", config_json[:100])

        elif mtype == "move":
            # opponent's move echoed back from server
            from_coord = message["from"]
            to_coord = message["to"]

            if self.game:
                self.game.move_piece(
                    (from_coord[0], from_coord[1]),
                    (to_coord[0], to_coord[1])
                )
                # Update match move counter
                if self.current_match:
                    self.current_match.move += 1
                # Clear selection after opponent move
                self.selected_tile = None
                self.valid_moves = []

        elif mtype == "error":
            # random server errors
            error_msg = message.get("message", "Unknown error")
            print(f"Server error: {error_msg}")
            if hasattr(self, "status_label") and self.status_label.visible:
                self.status_label.set_text(f"Error: {error_msg}")

    async def vs_screen_timer(self):
        await asyncio.sleep(2)
        if self.game_state == "vs_screen":
            pass

    async def run(self):
        await asyncio.gather(self.conn.listen(self.handle_packet), self.game_loop())
