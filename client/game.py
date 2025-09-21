import asyncio
import math
from typing import Any, Dict, List, Optional

import pygame
import pygame_gui

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
        self.match_click_areas = {}

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
            relative_rect=pygame.Rect(WINDOW_WIDTH // 2 - 100, WINDOW_HEIGHT // 2 + 50, 200, 40),
            text="Host Match",
            manager=self.ui_manager,
        )
        self.create_match_button.hide()

        # match list area
        self.match_buttons = []

    def draw_title_and_decorations(self):
        font_large = pygame.font.Font(None, 72)
        font_medium = pygame.font.Font(None, 36)

        # slightly animated title with pulse
        pulse_scale = 1 + math.sin(self.title_pulse) * 0.02
        title_text = font_large.render("CHESS", True, COLORS["text"])
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
            subtitle_text = "Funny chess game"

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

        elif event.type == pygame_gui.UI_TEXT_ENTRY_FINISHED:
            if event.ui_element == self.name_input:
                self.player_name = event.text
                if self.player_name.strip():
                    asyncio.create_task(self.send_player_name())

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if self.game_state == "lobby" and hasattr(self, 'match_click_areas'):
                mouse_pos = pygame.mouse.get_pos()
                for host_id, rect in self.match_click_areas.items():
                    if rect.collidepoint(mouse_pos):
                        asyncio.create_task(self.join_match(host_id))
                        break

    async def create_match(self):
        await self.conn.send({"type": "matchcreate"})

    async def join_match(self, host_id):
        await self.conn.send({"type": "matchjoin", "player_id": host_id})

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

    def draw_available_matches(self):
        if not self.connected or self.game_state != "lobby":
            return

        font = pygame.font.Font(None, 24)
        y_offset = WINDOW_HEIGHT // 2 + 100

        for i, (host_id, host_name) in enumerate(self.available_matches.items()):
            match_text = f"{host_name} awaiting opponent"
            color = COLORS["accent_light"] if i % 2 == 0 else COLORS["text_muted"]
            text_surface = font.render(match_text, True, color)
            text_rect = text_surface.get_rect(
                center=(WINDOW_WIDTH // 2, y_offset + i * 30)
            )
            self.screen.blit(text_surface, text_rect)

            # TODO! make them BUTTONS BRO what am i doing
            if not hasattr(self, 'match_click_areas'):
                self.match_click_areas = {}
            self.match_click_areas[host_id] = text_rect

    # the loading screen p much
    def draw_vs_screen(self):
        font_large = pygame.font.Font(None, 72)
        vs_text = f"{self.player_name} VS {self.opponent_name}"
        text_surface = font_large.render(vs_text, True, COLORS["text"])
        text_rect = text_surface.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
        self.screen.blit(text_surface, text_rect)

    def draw_chess_board(self):
        board_size = 600
        board_x = (WINDOW_WIDTH - board_size) // 2
        board_y = (WINDOW_HEIGHT - board_size) // 2
        square_size = board_size // 8

        # draw checkerboard
        for row in range(8):
            for col in range(8):
                color = COLORS["bg_light"] if (row + col) % 2 == 0 else COLORS["accent"]
                square_rect = pygame.Rect(
                    board_x + col * square_size,
                    board_y + row * square_size,
                    square_size,
                    square_size
                )
                pygame.draw.rect(self.screen, color, square_rect)

        # draw border
        pygame.draw.rect(self.screen, COLORS["text"],
                        pygame.Rect(board_x - 2, board_y - 2, board_size + 4, board_size + 4), 2)

        # player names
        font = pygame.font.Font(None, 36)

        # you at bottom right
        you_text = font.render("YOU", True, COLORS["accent_light"])
        you_rect = you_text.get_rect(bottomright=(board_x + board_size + 120, board_y + board_size + 40))
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
            self.draw_available_matches()
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

                # HIDE HTE LOBBY UI STUFF
                self.create_match_button.hide()

                asyncio.create_task(self.vs_screen_timer())

        elif mtype == "matchconfig":
            # recieved match config and start the game
            self.game_state = "game"
            print("Game started with config:", message.get("config", {}))

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
