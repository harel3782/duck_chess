"""Tests for OpponentStrategy implementations."""
import numpy as np
import pytest

from DuckChess_Game.SBThree.base.opponent_strategy import (
    AlphaBetaOpponent,
    GreedyOpponent,
    LeagueOpponent,
    RandomOpponent,
    SelfPlayOpponent,
)


@pytest.fixture
def fresh_engine(engine):
    return engine


# ------------------------------------------------------------------ #
# RandomOpponent                                                       #
# ------------------------------------------------------------------ #

class TestRandomOpponent:
    def test_returns_valid_action(self, engine):
        opp = RandomOpponent()
        masks = engine.action_masks()
        action = opp.get_action(engine, masks)
        assert masks[action], "RandomOpponent returned an invalid action"

    def test_returns_int(self, engine):
        opp = RandomOpponent()
        masks = engine.action_masks()
        assert isinstance(opp.get_action(engine, masks), int)


# ------------------------------------------------------------------ #
# GreedyOpponent                                                       #
# ------------------------------------------------------------------ #

class TestGreedyOpponent:
    def test_returns_valid_action(self, engine):
        opp = GreedyOpponent()
        masks = engine.action_masks()
        action = opp.get_action(engine, masks)
        assert masks[action]

    def test_prefers_capture_when_available(self, engine):
        from DuckChess_Game.Logic.constants import PAWN
        from DuckChess_Game.UI.pieces import Piece

        # Place a black pawn on row 5 adjacent to white pawn — white can capture
        engine.board[5][3] = Piece('b', PAWN)
        engine.bb_mgr.add_piece('b', PAWN, 5, 3)

        opp = GreedyOpponent()
        masks = engine.action_masks()
        action = opp.get_action(engine, masks)

        _, end = engine._decode_move(action)
        target = engine.board[end[0]][end[1]]
        assert target is not None and target.color == 'b', \
            "GreedyOpponent did not choose a capture when one was available"


# ------------------------------------------------------------------ #
# AlphaBetaOpponent                                                    #
# ------------------------------------------------------------------ #

class TestAlphaBetaOpponent:
    def test_returns_valid_action(self, engine):
        opp = AlphaBetaOpponent()
        masks = engine.action_masks()
        action = opp.get_action(engine, masks)
        assert masks[action]

    def test_captures_king_immediately(self, engine):
        from DuckChess_Game.Logic.constants import KING
        from DuckChess_Game.UI.pieces import Piece

        # Place black king adjacent to a white piece that can capture it
        engine.board[5][4] = Piece('b', KING)
        # White pawn at (6,4) cannot capture diagonally to (5,4) — place a rook
        from DuckChess_Game.Logic.constants import ROOK
        engine.board[5][5] = None
        engine.board[4][4] = Piece('w', ROOK)
        engine.bb_mgr.add_piece('w', ROOK, 4, 4)
        engine.bb_mgr.add_piece('b', KING, 5, 4)

        opp = AlphaBetaOpponent()
        masks = engine.action_masks()
        action = opp.get_action(engine, masks)
        _, end = engine._decode_move(action)
        assert end == (5, 4), "AlphaBetaOpponent did not capture the exposed king"

    def test_board_not_mutated(self, engine):
        import copy
        opp = AlphaBetaOpponent()
        masks = engine.action_masks()
        snapshot = copy.deepcopy(engine.board)
        opp.get_action(engine, masks)
        for r in range(8):
            for c in range(8):
                orig = snapshot[r][c]
                curr = engine.board[r][c]
                if orig is None:
                    assert curr is None
                else:
                    assert curr is not None and curr.type == orig.type and curr.color == orig.color


# ------------------------------------------------------------------ #
# SelfPlayOpponent                                                     #
# ------------------------------------------------------------------ #

class TestSelfPlayOpponent:
    def test_falls_back_to_random_without_model(self, engine):
        opp = SelfPlayOpponent()
        masks = engine.action_masks()
        action = opp.get_action(engine, masks)
        assert masks[action]

    def test_set_model_nonexistent_path_is_safe(self):
        opp = SelfPlayOpponent()
        opp.set_model("/nonexistent/path.zip")
        assert opp._model is None


# ------------------------------------------------------------------ #
# LeagueOpponent                                                       #
# ------------------------------------------------------------------ #

class TestLeagueOpponent:
    def test_falls_back_to_random_without_models(self, engine):
        opp = LeagueOpponent(alpha_beta_prob=0.0, random_prob=0.0, historical_fraction=0.5)
        masks = engine.action_masks()
        action = opp.get_action(engine, masks)
        assert masks[action]

    def test_pure_random_config(self, engine):
        opp = LeagueOpponent(alpha_beta_prob=0.0, random_prob=1.0, historical_fraction=0.5)
        masks = engine.action_masks()
        for _ in range(10):
            assert masks[opp.get_action(engine, masks)]

    def test_pure_alpha_beta_config(self, engine):
        opp = LeagueOpponent(alpha_beta_prob=1.0, random_prob=0.0, historical_fraction=0.5)
        masks = engine.action_masks()
        assert masks[opp.get_action(engine, masks)]

    def test_set_model_nonexistent_paths_are_safe(self):
        opp = LeagueOpponent()
        opp.set_model("/nonexistent/latest.zip", "/nonexistent/hist.zip")
        assert opp._latest is None
        assert opp._historical is None
