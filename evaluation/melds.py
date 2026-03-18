"""
evaluation/melds.py

Meld validation — pure functions that inspect a list of tiles and determine
whether they form a valid chi (sequence), pon (triplet), or kan (quad).

These replace is_valid_sequence / is_valid_triplet / is_valid_quad in
utils/helpers.py. Import from here going forward.
"""

from typing import List
from core.tile import Tile, Suit


# Suits that can form sequences
_SUITED = {"bamboo", "characters", "dots"}


def is_valid_sequence(tiles: List[Tile]) -> bool:
    """
    Return True if tiles form a valid chi (3 consecutive suited tiles,
    all the same suit).
    """
    if len(tiles) != 3:
        return False
    if not all(t.suit.value in _SUITED for t in tiles):
        return False
    if not all(t.suit.value == tiles[0].suit.value for t in tiles):
        return False
    ranks = sorted(t.rank for t in tiles)
    return ranks[1] == ranks[0] + 1 and ranks[2] == ranks[1] + 1


def is_valid_triplet(tiles: List[Tile]) -> bool:
    """Return True if tiles form a valid pon (3 identical tiles)."""
    if len(tiles) != 3:
        return False
    return all(t == tiles[0] for t in tiles)


def is_valid_quad(tiles: List[Tile]) -> bool:
    """Return True if tiles form a valid kan (4 identical tiles)."""
    if len(tiles) != 4:
        return False
    return all(t == tiles[0] for t in tiles)
