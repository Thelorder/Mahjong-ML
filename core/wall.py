import random
from typing import List, Optional, Tuple
from .tile import Tile, Suit, Dragon, Wind


class Wall:
    """Represents the draw wall (and dead wall) for a game of Riichi Mahjong."""

    def __init__(self):
        self.tiles: List[Tile] = []
        self.dead_wall: List[Tile] = []
        self._build_wall()

    def _build_wall(self):
        """Create all 136 tiles and shuffle them."""
        for suit in (Suit.BAMBOO, Suit.CHARACTERS, Suit.DOTS):
            for rank in range(1, 10):
                for _ in range(4):
                    self.tiles.append(Tile(suit, rank=rank))

        for wind in Wind:
            for _ in range(4):
                self.tiles.append(Tile(Suit.WINDS, wind=wind))

        for dragon in Dragon:
            for _ in range(4):
                self.tiles.append(Tile(Suit.DRAGONS, dragon=dragon))

        random.shuffle(self.tiles)

    def set_dead_wall(self, count: int = 14):
        """
        Set aside the last `count` tiles as the dead wall.
        Must be called before dealing begins.
        """
        if len(self.tiles) < count:
            raise ValueError(f"Not enough tiles for dead wall (need {count}, have {len(self.tiles)})")
        self.dead_wall = self.tiles[-count:]
        self.tiles = self.tiles[:-count]

    def draw_tile(self, from_dead_wall: bool = False) -> Tile:
        """Draw a tile from the main wall or dead wall."""
        if from_dead_wall:
            if not self.dead_wall:
                raise RuntimeError("Dead wall is empty")
            return self.dead_wall.pop(0)
        else:
            if not self.tiles:
                raise RuntimeError("Main wall is empty")
            return self.tiles.pop(0)

    def deal_starting_hands(self, num_players: int = 4) -> List[List[Tile]]:
        """
        Deal 13 tiles to each player in the standard Riichi draw sequence:
        each player draws 4, 4, 4, then 1 (dealer gets one extra and discards to start).
        Returns a list of hands, one per player (each 13 tiles).
        Dealer (index 0) receives 13 tiles; the game engine should give them the
        14th by drawing from the wall on their first turn.
        """
        if len(self.tiles) < num_players * 13:
            raise RuntimeError("Not enough tiles to deal")

        hands: List[List[Tile]] = [[] for _ in range(num_players)]

        # Three rounds of 4 tiles each
        for _ in range(3):
            for p in range(num_players):
                for _ in range(4):
                    hands[p].append(self.tiles.pop(0))

        # Final round of 1 tile each
        for p in range(num_players):
            hands[p].append(self.tiles.pop(0))

        return hands

    def get_wall_size(self) -> int:
        """Number of tiles remaining in the main wall."""
        return len(self.tiles)

    def get_dead_wall_size(self) -> int:
        """Number of tiles remaining in the dead wall."""
        return len(self.dead_wall)

    def is_empty(self) -> bool:
        """True if the main wall has no tiles left (draw game)."""
        return len(self.tiles) == 0

    def peek_next_tile(self) -> Optional[Tile]:
        """Look at the next tile without drawing it."""
        return self.tiles[0] if self.tiles else None

    def __str__(self) -> str:
        return f"Wall({len(self.tiles)} tiles | dead wall: {len(self.dead_wall)})"