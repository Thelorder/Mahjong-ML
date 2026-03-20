"""
core/game_state.py
 
Owns the complete state of one Mahjong round and exposes a clean
action interface for human players, rule-based agents, and RL agents.
 
Typical call sequence
─────────────────────
    gs = GameState()
    gs.start_round()
 
    while not gs.is_round_over():
        legal = gs.get_legal_actions()          # what the current actor can do
        action = agent.choose(legal)            # agent picks one
        result = gs.apply_action(action)        # game advances
        obs    = gs.get_observation()           # agent reads new state
 
Key design decisions
────────────────────
- GameState drives the wall and calls player methods.  Player never touches
  the wall directly except through GameState.
- Actions are plain (Action, data) pairs so they serialise easily for RL.
- get_observation() returns only information legally visible to the current
  actor — opponents' hands are hidden.
"""


from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict,List,Optional,Tuple

from .tile import Tile, Suit,Dragon,Wind
from .wall import Wall
from .player import Player,PlayerState

# ===== Action definitions =====

class ActionType(Enum):
    DISCARD = "discard" # discard tile at hand index
    RIICHI = "riichi" # discard + declare riichi
    TSUMO = "tsumo" # self-draw win 
    CONCEALD_KAN = "conceald_kan" # a kan from own hand
    ADDED_KAN = "added_kan" # extend pon -> kan
    
    # Call actions 
    RON = "ron" # claim discard win
    CHI = "chi" # claim sequence (left player only)
    PON = "pon" # claim triplet
    OPEN_KAN = "open_kan" # claim quad from discard
    
    # Pass - declined action
    PASS = "pass"