"""
test_player.py — Test suite for the Riichi Mahjong Player class.

Run from the project root with:
    python -m pytest core/test_player.py -v
Or:
    python -m core.test_player
"""

import unittest
from unittest.mock import MagicMock

from .tile import Tile, Suit, Wind, Dragon
from .wall import Wall
from .player import Player, PlayerState
from evaluation.hand_checker import is_complete_hand, is_tenpai, get_wait_tiles, get_all_tiles, sort_key
from evaluation.melds import is_valid_sequence, is_valid_triplet, is_valid_quad

# ---------------------------------------------------------------------------
# Shorthand helpers
# ---------------------------------------------------------------------------

B = Suit.BAMBOO
C = Suit.CHARACTERS
D = Suit.DOTS


def t(suit: Suit, rank: int) -> Tile:
    return Tile(suit, rank=rank)


def make_wall_mock(replacement: Tile = None) -> MagicMock:
    wall = MagicMock(spec=Wall)
    wall.get_dead_wall_size.return_value = 4
    wall.draw_tile.return_value = replacement or t(D, 1)
    return wall


# ---------------------------------------------------------------------------
# Standard 13-tile tenpai hand used across multiple tests:
#   Pair: 1D 1D
#   Seq:  2D 3D 4D
#   Seq:  5D 6D 7D
#   Seq:  2B 3B 4B
#   Partial: 3C 4C  → waits on 2C or 5C
# ---------------------------------------------------------------------------

TENPAI_13 = [
    t(D, 1), t(D, 1),
    t(D, 2), t(D, 3), t(D, 4),
    t(D, 5), t(D, 6), t(D, 7),
    t(B, 2), t(B, 3), t(B, 4),
    t(C, 3), t(C, 4),
]

WINNING_14 = TENPAI_13 + [t(C, 5)]


def tenpai_player() -> Player:
    """Return a Player with TENPAI_13 already in hand."""
    p = Player("TestPlayer", Wind.EAST)
    for tile in TENPAI_13:
        p.hand.append(tile)
    p._sort_hand()
    p.update_tenpai()
    return p


def winning_player() -> Player:
    """Return a Player with WINNING_14 in hand."""
    p = Player("TestPlayer", Wind.EAST)
    for tile in WINNING_14:
        p.hand.append(tile)
    p._sort_hand()
    p.update_tenpai()
    return p


# ===========================================================================
# Tests
# ===========================================================================

class TestDrawAndDiscard(unittest.TestCase):

    def test_draw_adds_tile_to_hand(self):
        p = Player("Alice", Wind.EAST)
        tile = t(D, 5)
        p.draw_tile(tile)
        self.assertIn(tile, p.hand)

    def test_draw_updates_tenpai(self):
        p = Player("Alice", Wind.EAST)
        for tile in TENPAI_13:
            p.hand.append(tile)
        p._sort_hand()
        p.draw_tile(t(C, 5))
        self.assertEqual(p.state, PlayerState.WINNING)

    def test_discard_removes_tile(self):
        p = tenpai_player()
        p.draw_tile(t(C, 9))
        size_before = len(p.hand)
        discarded = p.discard_tile(0)
        self.assertEqual(len(p.hand), size_before - 1)
        self.assertIn(discarded, p.discards)

    def test_discard_records_indicator(self):
        p = tenpai_player()
        p.hand.append(t(C, 9))
        p.discard_tile(0)
        self.assertEqual(p.discard_indicators[-1], " ")

    def test_discard_invalid_index_raises(self):
        p = Player("Alice", Wind.EAST)
        p.hand.append(t(D, 1))
        with self.assertRaises(ValueError):
            p.discard_tile(99)


