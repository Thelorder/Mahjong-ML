"""
Mahjong Game - Main Entry Point
"""

from core.game_state import GameState
from ui.console import ConsoleUI

def main():
    """Main game loop"""
    print("=" * 50)
    print("Welcome to Mahjong!")
    print("=" * 50)
    
    # Initialize game
    game = GameState()
    ui = ConsoleUI(game)
    
    # Start game
    ui.start()
    
    # Main game loop
    while not game.is_game_over():
        ui.display_game_state()
        ui.get_player_action()
        game.next_turn()
    
    # Game over
    ui.display_winner()
    print("\nThanks for playing!")

if __name__ == "__main__":
    main()