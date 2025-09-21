#!/usr/bin/env python3
"""
Chess Game Launcher - Start the full GUI chess client
Run this to start the chess game with GUI lobby and networking.
"""

import asyncio
import sys
import os

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(__file__))

try:
    from client.conn import ClientConnection
    from client.game import ClientGame
except ImportError as e:
    print(f"Error importing game modules: {e}")
    print("Make sure you have installed the requirements: pip install -r requirements.txt")
    sys.exit(1)

async def main():
    """Main entry point for the chess game"""
    print("Starting Chess Game...")
    print("Features:")
    print("- Clean modern GUI")
    print("- Networked multiplayer")
    print("- Real-time lobby system")
    print()

    # Create connection and game
    connection = ClientConnection()

    try:
        # Connect to server
        await connection.start()

        # Start the game with GUI
        game = ClientGame(connection)
        await game.run()

    except KeyboardInterrupt:
        print("\nGame closed by user")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if connection.connected:
            connection.connected = False

if __name__ == "__main__":
    asyncio.run(main())