class TestTenpaiDetection(unittest.TestCase):

    def test_tenpai_detected_on_13_tiles(self):
        p = tenpai_player()
        self.assertTrue(p.is_tenpai)
        self.assertEqual(p.state, PlayerState.TENPAI)

    def test_wait_tiles_include_c2_or_c5(self):
        p = tenpai_player()
        waits = p.tenpai_wait_tiles
        self.assertTrue(
            t(C, 2) in waits or t(C, 5) in waits,
            f"Expected C2 or C5 in waits, got: {waits}"
        )

    def test_winning_state_on_14_tile_complete_hand(self):
        p = winning_player()
        self.assertEqual(p.state, PlayerState.WINNING)
        self.assertTrue(p.is_tenpai)

    def test_non_tenpai_hand(self):
        p = Player("Bob", Wind.EAST)
        for i in [1, 1, 3, 3, 5, 5, 7, 7, 9, 9, 2, 4, 6]:
            p.hand.append(t(D, i))
        p._sort_hand()
        p.update_tenpai()
        self.assertFalse(p.is_tenpai)

    def test_no_tenpai_with_wrong_count(self):
        p = Player("Bob", Wind.EAST)
        p.hand = [t(D, 1)]
        p.update_tenpai()
        self.assertFalse(p.is_tenpai)


class TestCheckWin(unittest.TestCase):

    def test_tsumo_win(self):
        p = winning_player()
        self.assertTrue(p.check_win(from_discard=False))

    def test_ron_win(self):
        p = tenpai_player()
        self.assertTrue(p.check_win(tile=t(C, 5), from_discard=True))

    def test_ron_wrong_tile(self):
        p = tenpai_player()
        self.assertFalse(p.check_win(tile=t(C, 9), from_discard=True))

    def test_furiten_blocks_ron(self):
        p = tenpai_player()
        p.discards.append(t(C, 5))
        p.in_furiten = True
        self.assertFalse(p.check_win(tile=t(C, 5), from_discard=True))

    def test_wrong_tile_count_fails(self):
        p = Player("Carol", Wind.EAST)
        p.hand = [t(D, 1)]
        self.assertFalse(p.check_win(from_discard=False))


class TestRiichi(unittest.TestCase):

    def _riichi_ready_player(self) -> Player:
        p = Player("Dave", Wind.WEST)
        p.points = 25000
        for tile in TENPAI_13 + [t(C, 9)]:
            p.hand.append(tile)
        p._sort_hand()
        return p

    def test_can_declare_riichi(self):
        p = self._riichi_ready_player()
        can, reason, safe = p.can_declare_riichi()
        self.assertTrue(can, reason)
        self.assertIsNotNone(safe)
        self.assertGreater(len(safe), 0)

    def test_safe_discards_contain_junk(self):
        p = self._riichi_ready_player()
        _, _, safe = p.can_declare_riichi()
        self.assertIn(t(C, 9), safe)

    def test_cannot_riichi_with_open_melds(self):
        p = self._riichi_ready_player()
        p.melds.append([t(D, 1), t(D, 2), t(D, 3)])
        can, _, _ = p.can_declare_riichi()
        self.assertFalse(can)

    def test_cannot_riichi_insufficient_points(self):
        p = self._riichi_ready_player()
        p.points = 500
        can, _, _ = p.can_declare_riichi()
        self.assertFalse(can)

    def test_cannot_riichi_twice(self):
        p = self._riichi_ready_player()
        p.riichi_declared = True
        can, reason, _ = p.can_declare_riichi()
        self.assertFalse(can)
        self.assertIn("riichi", reason.lower())

    def test_riichi_discard_deducts_points_and_sets_state(self):
        p = self._riichi_ready_player()
        c9_idx = next(i for i, tile in enumerate(p.hand) if tile == t(C, 9))
        initial_points = p.points
        p.discard_tile(c9_idx, is_riichi_discard=True)
        self.assertTrue(p.riichi_declared)
        self.assertEqual(p.state, PlayerState.RIICHI)
        self.assertEqual(p.points, initial_points - 1000)

    def test_riichi_discard_indicator(self):
        p = self._riichi_ready_player()
        c9_idx = next(i for i, tile in enumerate(p.hand) if tile == t(C, 9))
        p.discard_tile(c9_idx, is_riichi_discard=True)
        self.assertEqual(p.discard_indicators[-1], "R")


