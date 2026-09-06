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
    
@dataclass
class Action:
  """
    A fully-specified action.
 
    Fields used per action type:
        DISCARD / RIICHI : tile_index (index in hand)
        CHI              : tile_index × 2 in hand_indices
        PON / OPEN_KAN   : hand_indices (2 or 3 indices in hand)
        CONCEALED_KAN    : tile_index (start index of 4-of-a-kind in hand)
        ADDED_KAN        : meld_index + tile_index
        TSUMO / RON / PASS: no extra data needed
  """
  type: ActionType
  tile_index: Optional[int] = None # primary hand index
  hand_indices: Optional[List[int]] = None #secondary hand index
  meld_index: Optional[int] = None # for kan
  
  def __repr__(self) -> str:
      parts = [self.type.value]
      if self.tile_index  is not None: parts.append(f"ti={self.tile_index}")
      if self.hand_indices is not None: parts.append(f"hi={self.hand_indices}")
      if self.meld_index   is not None: parts.append(f"mi={self.meld_index}")
      return f"Action({', '.join(parts)})"


# Round Results

class RoundEndReason(Enum):
    TSUMO       = "tsumo"       # self-draw win
    RON         = "ron"         # discard win
    EXHAUSTIVE  = "exhaustive"  # wall ran out (ryuukyoku)
    ABORTIVE    = "abortive"    # special abort (e.g. 9 terminals)

@dataclass
class RoundResult:
    reason:        RoundEndReason
    winner_index:  Optional[int]         = None  # None for draws
    loser_index:   Optional[int]         = None  # None for tsumo / draws
    winning_tile:  Optional[Tile]        = None
    points_delta:  Dict[int, int]        = field(default_factory=dict)


# Turn Phase

class Phase(Enum):
    DRAW          = "draw"          # current player must draw (or has just drawn)
    DISCARD       = "discard"       # current player must discard
    CALL_WINDOW   = "call_window"   # other players may call on the last discard
    ROUND_OVER    = "round_over"


# Observer

@dataclass
class Observation:
    """
    A fully numeric, legally-visible snapshot of the game for the current actor.
 
    hand_counts[34]        : count of each tile type in own hand (0–4)
    discard_counts[4][34]  : count of each tile type in each player's discard pond
    meld_counts[4][34]     : count of each tile type locked in each player's melds
    riichi_flags[4]        : 1 if player i has declared riichi, else 0
    scores[4]              : current point totals
    wall_remaining         : tiles left in main wall
    current_player         : index of the player to act
    round_wind_index       : 0=East 1=South 2=West 3=North
    honba                  : current honba count
    riichi_sticks          : unclaimed riichi bets on the table
    phase                  : current Phase value
    legal_actions          : list of legal Action objects for the current actor
    """
    hand_counts:     List[int]          # length 34
    discard_counts:  List[List[int]]    # shape [4][34]
    meld_counts:     List[List[int]]    # shape [4][34]
    riichi_flags:    List[int]          # length 4
    scores:          List[int]          # length 4
    wall_remaining:  int
    current_player:  int
    round_wind_index: int
    honba:           int
    riichi_sticks:   int
    phase:           Phase
    legal_actions:   List[Action]


# Tile index mapping

def _build_tile_index() -> Dict[str, int]:
    """Map every unique tile repr to a stable 0-33 integer index."""
    idx: Dict[str, int] = {}
    i = 0
    for suit in (Suit.BAMBOO, Suit.CHARACTERS, Suit.DOTS):
        for rank in range(1, 10):
            idx[repr(Tile(suit, rank=rank))] = i
            i += 1
    for wind in Wind:
        idx[repr(Tile(Suit.WINDS, wind=wind))] = i
        i += 1
    for dragon in Dragon:
        idx[repr(Tile(Suit.DRAGONS, dragon=dragon))] = i
        i += 1
    return idx

TILE_INDEX: Dict[str, int] = _build_tile_index()   # frozen at import time
WIND_ORDER: List[Wind] = [Wind.EAST, Wind.SOUTH, Wind.WEST, Wind.NORTH]
 
 
def tile_to_idx(tile: Tile) -> int:
    return TILE_INDEX[repr(tile)]
 
 
def tiles_to_counts(tiles: List[Tile]) -> List[int]:
    counts = [0] * 34
    for tile in tiles:
        counts[tile_to_idx(tile)] += 1
    return counts

# Game State


class GameState:
  """
    Manages one full round of Riichi Mahjong for 4 players.
 
    Attributes (readable by agents / tests):
        players         : List[Player]  (index 0 = dealer / East this round)
        wall            : Wall
        current_player  : int           (index of player to act)
        phase           : Phase
        round_wind      : Wind
        honba           : int
        riichi_sticks   : int           (bets on table, paid to next winner)
        last_discard    : Optional[Tile]
        last_discarder  : Optional[int]
        result          : Optional[RoundResult]  (set when round ends)
  """
  NUM_PLAYERS = 4
  

  def __init__(
        self,
        player_names: Optional[List[str]] = None,
        round_wind: Wind = Wind.EAST,
        honba: int = 0,
        riichi_sticks: int = 0,
        starting_points: int = 25000,
    ):
        names = player_names or [f"Player {i}" for i in range(self.NUM_PLAYERS)]
        assert len(names) == self.NUM_PLAYERS
 
        seat_winds = WIND_ORDER[:self.NUM_PLAYERS]
        self.players: List[Player] = [
            Player(names[i], seat_winds[i]) for i in range(self.NUM_PLAYERS)
        ]
        for p in self.players:
            p.points = starting_points
 
        self.wall            = Wall()
        self.round_wind      = round_wind
        self.honba           = honba
        self.riichi_sticks   = riichi_sticks
 
        self.current_player: int          = 0          # dealer goes first
        self.phase:          Phase        = Phase.DRAW
        self.last_discard:   Optional[Tile] = None
        self.last_discarder: Optional[int]  = None
        self.result:         Optional[RoundResult] = None
 
        # Track which players have passed on the current discard
        self._passed_players: List[int] = []
        
        
        
