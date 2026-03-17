from typing import List, Optional, Tuple, Set
from enum import Enum

from .tile import Tile, Suit, Wind, Dragon
from .wall import Wall
from utils.helpers import is_valid_sequence, is_valid_triplet, is_valid_quad


class PlayerState(Enum):
    """Current state of a player."""
    NORMAL = "normal"
    RIICHI = "riichi"
    FURITEN = "furiten"
    TENPAI = "tenpai"
    WINNING = "winning"  # Added: distinct from tenpai


class Player:
    """Represents a Mahjong player under Riichi rules."""

    def __init__(self, name: str, wind: Wind = Wind.EAST):
        self.name = name
        self.wind = wind
        self.hand: List[Tile] = []
        self.melds: List[List[Tile]] = []
        self.concealed_melds: List[List[Tile]] = []
        self.discards: List[Tile] = []
        self.discard_indicators: List[str] = []

        self.state: PlayerState = PlayerState.NORMAL
        self.riichi_declared: bool = False
        self.riichi_bet: int = 1000
        self.riichi_discard_index: Optional[int] = None
        self.in_furiten: bool = False
        self.temp_furiten: bool = False

        self.is_tenpai: bool = False
        self.tenpai_wait_tiles: Set[Tile] = set()

        self.points: int = 25000

    # ========== Drawing & Discarding ==========

    def draw_tile(self, tile: Tile):
        """Draw a tile from the wall."""
        self.hand.append(tile)
        self._sort_hand()
        print(f"{self.name} draws {tile}")
        self.update_tenpai()

    def discard_tile(self, index: int, is_riichi_discard: bool = False) -> Tile:
        """
        Discard a tile from hand by index.
        Pass is_riichi_discard=True to simultaneously declare Riichi.
        """
        if index < 0 or index >= len(self.hand):
            raise ValueError(f"Invalid tile index: {index}")

        tile = self.hand.pop(index)
        self.discards.append(tile)
        self.discard_indicators.append("R" if is_riichi_discard else " ")

        print(f"{self.name} discards {tile}{' (Riichi)' if is_riichi_discard else ''}")

        if is_riichi_discard:
            remaining = sorted(self.hand, key=lambda t: (t.suit.value, t.rank or 0))
            if not self._is_tenpai_13_tiles(remaining):
                print("Warning: riichi discard does not leave hand in tenpai")
            self.riichi_declared = True
            self.riichi_discard_index = len(self.discards) - 1
            self.points -= self.riichi_bet
            self.state = PlayerState.RIICHI
        else:
            self.update_tenpai()

        return tile

    # ========== Melding (Calls) ==========

    def _draw_kan_replacement(self, wall: Wall):
        """Draw replacement tile from dead wall after any kan."""
        if wall.get_dead_wall_size() == 0:
            print("Warning: dead wall empty — cannot draw replacement")
            return
        replacement = wall.draw_tile(from_dead_wall=True)
        self.draw_tile(replacement)
        print(f"{self.name} draws replacement after kan: {replacement}")

    def call_chi(self, tile: Tile, hand_indices: List[int]) -> bool:
        """
        Call chi (sequence) using a discarded tile.
        Cannot be called in riichi.
        """
        if self.riichi_declared:
            print(f"{self.name} cannot call Chi after declaring Riichi")
            return False

        if len(hand_indices) != 2:
            return False

        hand_tiles = [self.hand[i] for i in sorted(hand_indices)]
        potential_meld = hand_tiles + [tile]

        if is_valid_sequence(potential_meld):
            for i in sorted(hand_indices, reverse=True):
                self.hand.pop(i)
            self.melds.append(sorted(potential_meld, key=lambda t: (t.suit.value, t.rank or 0)))
            print(f"{self.name} calls CHI: {potential_meld}")
            self._sort_hand()
            self.update_tenpai()
            return True

        return False

    def call_pon(self, tile: Tile, hand_indices: List[int]) -> bool:
        """
        Call pon (triplet) using a discarded tile.
        Cannot be called in riichi.
        """
        if self.riichi_declared:
            print(f"{self.name} cannot call Pon after declaring Riichi")
            return False

        if len(hand_indices) != 2:
            return False

        hand_tiles = [self.hand[i] for i in hand_indices]
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
        """
        Call open kan (quad) using a discarded tile.
        Cannot be called in riichi.
        """
        if self.riichi_declared:
            print(f"{self.name} cannot call open Kan after declaring Riichi")
            return False

        if len(hand_indices) != 3:
            return False

        hand_tiles = [self.hand[i] for i in hand_indices]
        first_tile = hand_tiles[0]

        if not all(t == first_tile for t in hand_tiles):
            return False
        if tile != first_tile:
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
        Declare a concealed kan from own hand (ankan).
        Requires 4 identical tiles starting at tile_index (hand must be sorted).
        Can be done in riichi only if it does not change the wait tiles.
        """
        if tile_index + 4 > len(self.hand):
            return False

        tiles = [self.hand[tile_index + i] for i in range(4)]
        if not all(t == tiles[0] for t in tiles):
            return False

        # In riichi: only allow if waits are unchanged
        if self.riichi_declared:
            hand_after = self.hand[:tile_index] + self.hand[tile_index + 4:]
            new_waits = self._calculate_wait_tiles_for(hand_after)
            if new_waits != self.tenpai_wait_tiles:
                print(f"{self.name} cannot declare concealed kan: would change riichi waits")
                return False

        for i in range(3, -1, -1):
            self.hand.pop(tile_index + i)

        self.concealed_melds.append(tiles)
        print(f"{self.name} declares concealed KAN: {tiles}")
        self._draw_kan_replacement(wall)
        return True

    def declare_added_kan(self, meld_index: int, tile_index: int, wall: Wall) -> bool:
        """
        Add a tile from hand to an existing pon to form a shouminkan (added kan).
        """
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

    # ========== Riichi ==========

    def can_declare_riichi(self) -> Tuple[bool, str, Optional[List[Tile]]]:
        """
        Check if riichi can be declared.
        Returns (can_declare, reason, safe_discard_tiles_or_None).
        """
        if self.riichi_declared:
            return False, "Already in riichi", None
        if self.melds:
            return False, "Cannot riichi with open melds", None
        if self.points < 1000:
            return False, f"Need 1000 points, have {self.points}", None

        total_meld_tiles = sum(len(m) for m in self.concealed_melds)
        expected_hand_size = 14 - total_meld_tiles
        if len(self.hand) != expected_hand_size:
            return False, f"Hand size is {len(self.hand)}, expected {expected_hand_size}", None

        safe_discards = []
        seen: Set[str] = set()
        for i, tile in enumerate(self.hand):
            key = str(tile)
            if key in seen:
                continue
            seen.add(key)
            remaining = self.hand[:i] + self.hand[i + 1:]
            if self._is_tenpai_13_tiles(remaining):
                safe_discards.append(tile)

        if safe_discards:
            return True, "Can declare Riichi", safe_discards
        return False, "No discard leads to tenpai", None

    def declare_riichi(self) -> Tuple[bool, str, Optional[List[Tile]]]:
        """
        Check riichi eligibility and return results.
        Actual state change happens in discard_tile(is_riichi_discard=True).
        """
        can, reason, safe = self.can_declare_riichi()
        if can:
            print(f"{self.name} is eligible to declare Riichi")
        else:
            print(f"{self.name} cannot declare Riichi: {reason}")
        return can, reason, safe

    # ========== Tenpai & Winning ==========

    def update_tenpai(self):
        """Recompute tenpai/winning state after any hand change."""
        was_tenpai = self.is_tenpai

        total_meld_tiles = (sum(len(m) for m in self.melds) +
                            sum(len(m) for m in self.concealed_melds))
        expected_hand_size = 14 - total_meld_tiles

        if len(self.hand) == expected_hand_size:
            # 14 tiles in effective hand — check for immediate win (tsumo)
            hand_copy = sorted(self.hand, key=lambda t: (t.suit.value, t.rank or 0))
            if self._is_complete_hand(hand_copy, total_meld_tiles):
                self.is_tenpai = True   # winning IS a form of tenpai for the RL agent
                self.tenpai_wait_tiles = set()
                self.state = PlayerState.WINNING
                print(f"{self.name} has a winning hand! (tsumo possible)")
            else:
                self.is_tenpai = False
                self.tenpai_wait_tiles = set()
                if not self.riichi_declared and not self.in_furiten:
                    self.state = PlayerState.NORMAL

        elif len(self.hand) == expected_hand_size - 1:
            # 13 tiles — standard tenpai check
            self.is_tenpai = self._is_tenpai_13_tiles(self.hand)
            if self.is_tenpai:
                self.tenpai_wait_tiles = self._calculate_wait_tiles()
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
            self.is_tenpai = False
            self.tenpai_wait_tiles = set()

        if was_tenpai != self.is_tenpai:
            if self.is_tenpai:
                print(f"{self.name} is TENPAI — waiting for: {self.get_wait_tile_display()}")
            else:
                print(f"{self.name} is no longer tenpai")

    def _is_tenpai_13_tiles(self, tiles_13: List[Tile]) -> bool:
        """Return True if the given 13-tile hand is one tile away from winning."""
        total_meld_tiles = (sum(len(m) for m in self.melds) +
                            sum(len(m) for m in self.concealed_melds))
        hand_tiles_needed = 14 - total_meld_tiles

        if len(tiles_13) != hand_tiles_needed - 1:
            return False

        for test_tile in self._get_all_possible_tiles():
            test_hand = sorted(tiles_13 + [test_tile], key=lambda t: (t.suit.value, t.rank or 0))
            if self._is_complete_hand(test_hand, total_meld_tiles):
                return True
        return False

    def check_win(self, tile: Optional[Tile] = None, from_discard: bool = True) -> bool:
        """
        Check if hand is a winning hand.
        If tile is provided, temporarily add it before checking.
        """
        hand_copy = self.hand.copy()
        if tile:
            hand_copy.append(tile)

        total_meld_tiles = (sum(len(m) for m in self.melds) +
                            sum(len(m) for m in self.concealed_melds))

        if len(hand_copy) + total_meld_tiles != 14:
            return False

        # Furiten: cannot win on a discard if any wait tile is in own discards
        if from_discard and tile:
            wait_tiles = self.tenpai_wait_tiles or self._calculate_wait_tiles_for(self.hand)
            if self.in_furiten or any(w in self.discards for w in wait_tiles):
                print(f"{self.name} is in furiten — cannot win on discard")
                return False

        hand_copy.sort(key=lambda t: (t.suit.value, t.rank or 0))
        return self._is_complete_hand(hand_copy, total_meld_tiles)

    # ========== Furiten ==========

    def update_furiten(self, all_discards: List[List[Tile]]):
        """
        Update furiten status.
        Furiten applies when any of your wait tiles appears in your own discards,
        OR (outside riichi) in any other player's discards that you passed on.
        """
        wait_tiles = self._calculate_wait_tiles()
        if not wait_tiles:
            self.in_furiten = False
            return

        # Self-furiten: one of your waits is in your own discard pond
        own_discard_set = set(self.discards)
        if any(t in own_discard_set for t in wait_tiles):
            self.in_furiten = True
            self.state = PlayerState.FURITEN
            return

        # Temporary furiten (non-riichi): passed on another player's winning discard
        # all_discards is a flat list of all other players' most recent discards
        all_discard_set = set(t for pile in all_discards for t in pile)
        if not self.riichi_declared and any(t in all_discard_set for t in wait_tiles):
            self.temp_furiten = True
            self.in_furiten = True
            self.state = PlayerState.FURITEN
            return

        self.in_furiten = False
        self.temp_furiten = False
        if self.state == PlayerState.FURITEN:
            self.state = PlayerState.TENPAI if self.is_tenpai else PlayerState.NORMAL

    # ========== Hand Inspection ==========

    def _get_all_possible_tiles(self) -> List[Tile]:
        """Return one instance of every unique tile type (34 total)."""
        tiles = []
        for suit in (Suit.BAMBOO, Suit.CHARACTERS, Suit.DOTS):
            for rank in range(1, 10):
                tiles.append(Tile(suit, rank=rank))
        for wind in Wind:
            tiles.append(Tile(Suit.WINDS, wind=wind))
        for dragon in Dragon:
            tiles.append(Tile(Suit.DRAGONS, dragon=dragon))
        return tiles

    def _calculate_wait_tiles(self) -> Set[Tile]:
        """Return the set of tiles that would complete the current hand."""
        return self._calculate_wait_tiles_for(self.hand)

    def _calculate_wait_tiles_for(self, hand: List[Tile]) -> Set[Tile]:
        """Return the set of tiles that would complete a given hand."""
        total_meld_tiles = (sum(len(m) for m in self.melds) +
                            sum(len(m) for m in self.concealed_melds))
        wait_tiles: Set[Tile] = set()
        for test_tile in self._get_all_possible_tiles():
            test_hand = sorted(hand + [test_tile], key=lambda t: (t.suit.value, t.rank or 0))
            if self._is_complete_hand(test_hand, total_meld_tiles):
                wait_tiles.add(test_tile)
        return wait_tiles

    def _sort_hand(self):
        """Sort hand: Bamboo → Characters → Dots → Winds → Dragons, then by rank."""
        suit_order = {
            "bamboo": 0,
            "characters": 1,
            "dots": 2,
            "winds": 3,
            "dragons": 4,
        }
        self.hand.sort(key=lambda t: (suit_order[t.suit.value], t.rank or 0))

    def _is_complete_hand(self, tiles: List[Tile], existing_meld_tiles: int = 0) -> bool:
        """
        Check whether tiles + existing melds form a standard winning hand (4 melds + 1 pair).
        Tiles must be pre-sorted.
        """
        if len(tiles) + existing_meld_tiles != 14:
            return False
        if len(tiles) == 0:
            return True

        # Try every possible pair position
        for i in range(len(tiles) - 1):
            if tiles[i] == tiles[i + 1]:
                remaining = tiles[:i] + tiles[i + 2:]
                if self._check_melds_only(remaining, existing_meld_tiles + 2):
                    return True
        return False

    def _check_melds_only(self, tiles: List[Tile], counted_so_far: int) -> bool:
        """Recursively verify that remaining tiles form complete melds (no pair needed)."""
        n = len(tiles)
        if n == 0:
            return counted_so_far == 14
        if n < 3:
            return False

        first = tiles[0]

        # Triplet (pon)
        if tiles[1] == first and tiles[2] == first:
            if self._check_melds_only(tiles[3:], counted_so_far + 3):
                return True

        # Quad (kan) — treated as 4-of-a-kind
        if n >= 4 and tiles[1] == first and tiles[2] == first and tiles[3] == first:
            if self._check_melds_only(tiles[4:], counted_so_far + 4):
                return True

        # Sequence (chi) — suited tiles only
        if first.suit.value in ("bamboo", "characters", "dots") and first.rank is not None:
            r = first.rank
            found_indices = [0]
            needed = [r + 1, r + 2]
            pos = 1
            while pos < n and len(found_indices) < 3:
                t = tiles[pos]
                if t.suit == first.suit and t.rank == needed[len(found_indices) - 1]:
                    found_indices.append(pos)
                pos += 1

            if len(found_indices) == 3:
                remaining = [tiles[j] for j in range(n) if j not in found_indices]
                if self._check_melds_only(remaining, counted_so_far + 3):
                    return True

        return False

    # ========== Hand Utilities ==========

    def get_hand_size(self) -> int:
        return len(self.hand)

    def get_total_tiles(self) -> int:
        return len(self.hand) + sum(len(m) for m in self.melds) + sum(len(m) for m in self.concealed_melds)

    def find_tile_indices(self, target_tile: Tile) -> List[int]:
        return [i for i, t in enumerate(self.hand) if t == target_tile]

    def has_tile(self, tile: Tile) -> bool:
        return any(t == tile for t in self.hand)

    def count_tile(self, tile: Tile) -> int:
        return sum(1 for t in self.hand if t == tile)

    # ========== Display ==========

    def get_wait_tile_display(self) -> str:
        if not self.tenpai_wait_tiles:
            return "No waits"
        waits_by_suit: dict = {}
        for tile in self.tenpai_wait_tiles:
            s = tile.suit.value
            waits_by_suit.setdefault(s, []).append(str(tile))
        return " | ".join(f"{suit}: {' '.join(ts)}" for suit, ts in waits_by_suit.items())

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
        indicators = {
            PlayerState.RIICHI: "🎋",
            PlayerState.FURITEN: "⚠️",
            PlayerState.TENPAI: "🎯",
            PlayerState.WINNING: "🏆",
        }
        return indicators.get(self.state, "")

    def __str__(self):
        return f"{self.name} ({self.wind.value}) {self.get_state_indicator()}"