"""
core/player.py

Represents a single Riichi Mahjong player.

Responsibilities:
  - Holding and mutating hand state (draw, discard, meld)
  - Tracking riichi / furiten / tenpai status
  - Delegating all hand evaluation to evaluation/hand_checker.py

NOT responsible for:
  - Deciding which action to take  (→ ai/)
  - Scoring a winning hand         (→ evaluation/scoring.py)
  - Orchestrating turns            (→ core/game_state.py)
"""

from typing import List, Optional, Set, Tuple
from enum import Enum

from .tile import Tile, Suit, Wind, Dragon
from .wall import Wall
from evaluation.hand_checker import (
    is_complete_hand,
    is_tenpai,
    get_wait_tiles,
    get_all_tiles,
    sort_key,
)
from evaluation.melds import is_valid_sequence, is_valid_triplet, is_valid_quad


class PlayerState(Enum):
    NORMAL  = "normal"
    TENPAI  = "tenpai"
    RIICHI  = "riichi"
    FURITEN = "furiten"
    WINNING = "winning"


class Player:
    """Represents a Mahjong player under Riichi rules."""

    def __init__(self, name: str, wind: Wind = Wind.EAST):
        self.name  = name
        self.wind  = wind

        # Hand
        self.hand:             List[Tile]       = []
        self.melds:            List[List[Tile]] = []   # open melds
        self.concealed_melds:  List[List[Tile]] = []   # ankan only

        # Discard pond
        self.discards:          List[Tile] = []
        self.discard_indicators: List[str] = []   # " " or "R" (riichi discard)

        # State
        self.state:               PlayerState    = PlayerState.NORMAL
        self.riichi_declared:     bool           = False
        self.riichi_bet:          int            = 1000
        self.riichi_discard_index: Optional[int] = None
        self.in_furiten:          bool           = False
        self.temp_furiten:        bool           = False
        self.is_tenpai:           bool           = False
        self.tenpai_wait_tiles:   Set[Tile]      = set()

        # Score
        self.points: int = 25000

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _meld_tile_count(self) -> int:
        return sum(len(m) for m in self.melds) + sum(len(m) for m in self.concealed_melds)

    def _sort_hand(self):
        self.hand.sort(key=sort_key)

    # ------------------------------------------------------------------ #
    #  Drawing & Discarding                                                #
    # ------------------------------------------------------------------ #

    def draw_tile(self, tile: Tile):
        """Add a tile to hand, re-sort, and update tenpai state."""
        self.hand.append(tile)
        self._sort_hand()
        print(f"{self.name} draws {tile}")
        self.update_tenpai()

    def discard_tile(self, index: int, is_riichi_discard: bool = False) -> Tile:
        """
        Remove and record a tile from hand.
        Pass is_riichi_discard=True to simultaneously lock in Riichi.
        """
        if not (0 <= index < len(self.hand)):
            raise ValueError(f"Invalid discard index {index} (hand size {len(self.hand)})")

        tile = self.hand.pop(index)
        self.discards.append(tile)
        self.discard_indicators.append("R" if is_riichi_discard else " ")

        print(f"{self.name} discards {tile}{' (Riichi)' if is_riichi_discard else ''}")

        if is_riichi_discard:
            remaining = sorted(self.hand, key=sort_key)
            if not is_tenpai(remaining, self._meld_tile_count()):
                print("Warning: riichi discard does not leave hand in tenpai")
            self.riichi_declared     = True
            self.riichi_discard_index = len(self.discards) - 1
            self.points             -= self.riichi_bet
            self.state               = PlayerState.RIICHI
        else:
            self.update_tenpai()

        return tile

    # ------------------------------------------------------------------ #
    #  Kan replacement                                                     #
    # ------------------------------------------------------------------ #

    def _draw_kan_replacement(self, wall: Wall):
        """Draw one replacement tile from the dead wall after any kan."""
        if wall.get_dead_wall_size() == 0:
            print("Warning: dead wall empty — cannot draw replacement")
            return
        replacement = wall.draw_tile(from_dead_wall=True)
        self.draw_tile(replacement)
        print(f"{self.name} draws replacement after kan: {replacement}")

    # ------------------------------------------------------------------ #
    #  Calls (Chi / Pon / Kan)                                             #
    # ------------------------------------------------------------------ #

    def call_chi(self, tile: Tile, hand_indices: List[int]) -> bool:
        """Claim a chi (sequence) using a discarded tile. Blocked in riichi."""
        if self.riichi_declared:
            print(f"{self.name} cannot call Chi after declaring Riichi")
            return False
        if len(hand_indices) != 2:
            return False

        hand_tiles    = [self.hand[i] for i in sorted(hand_indices)]
        potential_meld = hand_tiles + [tile]

        if is_valid_sequence(potential_meld):
            for i in sorted(hand_indices, reverse=True):
                self.hand.pop(i)
            self.melds.append(sorted(potential_meld, key=sort_key))
            print(f"{self.name} calls CHI: {potential_meld}")
            self._sort_hand()
            self.update_tenpai()
            return True

        return False

    def call_pon(self, tile: Tile, hand_indices: List[int]) -> bool:
        """Claim a pon (triplet) using a discarded tile. Blocked in riichi."""
        if self.riichi_declared:
            print(f"{self.name} cannot call Pon after declaring Riichi")
            return False
        if len(hand_indices) != 2:
            return False

        hand_tiles    = [self.hand[i] for i in hand_indices]
        potential_meld = hand_tiles + [tile]

        if is_valid_triplet(potential_meld):
            for i in sorted(hand_indices, reverse=True):
                self.hand.pop(i)
            self.melds.append(potential_meld)
            print(f"{self.name} calls PON: {potential_meld}")
            self._sort_hand()
            self.update_tenpai()
            return True

        return False

    def call_kan(self, tile: Tile, hand_indices: List[int], wall: Wall) -> bool:
        """Claim an open kan (quad) using a discarded tile. Blocked in riichi."""
        if self.riichi_declared:
            print(f"{self.name} cannot call open Kan after declaring Riichi")
            return False
        if len(hand_indices) != 3:
            return False

        hand_tiles = [self.hand[i] for i in hand_indices]
        if not all(t == hand_tiles[0] for t in hand_tiles):
            return False
        if tile != hand_tiles[0]:
            return False

        for i in sorted(hand_indices, reverse=True):
            self.hand.pop(i)
        self.melds.append(hand_tiles + [tile])
        print(f"{self.name} calls KAN: {hand_tiles + [tile]}")
        self.update_tenpai()
        self._draw_kan_replacement(wall)
        return True

    def declare_concealed_kan(self, tile_index: int, wall: Wall) -> bool:
        """
        Declare an ankan (concealed quad) from own hand.
        In riichi, only allowed if the waits are unchanged.
        """
        if tile_index + 4 > len(self.hand):
            return False

        tiles = [self.hand[tile_index + i] for i in range(4)]
        if not all(t == tiles[0] for t in tiles):
            return False

        if self.riichi_declared:
            hand_after = self.hand[:tile_index] + self.hand[tile_index + 4:]
            new_waits  = get_wait_tiles(hand_after, self._meld_tile_count())
            if new_waits != self.tenpai_wait_tiles:
                print(f"{self.name} cannot declare ankan: would change riichi waits")
                return False

        for i in range(3, -1, -1):
            self.hand.pop(tile_index + i)
        self.concealed_melds.append(tiles)
        print(f"{self.name} declares concealed KAN: {tiles}")
        self._draw_kan_replacement(wall)
        return True

    def declare_added_kan(self, meld_index: int, tile_index: int, wall: Wall) -> bool:
        """Upgrade an existing pon to a shouminkan (added kan)."""
        if meld_index >= len(self.melds):
            return False

        meld = self.melds[meld_index]
        if len(meld) != 3:
            return False

        tile = self.hand[tile_index]
        if tile != meld[0]:
            return False

        self.hand.pop(tile_index)
        meld.append(tile)
        print(f"{self.name} upgrades PON to KAN: {meld}")
        self._draw_kan_replacement(wall)
        return True

    # ------------------------------------------------------------------ #
    #  Riichi                                                              #
    # ------------------------------------------------------------------ #

    def can_declare_riichi(self) -> Tuple[bool, str, Optional[List[Tile]]]:
        """
        Check riichi eligibility.
        Returns (can_declare, reason_string, safe_discard_tiles | None).
        """
        if self.riichi_declared:
            return False, "Already in riichi", None
        if self.melds:
            return False, "Cannot riichi with open melds", None
        if self.points < 1000:
            return False, f"Need 1000 points, have {self.points}", None

        meld_count        = self._meld_tile_count()
        expected_hand_size = 14 - meld_count
        if len(self.hand) != expected_hand_size:
            return False, f"Hand size is {len(self.hand)}, expected {expected_hand_size}", None

        safe_discards: List[Tile] = []
        seen: Set[str] = set()
        for i, tile in enumerate(self.hand):
            key = str(tile)
            if key in seen:
                continue
            seen.add(key)
            remaining = self.hand[:i] + self.hand[i + 1:]
            if is_tenpai(remaining, meld_count):
                safe_discards.append(tile)

        if safe_discards:
            return True, "Can declare Riichi", safe_discards
        return False, "No discard leads to tenpai", None

    def declare_riichi(self) -> Tuple[bool, str, Optional[List[Tile]]]:
        """
        Check riichi eligibility and log the result.
        Actual state mutation happens inside discard_tile(is_riichi_discard=True).
        """
        can, reason, safe = self.can_declare_riichi()
        if can:
            print(f"{self.name} is eligible to declare Riichi")
        else:
            print(f"{self.name} cannot declare Riichi: {reason}")
        return can, reason, safe

    # ------------------------------------------------------------------ #
    #  Tenpai / Winning state                                              #
    # ------------------------------------------------------------------ #

    def update_tenpai(self):
        """Recompute and cache tenpai/winning state after any hand change."""
        was_tenpai    = self.is_tenpai
        meld_count    = self._meld_tile_count()
        expected_size = 14 - meld_count

        if len(self.hand) == expected_size:
            # 14 effective tiles — check for immediate tsumo
            hand_sorted = sorted(self.hand, key=sort_key)
            if is_complete_hand(hand_sorted, meld_count):
                self.is_tenpai         = True
                self.tenpai_wait_tiles = set()
                self.state             = PlayerState.WINNING
                print(f"{self.name} has a winning hand! (tsumo possible)")
            else:
                self.is_tenpai         = False
                self.tenpai_wait_tiles = set()
                if not self.riichi_declared and not self.in_furiten:
                    self.state = PlayerState.NORMAL

        elif len(self.hand) == expected_size - 1:
            # 13 effective tiles — standard tenpai check
            self.is_tenpai = is_tenpai(self.hand, meld_count)
            if self.is_tenpai:
                self.tenpai_wait_tiles = get_wait_tiles(self.hand, meld_count)
                if self.riichi_declared:
                    self.state = PlayerState.RIICHI
                elif self.in_furiten:
                    self.state = PlayerState.FURITEN
                else:
                    self.state = PlayerState.TENPAI
            else:
                self.tenpai_wait_tiles = set()
                if not self.riichi_declared:
                    self.state = PlayerState.NORMAL
        else:
            self.is_tenpai         = False
            self.tenpai_wait_tiles = set()

        if was_tenpai != self.is_tenpai:
            if self.is_tenpai:
                print(f"{self.name} is TENPAI — waiting for: {self.get_wait_tile_display()}")
            else:
                print(f"{self.name} is no longer tenpai")

    def check_win(self, tile: Optional[Tile] = None, from_discard: bool = True) -> bool:
        """
        Return True if hand is currently winning (optionally with an added tile).
        Respects furiten when checking a discard win.
        """
        hand_copy  = self.hand.copy()
        meld_count = self._meld_tile_count()

        if tile:
            hand_copy.append(tile)

        if len(hand_copy) + meld_count != 14:
            return False

        if from_discard and tile:
            waits = self.tenpai_wait_tiles or get_wait_tiles(self.hand, meld_count)
            if self.in_furiten or any(w in self.discards for w in waits):
                print(f"{self.name} is in furiten — cannot win on discard")
                return False

        hand_copy.sort(key=sort_key)
        return is_complete_hand(hand_copy, meld_count)

    # ------------------------------------------------------------------ #
    #  Furiten                                                             #
    # ------------------------------------------------------------------ #

    def update_furiten(self, all_discards: List[List[Tile]]):
        """
        Recompute furiten status.

        Self-furiten:      one of your own waits is in your own discard pond.
        Temporary furiten: (non-riichi only) you passed on another player's
                           discard that would have completed your hand.

        Args:
            all_discards: List of discard piles for all OTHER players.
        """
        waits = get_wait_tiles(self.hand, self._meld_tile_count())
        if not waits:
            self.in_furiten   = False
            self.temp_furiten = False
            return

        # Self-furiten
        own_discard_set = set(self.discards)
        if any(t in own_discard_set for t in waits):
            self.in_furiten = True
            self.state      = PlayerState.FURITEN
            return

        # Temporary furiten (non-riichi)
        all_discard_set = {t for pile in all_discards for t in pile}
        if not self.riichi_declared and any(t in all_discard_set for t in waits):
            self.temp_furiten = True
            self.in_furiten   = True
            self.state        = PlayerState.FURITEN
            return

        # Clear furiten
        self.in_furiten   = False
        self.temp_furiten = False
        if self.state == PlayerState.FURITEN:
            self.state = PlayerState.TENPAI if self.is_tenpai else PlayerState.NORMAL

    # ------------------------------------------------------------------ #
    #  Hand inspection utilities                                           #
    # ------------------------------------------------------------------ #

    def get_hand_size(self) -> int:
        return len(self.hand)

    def get_total_tiles(self) -> int:
        return len(self.hand) + self._meld_tile_count()

    def find_tile_indices(self, target: Tile) -> List[int]:
        return [i for i, t in enumerate(self.hand) if t == target]

    def has_tile(self, tile: Tile) -> bool:
        return any(t == tile for t in self.hand)

    def count_tile(self, tile: Tile) -> int:
        return sum(1 for t in self.hand if t == tile)

    # ------------------------------------------------------------------ #
    #  Display                                                             #
    # ------------------------------------------------------------------ #

    def get_wait_tile_display(self) -> str:
        if not self.tenpai_wait_tiles:
            return "No waits"
        by_suit: dict = {}
        for tile in self.tenpai_wait_tiles:
            by_suit.setdefault(tile.suit.value, []).append(str(tile))
        return " | ".join(f"{suit}: {' '.join(ts)}" for suit, ts in by_suit.items())

    def show_hand(self, hide_last: bool = False) -> str:
        if not self.hand:
            return "Empty hand"
        if hide_last and self.state == PlayerState.RIICHI:
            return " ".join(str(t) for t in self.hand[:-1]) + " ?"
        return " ".join(str(t) for t in self.hand)

    def show_melds(self) -> str:
        if not self.melds:
            return "No open melds"
        return " | ".join(" ".join(str(t) for t in meld) for meld in self.melds)

    def show_concealed_melds(self) -> str:
        if not self.concealed_melds:
            return ""
        return " | ".join(" ".join(str(t) for t in meld) for meld in self.concealed_melds)

    def show_discards(self) -> str:
        if not self.discards:
            return "No discards"
        result = []
        for i, (tile, indicator) in enumerate(zip(self.discards, self.discard_indicators)):
            result.append(f"*{tile}*" if indicator == "R" else str(tile))
            if (i + 1) % 6 == 0 and i + 1 < len(self.discards):
                result.append("\n         ")
        return " ".join(result)

    def get_state_indicator(self) -> str:
        return {
            PlayerState.RIICHI:  "🎋",
            PlayerState.FURITEN: "⚠️",
            PlayerState.TENPAI:  "🎯",
            PlayerState.WINNING: "🏆",
        }.get(self.state, "")

    def __str__(self) -> str:
        return f"{self.name} ({self.wind.value}) {self.get_state_indicator()}"
    