class TestMelding(unittest.TestCase):

    def test_call_chi_valid(self):
        p = Player("Eve", Wind.NORTH)
        p.hand = [t(D, 2), t(D, 3), t(B, 1), t(B, 2)]
        self.assertTrue(p.call_chi(t(D, 4), [0, 1]))
        self.assertEqual(len(p.melds), 1)
        self.assertEqual(len(p.hand), 2)

    def test_call_chi_invalid_sequence(self):
        p = Player("Eve", Wind.NORTH)
        p.hand = [t(D, 2), t(D, 9)]
        self.assertFalse(p.call_chi(t(D, 4), [0, 1]))

    def test_call_chi_blocked_in_riichi(self):
        p = Player("Eve", Wind.NORTH)
        p.riichi_declared = True
        p.hand = [t(D, 2), t(D, 3)]
        self.assertFalse(p.call_chi(t(D, 4), [0, 1]))

    def test_call_pon_valid(self):
        p = Player("Eve", Wind.NORTH)
        p.hand = [t(D, 5), t(D, 5), t(B, 1)]
        self.assertTrue(p.call_pon(t(D, 5), [0, 1]))
        self.assertEqual(len(p.melds), 1)
        self.assertEqual(len(p.hand), 1)

    def test_call_pon_blocked_in_riichi(self):
        p = Player("Eve", Wind.NORTH)
        p.riichi_declared = True
        p.hand = [t(D, 5), t(D, 5)]
        self.assertFalse(p.call_pon(t(D, 5), [0, 1]))

    def test_call_kan_valid(self):
        wall = make_wall_mock()
        p = Player("Eve", Wind.NORTH)
        p.hand = [t(D, 5), t(D, 5), t(D, 5), t(B, 1)]
        self.assertTrue(p.call_kan(t(D, 5), [0, 1, 2], wall))
        self.assertEqual(len(p.melds[0]), 4)

    def test_call_kan_wrong_tile_fails(self):
        wall = make_wall_mock()
        p = Player("Eve", Wind.NORTH)
        p.hand = [t(D, 5), t(D, 5), t(D, 5)]
        self.assertFalse(p.call_kan(t(D, 3), [0, 1, 2], wall))

    def test_declare_added_kan(self):
        wall = make_wall_mock(replacement=t(B, 9))
        p = Player("Eve", Wind.NORTH)
        p.melds = [[t(D, 7), t(D, 7), t(D, 7)]]
        p.hand = [t(D, 7), t(B, 1)]
        self.assertTrue(p.declare_added_kan(0, 0, wall))
        self.assertEqual(len(p.melds[0]), 4)

    def test_declare_added_kan_wrong_index(self):
        wall = make_wall_mock()
        p = Player("Eve", Wind.NORTH)
        p.melds = [[t(D, 7), t(D, 7), t(D, 7)]]
        p.hand = [t(D, 7)]
        self.assertFalse(p.declare_added_kan(5, 0, wall))


class TestFuriten(unittest.TestCase):

    def test_self_furiten_when_wait_in_own_discards(self):
        p = tenpai_player()
        p.discards.append(t(C, 5))
        p.update_furiten([])
        self.assertTrue(p.in_furiten)
        self.assertEqual(p.state, PlayerState.FURITEN)

    def test_no_furiten_without_matching_discard(self):
        p = tenpai_player()
        p.discards.append(t(B, 9))
        p.update_furiten([])
        self.assertFalse(p.in_furiten)

    def test_furiten_clears_when_discard_irrelevant(self):
        p = tenpai_player()
        p.in_furiten = True
        p.state = PlayerState.FURITEN
        p.update_furiten([])
        self.assertFalse(p.in_furiten)


