import asyncio
import math
from typing import Any, Dict, List, Optional

import pygame
import pygame_gui

from chess.player import PlayerState
from client.conn import ClientConnection

# Initialize Pygame
pygame.init()

# Constants
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
FPS = 60

# Color palette - liminal, muted tones
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

        # Pygame GUI setup
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Chess • Game")
        self.clock = pygame.time.Clock()
        self.running = True

        # UI Manager for GUI elements
        self.ui_manager = pygame_gui.UIManager((WINDOW_WIDTH, WINDOW_HEIGHT))

        # Animation variables
        self.time_accumulator = 0
        self.title_pulse = 0

        # Game state
        self.in_lobby = True
        self.player_name = ""

        # Create initial UI elements
        self.create_lobby_ui()

    def create_lobby_ui(self):
        """Create UI elements for lobby screen"""
        # Name input field
        input_rect = pygame.Rect(
            WINDOW_WIDTH // 2 - 200, WINDOW_HEIGHT // 2 + 50, 400, 50
        )
        self.name_input = pygame_gui.elements.UITextEntryLine(
            relative_rect=input_rect,
            manager=self.ui_manager,
            placeholder_text="Enter your name...",
        )

        # Connect button
        button_rect = pygame.Rect(
            WINDOW_WIDTH // 2 - 100, WINDOW_HEIGHT // 2 + 120, 200, 50
        )
        self.connect_button = pygame_gui.elements.UIButton(
            relative_rect=button_rect, text="Join Game", manager=self.ui_manager
        )

        # Status label
        status_rect = pygame.Rect(
            WINDOW_WIDTH // 2 - 200, WINDOW_HEIGHT // 2 + 190, 400, 30
        )
        self.status_label = pygame_gui.elements.UILabel(
            relative_rect=status_rect,
            text="Enter your name to begin",
            manager=self.ui_manager,
        )

    def draw_title_and_decorations(self):
        """Draw the main title and decorative elements"""
        # Title
        font_large = pygame.font.Font(None, 72)
        font_medium = pygame.font.Font(None, 36)

        # Animated title with subtle pulse
        pulse_scale = 1 + math.sin(self.title_pulse) * 0.02
        title_text = font_large.render("CHESS", True, COLORS["text"])
        title_rect = title_text.get_rect()

        # Scale the title slightly
        scaled_width = int(title_rect.width * pulse_scale)
        scaled_height = int(title_rect.height * pulse_scale)
        scaled_title = pygame.transform.scale(title_text, (scaled_width, scaled_height))
        scaled_rect = scaled_title.get_rect(
            center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 150)
        )

        self.screen.blit(scaled_title, scaled_rect)

        # Subtitle
        subtitle = font_medium.render("Enter the Arena", True, COLORS["text_muted"])
        subtitle_rect = subtitle.get_rect(
            center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 80)
        )
        self.screen.blit(subtitle, subtitle_rect)

        # Decorative lines around title
        line_y = WINDOW_HEIGHT // 2 - 20
        pygame.draw.line(
            self.screen,
            COLORS["accent"],
            (WINDOW_WIDTH // 2 - 300, line_y),
            (WINDOW_WIDTH // 2 + 300, line_y),
            2,
        )

    def handle_gui_events(self, event):
        """Handle pygame GUI events"""
        self.ui_manager.process_events(event)

        if event.type == pygame.QUIT:
            self.running = False

        elif event.type == pygame_gui.UI_BUTTON_PRESSED:
            if event.ui_element == self.connect_button:
                self.player_name = self.name_input.get_text()
                if self.player_name.strip():
                    asyncio.create_task(self.send_player_name())

        elif event.type == pygame_gui.UI_TEXT_ENTRY_FINISHED:
            if event.ui_element == self.name_input:
                self.player_name = event.text
                if self.player_name.strip():
                    asyncio.create_task(self.send_player_name())

    async def send_player_name(self):
        """Send player name to server"""
        if not self.player_name.strip():
            self.status_label.set_text("Please enter a name first")
            return

        self.status_label.set_text("Sending name...")
        self.connect_button.disable()

        await self.conn.send({"type": "name", "name": self.player_name})
        self.status_label.set_text(f"Connected as {self.player_name}! Waiting for game...")

    def render_gui(self, time_delta):
        """Render the GUI"""
        # Clear screen with background
        self.screen.fill(COLORS["bg_dark"])

        if self.in_lobby:
            # Draw lobby UI
            self.draw_title_and_decorations()

        # Draw pygame_gui elements
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

            # Update GUI status if we're in lobby
            if self.in_lobby and hasattr(self, "status_label"):
                player_count = len(self.players)
                self.status_label.set_text(f"Players in lobby: {player_count}")

        elif mtype == "playerleave":
            player: PlayerState = PlayerState(**message["player"])
            print(f"{player.name}:{player.id} left the server")
            if player.id in self.players:
                del self.players[player.id]

            if self.in_lobby and hasattr(self, "status_label"):
                player_count = len(self.players)
                self.status_label.set_text(f"Players in lobby: {player_count}")

        elif mtype == "playerlist":
            # update playerlist
            self.players.update(
                {pd["id"]: PlayerState(**pd) for pd in message["players"]}
            )

            if self.in_lobby and hasattr(self, "status_label"):
                player_count = len(self.players)
                self.status_label.set_text(f"Players in lobby: {player_count}")

        elif mtype == "game_start":
            # Transition from lobby to game
            self.in_lobby = False
            print("Game starting!")
            if hasattr(self, "status_label"):
                self.status_label.set_text("Game started!")

        elif mtype == "error":
            # Handle server errors
            error_msg = message.get("message", "Unknown error")
            print(f"Server error: {error_msg}")
            if hasattr(self, "status_label"):
                self.status_label.set_text(f"Error: {error_msg}")

    async def run(self):
        await asyncio.gather(self.conn.listen(self.handle_packet), self.game_loop())
