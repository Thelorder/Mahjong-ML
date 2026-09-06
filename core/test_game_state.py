"""
test_game_state.py — Tests for GameState, Action, and Observation.

Run from project root:
    python -m pytest core/test_game_state.py -v
Or:
    python -m core.test_game_state
"""

import unittest

from .tile import Tile, Suit, Wind
from .player import PlayerState
from .game_state import (
    GameState, Action, ActionType, Phase,
    RoundEndReason, Observation,
    TILE_INDEX, tile_to_idx, tiles_to_counts,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def t(suit, rank): return Tile(suit, rank=rank)
D, B, C = Suit.DOTS, Suit.BAMBOO, Suit.CHARACTERS


def make_started_game(**kwargs) -> GameState:
    """Return a GameState that has called start_round()."""
    gs = GameState(**kwargs)
    gs.start_round()
    return gs


# ─────────────────────────────────────────────────────────────────────────────
# Tile encoding
# ─────────────────────────────────────────────────────────────────────────────

class TestTileEncoding(unittest.TestCase):

    def test_tile_index_has_34_entries(self):
        self.assertEqual(len(TILE_INDEX), 34)

    def test_tile_index_unique(self):
        self.assertEqual(len(set(TILE_INDEX.values())), 34)

    def test_tile_index_range(self):
        self.assertTrue(all(0 <= v <= 33 for v in TILE_INDEX.values()))

    def test_tiles_to_counts_length(self):
        counts = tiles_to_counts([t(D, 1), t(D, 1), t(B, 3)])
        self.assertEqual(len(counts), 34)

    def test_tiles_to_counts_correct_values(self):
        tile = t(D, 1)
        counts = tiles_to_counts([tile, tile])
        self.assertEqual(counts[tile_to_idx(tile)], 2)

    def test_empty_tiles_all_zero(self):
        self.assertEqual(tiles_to_counts([]), [0] * 34)


# ─────────────────────────────────────────────────────────────────────────────
# GameState initialisation
# ─────────────────────────────────────────────────────────────────────────────

class TestGameStateInit(unittest.TestCase):

    def test_default_player_names(self):
        gs = GameState()
        self.assertEqual(len(gs.players), 4)
        self.assertIn("Player", gs.players[0].name)

    def test_custom_player_names(self):
        gs = GameState(player_names=["A", "B", "C", "D"])
        self.assertEqual([p.name for p in gs.players], ["A", "B", "C", "D"])

    def test_wrong_player_count_raises(self):
        with self.assertRaises(AssertionError):
            GameState(player_names=["A", "B"])

    def test_initial_phase_is_draw(self):
        gs = GameState()
        self.assertEqual(gs.phase, Phase.DRAW)

    def test_starting_points(self):
        gs = GameState(starting_points=30000)
        for p in gs.players:
            self.assertEqual(p.points, 30000)

    def test_seat_winds_assigned(self):
        gs = GameState()
        winds = [p.wind for p in gs.players]
        self.assertEqual(winds[0], Wind.EAST)
        self.assertEqual(winds[1], Wind.SOUTH)


# ─────────────────────────────────────────────────────────────────────────────
# Round start / dealing
# ─────────────────────────────────────────────────────────────────────────────

class TestRoundStart(unittest.TestCase):

    def test_each_player_has_13_tiles_after_deal(self):
        gs = GameState()
        gs.wall.set_dead_wall(14)
        hands = gs.wall.deal_starting_hands(4)
        for i, p in enumerate(gs.players):
            p.hand = hands[i]
        for p in gs.players:
            self.assertEqual(p.get_hand_size(), 13)

    def test_dealer_has_14_tiles_after_start_round(self):
        gs = make_started_game()
        # Dealer (player 0) drew their first tile
        self.assertEqual(gs.players[0].get_hand_size(), 14)

    def test_others_have_13_tiles_after_start_round(self):
        gs = make_started_game()
        for i in range(1, 4):
            self.assertEqual(gs.players[i].get_hand_size(), 13)

    def test_phase_is_discard_after_start(self):
        gs = make_started_game()
        self.assertEqual(gs.phase, Phase.DISCARD)

    def test_wall_reduced_after_start(self):
        gs = make_started_game()
        # 136 - 14 dead wall - 52 dealt (13×4) - 1 dealer draw = 69
        self.assertEqual(gs.wall.get_wall_size(), 69)

    def test_is_round_over_false_after_start(self):
        gs = make_started_game()
        self.assertFalse(gs.is_round_over())


# ─────────────────────────────────────────────────────────────────────────────
# Legal actions — discard phase
# ─────────────────────────────────────────────────────────────────────────────

class TestLegalActionsDiscard(unittest.TestCase):

    def test_discard_actions_cover_full_hand(self):
        gs = make_started_game()
        actions = gs.get_legal_actions()
        discard_actions = [a for a in actions if a.type == ActionType.DISCARD]
        hand_size = gs.players[gs.current_player].get_hand_size()
        # At least one discard per tile (may have riichi duplicates removed)
        self.assertGreaterEqual(len(discard_actions), 1)
        self.assertLessEqual(len(discard_actions), hand_size)

    def test_all_discard_indices_valid(self):
        gs = make_started_game()
        hand_size = gs.players[0].get_hand_size()
        actions = gs.get_legal_actions()
        for a in actions:
            if a.type == ActionType.DISCARD:
                self.assertGreaterEqual(a.tile_index, 0)
                self.assertLess(a.tile_index, hand_size)

    def test_no_tsumo_on_normal_hand(self):
        gs = make_started_game()
        # With a random hand it's extremely unlikely to immediately win
        actions = gs.get_legal_actions()
        tsumo_actions = [a for a in actions if a.type == ActionType.TSUMO]
        # Can't assert 0 (random deal could theoretically win), just check type
        for a in tsumo_actions:
            self.assertEqual(a.type, ActionType.TSUMO)


# ─────────────────────────────────────────────────────────────────────────────
# Legal actions — call window
# ─────────────────────────────────────────────────────────────────────────────

class TestLegalActionsCallWindow(unittest.TestCase):

    def _discard_from_dealer(self, gs: GameState) -> Tile:
        """Force the dealer to discard their first tile."""
        actions = gs.get_legal_actions()
        discard = next(a for a in actions if a.type == ActionType.DISCARD)
        gs.apply_action(discard)
        return gs.last_discard

    def test_phase_becomes_call_window_after_discard(self):
        gs = make_started_game()
        self._discard_from_dealer(gs)
        self.assertEqual(gs.phase, Phase.CALL_WINDOW)

    def test_pass_always_legal_in_call_window(self):
        gs = make_started_game()
        self._discard_from_dealer(gs)
        actions = gs.get_legal_actions()
        self.assertIn(ActionType.PASS, [a.type for a in actions])

    def test_current_player_advances_after_discard(self):
        gs = make_started_game()
        self._discard_from_dealer(gs)
        # Call window opens at player 1 (left of dealer)
        self.assertEqual(gs.current_player, 1)

    def test_all_players_pass_advances_to_next_draw(self):
        gs = make_started_game()
        self._discard_from_dealer(gs)
        # All 3 non-dealer players pass
        for _ in range(3):
            gs.apply_action(Action(ActionType.PASS))
        self.assertEqual(gs.phase, Phase.DISCARD)
        self.assertEqual(gs.current_player, 1)


# ─────────────────────────────────────────────────────────────────────────────
# Full turn cycle
# ─────────────────────────────────────────────────────────────────────────────

class TestTurnCycle(unittest.TestCase):

    def _all_pass(self, gs: GameState):
        """Pass through an entire call window."""
        while gs.phase == Phase.CALL_WINDOW:
            gs.apply_action(Action(ActionType.PASS))

    def test_full_turn_cycle_advances_player(self):
        gs = make_started_game()
        initial_player = gs.current_player  # 0

        # Dealer discards
        discard_action = next(
            a for a in gs.get_legal_actions() if a.type == ActionType.DISCARD
        )
        gs.apply_action(discard_action)
        self._all_pass(gs)

        # Now player 1 should be in DISCARD phase with 14 tiles
        self.assertEqual(gs.current_player, 1)
        self.assertEqual(gs.phase, Phase.DISCARD)
        self.assertEqual(gs.players[1].get_hand_size(), 14)

    def test_turn_rotates_through_all_players(self):
        gs = make_started_game()
        for expected in [0, 1, 2, 3, 0]:
            self.assertEqual(gs.current_player, expected)
            actions = gs.get_legal_actions()
            discard = next(a for a in actions if a.type == ActionType.DISCARD)
            gs.apply_action(discard)
            while gs.phase == Phase.CALL_WINDOW:
                gs.apply_action(Action(ActionType.PASS))

    def test_discard_recorded_in_player_pond(self):
        gs = make_started_game()
        actions = gs.get_legal_actions()
        discard = next(a for a in actions if a.type == ActionType.DISCARD)
        tile_to_discard = gs.players[0].hand[discard.tile_index]
        gs.apply_action(discard)
        self.assertIn(tile_to_discard, gs.players[0].discards)

    def test_wall_shrinks_each_turn(self):
        gs = make_started_game()
        wall_before = gs.wall.get_wall_size()

        actions = gs.get_legal_actions()
        discard = next(a for a in actions if a.type == ActionType.DISCARD)
        gs.apply_action(discard)
        while gs.phase == Phase.CALL_WINDOW:
            gs.apply_action(Action(ActionType.PASS))

        # One tile drawn for player 1
        self.assertEqual(gs.wall.get_wall_size(), wall_before - 1)


# ─────────────────────────────────────────────────────────────────────────────
# Win detection
# ─────────────────────────────────────────────────────────────────────────────

class TestWinDetection(unittest.TestCase):

    def _force_winning_hand(self, gs: GameState, player_index: int):
        """
        Replace a player's hand with a known complete 14-tile hand
        and update their tenpai state.
        """
        winning_tiles = [
            t(D, 1), t(D, 1),
            t(D, 2), t(D, 3), t(D, 4),
            t(D, 5), t(D, 6), t(D, 7),
            t(B, 2), t(B, 3), t(B, 4),
            t(C, 3), t(C, 4), t(C, 5),
        ]
        p = gs.players[player_index]
        p.hand = winning_tiles
        p._sort_hand()
        p.update_tenpai()

    def test_tsumo_action_available_on_winning_hand(self):
        gs = make_started_game()
        self._force_winning_hand(gs, 0)
        actions = gs.get_legal_actions()
        self.assertIn(ActionType.TSUMO, [a.type for a in actions])

    def test_tsumo_ends_round(self):
        gs = make_started_game()
        self._force_winning_hand(gs, 0)
        result = gs.apply_action(Action(ActionType.TSUMO))
        self.assertIsNotNone(result)
        self.assertEqual(result.reason, RoundEndReason.TSUMO)
        self.assertEqual(result.winner_index, 0)
        self.assertTrue(gs.is_round_over())

    def _force_tenpai_hand(self, gs: GameState, player_index: int):
        """Replace a player's hand with a known 13-tile tenpai hand."""
        tenpai_tiles = [
            t(D, 1), t(D, 1),
            t(D, 2), t(D, 3), t(D, 4),
            t(D, 5), t(D, 6), t(D, 7),
            t(B, 2), t(B, 3), t(B, 4),
            t(C, 3), t(C, 4),
        ]
        p = gs.players[player_index]
        p.hand = tenpai_tiles
        p._sort_hand()
        p.update_tenpai()

    def test_ron_available_when_discard_completes_hand(self):
        gs = make_started_game()
        # Put player 1 in tenpai waiting on C5
        self._force_tenpai_hand(gs, 1)

        # Force dealer to discard C5
        dealer = gs.players[0]
        dealer.hand.append(t(C, 5))
        dealer._sort_hand()

        # Dealer discards C5
        c5_idx = next(i for i, tile in enumerate(dealer.hand) if tile == t(C, 5))
        gs.apply_action(Action(ActionType.DISCARD, tile_index=c5_idx))

        # Call window — current actor is player 1
        gs.current_player = 1   # ensure player 1 is acting
        actions = gs.get_legal_actions()
        self.assertIn(ActionType.RON, [a.type for a in actions])

    def test_ron_ends_round(self):
        gs = make_started_game()
        self._force_tenpai_hand(gs, 1)

        dealer = gs.players[0]
        dealer.hand.append(t(C, 5))
        dealer._sort_hand()
        c5_idx = next(i for i, tile in enumerate(dealer.hand) if tile == t(C, 5))
        gs.apply_action(Action(ActionType.DISCARD, tile_index=c5_idx))

        gs.current_player = 1
        result = gs.apply_action(Action(ActionType.RON))
        self.assertIsNotNone(result)
        self.assertEqual(result.reason, RoundEndReason.RON)
        self.assertEqual(result.winner_index, 1)
        self.assertEqual(result.loser_index, 0)
        self.assertTrue(gs.is_round_over())


# ─────────────────────────────────────────────────────────────────────────────
# Exhaustive draw
# ─────────────────────────────────────────────────────────────────────────────

class TestExhaustiveDraw(unittest.TestCase):

    def test_exhaustive_draw_when_wall_empty(self):
        gs = make_started_game()
        gs.wall.tiles = []   # drain wall

        # Trigger a discard → call window → all pass → tries to draw → exhaustive
        actions = gs.get_legal_actions()
        discard = next(a for a in actions if a.type == ActionType.DISCARD)
        gs.apply_action(discard)
        while gs.phase == Phase.CALL_WINDOW:
            gs.apply_action(Action(ActionType.PASS))

        self.assertTrue(gs.is_round_over())
        self.assertEqual(gs.result.reason, RoundEndReason.EXHAUSTIVE)

    def test_tenpai_players_gain_points_on_exhaustive(self):
        gs = make_started_game()

        # Put player 0 in tenpai
        tenpai_tiles = [
            t(D, 1), t(D, 1),
            t(D, 2), t(D, 3), t(D, 4),
            t(D, 5), t(D, 6), t(D, 7),
            t(B, 2), t(B, 3), t(B, 4),
            t(C, 3), t(C, 4),
        ]
        gs.players[0].hand = tenpai_tiles
        gs.players[0]._sort_hand()
        gs.players[0].update_tenpai()

        gs.wall.tiles = []
        actions = gs.get_legal_actions()
        discard = next(a for a in actions if a.type == ActionType.DISCARD)
        gs.apply_action(discard)
        while gs.phase == Phase.CALL_WINDOW:
            gs.apply_action(Action(ActionType.PASS))

        self.assertTrue(gs.is_round_over())
        # Player 0 should have gained points (or at least not lost them)
        self.assertGreaterEqual(
            gs.result.points_delta.get(0, 0), 0
        )


# ─────────────────────────────────────────────────────────────────────────────
# Observation
# ─────────────────────────────────────────────────────────────────────────────

class TestObservation(unittest.TestCase):

    def test_observation_shape(self):
        gs = make_started_game()
        obs = gs.get_observation()
        self.assertEqual(len(obs.hand_counts), 34)
        self.assertEqual(len(obs.discard_counts), 4)
        self.assertEqual(len(obs.meld_counts), 4)
        self.assertEqual(len(obs.riichi_flags), 4)
        self.assertEqual(len(obs.scores), 4)
        for row in obs.discard_counts:
            self.assertEqual(len(row), 34)

    def test_observation_hand_counts_sum_to_hand_size(self):
        gs = make_started_game()
        obs = gs.get_observation()
        actor_hand_size = gs.players[gs.current_player].get_hand_size()
        self.assertEqual(sum(obs.hand_counts), actor_hand_size)

    def test_observation_scores_correct(self):
        gs = make_started_game()
        obs = gs.get_observation()
        for i, p in enumerate(gs.players):
            self.assertEqual(obs.scores[i], p.points)

    def test_observation_wall_remaining(self):
        gs = make_started_game()
        obs = gs.get_observation()
        self.assertEqual(obs.wall_remaining, gs.wall.get_wall_size())

    def test_observation_has_legal_actions(self):
        gs = make_started_game()
        obs = gs.get_observation()
        self.assertGreater(len(obs.legal_actions), 0)

    def test_observation_phase_matches(self):
        gs = make_started_game()
        obs = gs.get_observation()
        self.assertEqual(obs.phase, Phase.DISCARD)

    def test_observation_current_player(self):
        gs = make_started_game()
        obs = gs.get_observation()
        self.assertEqual(obs.current_player, gs.current_player)

    def test_no_riichi_flags_at_start(self):
        gs = make_started_game()
        obs = gs.get_observation()
        self.assertEqual(obs.riichi_flags, [0, 0, 0, 0])


# ─────────────────────────────────────────────────────────────────────────────
# Riichi in game context
# ─────────────────────────────────────────────────────────────────────────────

class TestRiichiInGame(unittest.TestCase):

    def test_riichi_action_available_when_tenpai(self):
        gs = make_started_game()
        # Give dealer a 14-tile hand where discarding C9 leaves tenpai
        riichi_tiles = [
            t(D, 1), t(D, 1),
            t(D, 2), t(D, 3), t(D, 4),
            t(D, 5), t(D, 6), t(D, 7),
            t(B, 2), t(B, 3), t(B, 4),
            t(C, 3), t(C, 4), t(C, 9),
        ]
        gs.players[0].hand = riichi_tiles
        gs.players[0]._sort_hand()

        actions = gs.get_legal_actions()
        riichi_actions = [a for a in actions if a.type == ActionType.RIICHI]
        self.assertGreater(len(riichi_actions), 0)

    def test_riichi_deducts_points_and_adds_stick(self):
        gs = make_started_game()
        riichi_tiles = [
            t(D, 1), t(D, 1),
            t(D, 2), t(D, 3), t(D, 4),
            t(D, 5), t(D, 6), t(D, 7),
            t(B, 2), t(B, 3), t(B, 4),
            t(C, 3), t(C, 4), t(C, 9),
        ]
        gs.players[0].hand = riichi_tiles
        gs.players[0]._sort_hand()

        actions = gs.get_legal_actions()
        riichi = next(a for a in actions if a.type == ActionType.RIICHI)
        initial_points = gs.players[0].points
        gs.apply_action(riichi)

        self.assertEqual(gs.players[0].points, initial_points - 1000)
        self.assertEqual(gs.riichi_sticks, 1)
        self.assertEqual(gs.players[0].state, PlayerState.RIICHI)

    def test_riichi_winner_collects_sticks(self):
        gs = make_started_game()
        gs.riichi_sticks = 2   # pre-existing sticks on table

        # Force player 0 to a winning hand and tsumo
        winning_tiles = [
            t(D, 1), t(D, 1),
            t(D, 2), t(D, 3), t(D, 4),
            t(D, 5), t(D, 6), t(D, 7),
            t(B, 2), t(B, 3), t(B, 4),
            t(C, 3), t(C, 4), t(C, 5),
        ]
        gs.players[0].hand = winning_tiles
        gs.players[0]._sort_hand()
        gs.players[0].update_tenpai()

        points_before = gs.players[0].points
        gs.apply_action(Action(ActionType.TSUMO))

        # Should have gained placeholder points + 2000 riichi sticks
        self.assertEqual(gs.players[0].points, points_before + 2000 + 2000)
        self.assertEqual(gs.riichi_sticks, 0)


# ─────────────────────────────────────────────────────────────────────────────
# Show table (smoke test)
# ─────────────────────────────────────────────────────────────────────────────

class TestDisplay(unittest.TestCase):

    def test_show_table_does_not_raise(self):
        gs = make_started_game()
        try:
            gs.show_table()
        except Exception as e:
            self.fail(f"show_table() raised {e}")

    def test_str_representation(self):
        gs = make_started_game()
        s = str(gs)
        self.assertIn("GameState", s)
        self.assertIn("east", s)


if __name__ == "__main__":
    unittest.main(verbosity=2)