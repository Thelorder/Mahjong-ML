"""
evaluation/hand_checker.py

Pure hand-evaluation functions — no Player object, no game state.
Called by Player, GameState, and the RL agent's reward function.

Public API:
    get_all_tiles()                          -> List[Tile]
    is_complete_hand(tiles, meld_tiles)      -> bool
    is_tenpai(tiles, meld_tiles)             -> bool
    get_wait_tiles(tiles, meld_tiles)        -> Set[Tile]
    sort_key(tile)                           -> tuple   (shared sort helper)
"""

from typing import List, Set
from core.tile import Tile, Suit, Wind, Dragon


# ---------------------------------------------------------------------------
# Shared sort key
# ---------------------------------------------------------------------------

_SUIT_ORDER = {"bamboo": 0, "characters": 1, "dots": 2, "winds": 3, "dragons": 4}


def sort_key(tile: Tile) -> tuple:
    """Bamboo → Characters → Dots → Winds → Dragons, then by rank."""
    return (_SUIT_ORDER[tile.suit.value], tile.rank or 0)


# ---------------------------------------------------------------------------
# Tile catalogue
# ---------------------------------------------------------------------------

def get_all_tiles() -> List[Tile]:
    """One instance of each of the 34 unique tile types."""
    tiles: List[Tile] = []
    for suit in (Suit.BAMBOO, Suit.CHARACTERS, Suit.DOTS):
        for rank in range(1, 10):
            tiles.append(Tile(suit, rank=rank))
    for wind in Wind:
        tiles.append(Tile(Suit.WINDS, wind=wind))
    for dragon in Dragon:
        tiles.append(Tile(Suit.DRAGONS, dragon=dragon))
    return tiles


# ---------------------------------------------------------------------------
# Core completeness check
# ---------------------------------------------------------------------------

def is_complete_hand(tiles: List[Tile], meld_tiles: int = 0) -> bool:
    """
    Return True if `tiles` (pre-sorted) + already-committed meld tiles
    form a complete winning hand (4 melds + 1 pair = 14 tiles total).

    Args:
        tiles:      Tiles currently in hand, sorted with sort_key.
        meld_tiles: Count of tiles already locked in open/concealed melds.
    """
    if len(tiles) + meld_tiles != 14:
        return False
    if len(tiles) == 0:
        return True

    for i in range(len(tiles) - 1):
        if tiles[i] == tiles[i + 1]:
            remaining = tiles[:i] + tiles[i + 2:]
            if _check_melds_only(remaining, meld_tiles + 2):
                return True

    return False


def _check_melds_only(tiles: List[Tile], counted: int) -> bool:
    """Recursively verify tiles decompose into melds only (no pair needed)."""
    n = len(tiles)

    if n == 0:
        return counted == 14
    if n < 3:
        return False

    first = tiles[0]

    # Triplet
    if tiles[1] == first and tiles[2] == first:
        if _check_melds_only(tiles[3:], counted + 3):
            return True

    # Quad (kan)
    if n >= 4 and tiles[1] == first and tiles[2] == first and tiles[3] == first:
        if _check_melds_only(tiles[4:], counted + 4):
            return True

    # Sequence (suited tiles only)
    if first.suit.value in ("bamboo", "characters", "dots") and first.rank is not None:
        r = first.rank
        found = [0]
        needed = [r + 1, r + 2]
        pos = 1

        while pos < n and len(found) < 3:
            t = tiles[pos]
            if t.suit.value == first.suit.value and t.rank == needed[len(found) - 1]:
                found.append(pos)
            pos += 1

        if len(found) == 3:
            remaining = [tiles[j] for j in range(n) if j not in found]
            if _check_melds_only(remaining, counted + 3):
                return True

    return False


# ---------------------------------------------------------------------------
# Tenpai and wait-tile calculation
# ---------------------------------------------------------------------------

def is_tenpai(tiles: List[Tile], meld_tiles: int = 0) -> bool:
    """
    Return True if this 13-tile hand is one tile away from winning.

    Args:
        tiles:      Tiles currently in hand (any order).
        meld_tiles: Count of tiles already locked in open/concealed melds.
    """
    if len(tiles) != (14 - meld_tiles) - 1:
        return False

    for test_tile in get_all_tiles():
        test_hand = sorted(tiles + [test_tile], key=sort_key)
        if is_complete_hand(test_hand, meld_tiles):
            return True

    return False


def get_wait_tiles(tiles: List[Tile], meld_tiles: int = 0) -> Set[Tile]:
    """
    Return the set of tiles that would complete the hand.

    Args:
        tiles:      Tiles currently in hand (any order).
        meld_tiles: Count of tiles already locked in open/concealed melds.
    """
    waits: Set[Tile] = set()
    for test_tile in get_all_tiles():
        test_hand = sorted(tiles + [test_tile], key=sort_key)
        if is_complete_hand(test_hand, meld_tiles):
            waits.add(test_tile)
    return waits
