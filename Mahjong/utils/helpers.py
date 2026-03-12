from typing import List, Optional
from core.tile import Tile, Suit

def is_valid_sequence(tiles: List[Tile]) -> bool:
    """Check if tiles form a valid sequence (chow)"""
    if len(tiles) != 3:
        return False
    
    # Must be same suit
    suit = tiles[0].suit
    if not all(t.suit == suit for t in tiles):
        return False
    
    # Must be suited tiles (not honors)
    if suit in [Suit.WINDS, Suit.DRAGONS]:
        return False
    
    # Check consecutive ranks
    ranks = sorted(t.rank for t in tiles)
    return ranks[0] + 1 == ranks[1] and ranks[1] + 1 == ranks[2]

def is_valid_triplet(tiles: List[Tile]) -> bool:
    """Check if tiles form a valid triplet (pung)"""
    if len(tiles) != 3:
        return False
    
    # All tiles must be identical
    first = tiles[0]
    return all(t == first for t in tiles)

def is_valid_quad(tiles: List[Tile]) -> bool:
    """Check if tiles form a valid quad (kong)"""
    if len(tiles) != 4:
        return False
    
    # All tiles must be identical
    first = tiles[0]
    return all(t == first for t in tiles)