class TestDisplayMethods(unittest.TestCase):

    def test_show_hand_non_empty(self):
        p = Player("Greta", Wind.EAST)
        p.hand = [t(D, 1), t(D, 2)]
        self.assertIn("1", p.show_hand())

    def test_show_hand_empty(self):
        p = Player("Greta", Wind.EAST)
        self.assertEqual(p.show_hand(), "Empty hand")

    def test_show_melds_empty(self):
        p = Player("Greta", Wind.EAST)
        self.assertEqual(p.show_melds(), "No open melds")

    def test_show_discards_empty(self):
        p = Player("Greta", Wind.EAST)
        self.assertEqual(p.show_discards(), "No discards")

    def test_state_indicator_riichi(self):
        p = Player("Greta", Wind.EAST)
        p.state = PlayerState.RIICHI
        self.assertIn("🎋", p.get_state_indicator())

    def test_state_indicator_winning(self):
        p = Player("Greta", Wind.EAST)
        p.state = PlayerState.WINNING
        self.assertIn("🏆", p.get_state_indicator())

    def test_str_contains_name_and_wind(self):
        p = Player("Greta", Wind.EAST)
        s = str(p)
        self.assertIn("Greta", s)
        self.assertIn("east", s)

    def test_riichi_discard_highlighted_in_show_discards(self):
        p = tenpai_player()
        p.hand.append(t(C, 9))
        idx = next(i for i, tile in enumerate(p.hand) if tile == t(C, 9))
        p.discard_tile(idx, is_riichi_discard=True)
        self.assertIn("*", p.show_discards())


class TestHandUtilities(unittest.TestCase):

    def test_find_tile_indices(self):
        p = Player("Han", Wind.EAST)
        p.hand = [t(D, 1), t(D, 3), t(D, 1)]
        self.assertEqual(p.find_tile_indices(t(D, 1)), [0, 2])

    def test_has_tile_true(self):
        p = Player("Han", Wind.EAST)
        p.hand = [t(D, 5)]
        self.assertTrue(p.has_tile(t(D, 5)))

    def test_has_tile_false(self):
        p = Player("Han", Wind.EAST)
        p.hand = [t(D, 5)]
        self.assertFalse(p.has_tile(t(D, 9)))

    def test_count_tile(self):
        p = Player("Han", Wind.EAST)
        p.hand = [t(D, 5), t(D, 5), t(D, 3)]
        self.assertEqual(p.count_tile(t(D, 5)), 2)

    def test_get_total_tiles(self):
        p = Player("Han", Wind.EAST)
        p.hand = [t(D, 1), t(D, 2)]
        p.melds = [[t(B, 1), t(B, 2), t(B, 3)]]
        p.concealed_melds = [[t(C, 7), t(C, 7), t(C, 7), t(C, 7)]]
        self.assertEqual(p.get_total_tiles(), 9)

    def test_hand_size(self):
        p = tenpai_player()
        self.assertEqual(p.get_hand_size(), 13)


class TestWall(unittest.TestCase):

    def test_wall_builds_136_tiles(self):
        wall = Wall()
        self.assertEqual(wall.get_wall_size(), 136)

    def test_set_dead_wall(self):
        wall = Wall()
        wall.set_dead_wall(14)
        self.assertEqual(wall.get_dead_wall_size(), 14)
        self.assertEqual(wall.get_wall_size(), 122)

    def test_draw_tile_reduces_wall(self):
        wall = Wall()
        wall.set_dead_wall(14)
        size_before = wall.get_wall_size()
        wall.draw_tile()
        self.assertEqual(wall.get_wall_size(), size_before - 1)

    def test_draw_from_dead_wall(self):
        wall = Wall()
        wall.set_dead_wall(14)
        size_before = wall.get_dead_wall_size()
        tile = wall.draw_tile(from_dead_wall=True)
        self.assertIsInstance(tile, Tile)
        self.assertEqual(wall.get_dead_wall_size(), size_before - 1)

    def test_draw_empty_wall_raises(self):
        wall = Wall()
        wall.tiles = []
        with self.assertRaises(RuntimeError):
            wall.draw_tile()

    def test_deal_starting_hands(self):
        wall = Wall()
        wall.set_dead_wall(14)
        hands = wall.deal_starting_hands(num_players=4)
        self.assertEqual(len(hands), 4)
        for hand in hands:
            self.assertEqual(len(hand), 13)
        self.assertEqual(wall.get_wall_size(), 122 - 52)

    def test_is_empty(self):
        wall = Wall()
        wall.tiles = []
        self.assertTrue(wall.is_empty())

    def test_peek_next_tile(self):
        wall = Wall()
        first = wall.peek_next_tile()
        self.assertIsInstance(first, Tile)
        self.assertEqual(wall.get_wall_size(), 136)

    def test_wall_str(self):
        wall = Wall()
        wall.set_dead_wall(14)
        s = str(wall)
        self.assertIn("122", s)
        self.assertIn("14", s)


class TestTile(unittest.TestCase):

    def test_eq_same_tile(self):
        self.assertEqual(t(D, 5), t(D, 5))

    def test_eq_different_rank(self):
        self.assertNotEqual(t(D, 5), t(D, 6))

    def test_eq_different_suit(self):
        self.assertNotEqual(t(D, 5), t(B, 5))

    def test_hash_consistent_with_eq(self):
        a, b = t(D, 5), t(D, 5)
        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))

    def test_tile_usable_in_set(self):
        tile_set = {t(D, 5), t(D, 5), t(B, 3)}
        self.assertEqual(len(tile_set), 2)

    def test_repr_suited(self):
        self.assertEqual(repr(t(D, 7)), "7D")
        self.assertEqual(repr(t(B, 3)), "3B")

    def test_repr_wind(self):
        tile = Tile(Suit.WINDS, wind=Wind.EAST)
        self.assertTrue(repr(tile).startswith("E"))

    def test_repr_dragon(self):
        tile = Tile(Suit.DRAGONS, dragon=Dragon.CHUN)
        self.assertTrue(repr(tile).startswith("C"))


# ---------------------------------------------------------------------------
# End-to-end
# ---------------------------------------------------------------------------

class TestEndToEnd(unittest.TestCase):

    def test_full_game_flow_tenpai_then_tsumo(self):
        p = tenpai_player()
        self.assertTrue(p.is_tenpai)
        self.assertTrue(t(C, 5) in p.tenpai_wait_tiles or t(C, 2) in p.tenpai_wait_tiles)
        p.draw_tile(t(C, 5))
        self.assertEqual(p.state, PlayerState.WINNING)
        self.assertTrue(p.check_win(from_discard=False))

    def test_full_game_flow_riichi_then_ron(self):
        p = Player("南ちゃん", Wind.SOUTH)
        for tile in TENPAI_13 + [t(C, 9)]:
            p.hand.append(tile)
        p._sort_hand()

        can, _, safe = p.can_declare_riichi()
        self.assertTrue(can)
        self.assertIn(t(C, 9), safe)

        c9_idx = next(i for i, tile in enumerate(p.hand) if tile == t(C, 9))
        p.discard_tile(c9_idx, is_riichi_discard=True)

        self.assertTrue(p.riichi_declared)
        self.assertEqual(p.state, PlayerState.RIICHI)
        self.assertEqual(p.points, 24000)
        self.assertTrue(p.check_win(tile=t(C, 5), from_discard=True))

    def test_wall_deal_and_draw(self):
        wall = Wall()
        wall.set_dead_wall(14)
        hands = wall.deal_starting_hands(4)

        players = [Player(f"P{i}", list(Wind)[i]) for i in range(4)]
        for player, hand in zip(players, hands):
            player.hand = hand
            player._sort_hand()
            player.update_tenpai()

        drawn = wall.draw_tile()
        self.assertIsInstance(drawn, Tile)
        players[0].draw_tile(drawn)
        self.assertEqual(players[0].get_hand_size(), 14)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestMelds(unittest.TestCase):

    def test_valid_sequence(self):
        self.assertTrue(is_valid_sequence([t(D, 3), t(D, 4), t(D, 5)]))

    def test_invalid_sequence_wrong_suit(self):
        self.assertFalse(is_valid_sequence([t(D, 3), t(B, 4), t(D, 5)]))

    def test_invalid_sequence_not_consecutive(self):
        self.assertFalse(is_valid_sequence([t(D, 3), t(D, 5), t(D, 7)]))

    def test_sequence_honours_rejected(self):
        east  = Tile(Suit.WINDS, wind=Wind.EAST)
        south = Tile(Suit.WINDS, wind=Wind.SOUTH)
        west  = Tile(Suit.WINDS, wind=Wind.WEST)
        self.assertFalse(is_valid_sequence([east, south, west]))

    def test_valid_triplet(self):
        self.assertTrue(is_valid_triplet([t(D, 5), t(D, 5), t(D, 5)]))

    def test_invalid_triplet_mixed(self):
        self.assertFalse(is_valid_triplet([t(D, 5), t(D, 5), t(B, 5)]))

    def test_valid_quad(self):
        self.assertTrue(is_valid_quad([t(C, 9), t(C, 9), t(C, 9), t(C, 9)]))

    def test_invalid_quad_wrong_count(self):
        self.assertFalse(is_valid_quad([t(C, 9), t(C, 9), t(C, 9)]))


class TestHandChecker(unittest.TestCase):

    def test_complete_hand_4_sequences_1_pair(self):
        tiles = sorted([
            t(D, 1), t(D, 1),
            t(D, 2), t(D, 3), t(D, 4),
            t(D, 5), t(D, 6), t(D, 7),
            t(B, 2), t(B, 3), t(B, 4),
            t(C, 3), t(C, 4), t(C, 5),
        ], key=sort_key)
        self.assertTrue(is_complete_hand(tiles, 0))

    def test_complete_hand_with_triplet(self):
        tiles = sorted([
            t(D, 1), t(D, 1),
            t(D, 5), t(D, 5), t(D, 5),
            t(D, 2), t(D, 3), t(D, 4),
            t(B, 2), t(B, 3), t(B, 4),
            t(C, 3), t(C, 4), t(C, 5),
        ], key=sort_key)
        self.assertTrue(is_complete_hand(tiles, 0))

    def test_incomplete_hand_13_tiles(self):
        tiles = sorted(TENPAI_13, key=sort_key)
        self.assertFalse(is_complete_hand(tiles, 0))

    def test_complete_hand_with_open_meld(self):
        hand_tiles = sorted([
            t(D, 1), t(D, 1),
            t(D, 2), t(D, 3), t(D, 4),
            t(D, 5), t(D, 6), t(D, 7),
            t(C, 3), t(C, 4), t(C, 5),
        ], key=sort_key)
        self.assertTrue(is_complete_hand(hand_tiles, existing_meld_tiles=3))

    def test_tenpai_standard(self):
        self.assertTrue(is_tenpai(TENPAI_13, 0))

    def test_not_tenpai_random_tiles(self):
        random_tiles = [t(D, i) for i in [1, 1, 3, 3, 5, 5, 7, 7, 9, 9, 2, 4, 6]]
        self.assertFalse(is_tenpai(random_tiles, 0))

    def test_tenpai_with_open_meld(self):
        hand = [
            t(D, 1), t(D, 1),
            t(D, 2), t(D, 3), t(D, 4),
            t(D, 5), t(D, 6), t(D, 7),
            t(C, 3), t(C, 4),
        ]
        self.assertTrue(is_tenpai(hand, existing_meld_tiles=3))

    def test_wait_tiles_two_sided(self):
        waits = get_wait_tiles(TENPAI_13, 0)
        self.assertIn(t(C, 2), waits)
        self.assertIn(t(C, 5), waits)

    def test_no_waits_non_tenpai(self):
        random_tiles = [t(D, i) for i in [1, 1, 3, 3, 5, 5, 7, 7, 9, 9, 2, 4, 6]]
        self.assertEqual(len(get_wait_tiles(random_tiles, 0)), 0)

    def test_get_all_tiles_count(self):
        self.assertEqual(len(get_all_tiles()), 34)

    def test_get_all_tiles_no_duplicates(self):
        self.assertEqual(len(set(get_all_tiles())), 34)
        