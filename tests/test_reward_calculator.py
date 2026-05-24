"""Tests for RewardCalculator implementations."""
import numpy as np
import pytest

from DuckChess_Game.SBThree.base.reward_calculator import ShapedReward, TerminalReward


# ------------------------------------------------------------------ #
# TerminalReward                                                       #
# ------------------------------------------------------------------ #

class TestTerminalReward:
    def test_zero_on_non_terminal(self, engine):
        r = TerminalReward()
        pre = r.capture_pre_state(engine, 0, 'w')
        post = r.capture_post_state(engine, 'w')
        assert r.calculate(pre, post, engine, 'w', terminated=False) == 0.0

    def test_win_reward(self, engine):
        r = TerminalReward(win=1.0)
        engine.game_over = True
        engine.winner = 'w'
        assert r.calculate({}, {}, engine, 'w', terminated=True) == pytest.approx(1.0)

    def test_loss_reward(self, engine):
        r = TerminalReward(loss=-1.0)
        engine.game_over = True
        engine.winner = 'b'
        assert r.calculate({}, {}, engine, 'w', terminated=True) == pytest.approx(-1.0)

    def test_draw_reward(self, engine):
        r = TerminalReward(draw=0.0)
        engine.game_over = True
        engine.winner = 'draw'
        assert r.calculate({}, {}, engine, 'w', terminated=True) == pytest.approx(0.0)

    def test_custom_draw_reward(self, engine):
        r = TerminalReward(draw=0.1)
        engine.game_over = True
        engine.winner = 'draw'
        assert r.calculate({}, {}, engine, 'w', terminated=True) == pytest.approx(0.1)

    def test_pre_state_is_empty_dict(self, engine):
        r = TerminalReward()
        assert r.capture_pre_state(engine, 0, 'w') == {}

    def test_post_state_is_empty_dict(self, engine):
        r = TerminalReward()
        assert r.capture_post_state(engine, 'w') == {}


# ------------------------------------------------------------------ #
# ShapedReward — capture_pre_state                                     #
# ------------------------------------------------------------------ #

class TestShapedRewardPreState:
    def test_returns_dict(self, engine):
        r = ShapedReward(material_weight=0.05)
        masks = engine.action_masks()
        action = int(np.where(masks)[0][0])
        pre = r.capture_pre_state(engine, action, 'w')
        assert isinstance(pre, dict)

    def test_contains_material_key(self, engine):
        r = ShapedReward(material_weight=0.05)
        masks = engine.action_masks()
        action = int(np.where(masks)[0][0])
        pre = r.capture_pre_state(engine, action, 'w')
        assert 'material' in pre

    def test_move_piece_phase_has_mobility(self, engine):
        r = ShapedReward(material_weight=0.05)
        assert engine.phase == 'move_piece'
        masks = engine.action_masks()
        action = int(np.where(masks)[0][0])
        pre = r.capture_pre_state(engine, action, 'w')
        assert 'mobility_learning' in pre

    def test_duck_phase_has_opp_mob(self, engine):
        r = ShapedReward(material_weight=0.05, blocking_scale=0.01)
        # Advance engine to duck phase via the engine's public API
        masks = engine.action_masks()
        action = int(np.where(masks)[0][0])
        start, end = engine._decode_move(action)
        engine.execute_move(start, end, animated=False)   # piece move → now in duck phase
        assert engine.phase == 'move_duck'
        masks2 = engine.action_masks()
        action2 = int(np.where(masks2)[0][0])
        pre = r.capture_pre_state(engine, action2, 'w')
        assert 'opp_mob' in pre


# ------------------------------------------------------------------ #
# ShapedReward — calculate                                             #
# ------------------------------------------------------------------ #

def _do_piece_move(engine):
    """Apply the first legal piece move; return (action_idx, start, end)."""
    masks = engine.action_masks()
    action = int(np.where(masks)[0][0])
    start, end = engine._decode_move(action)
    engine.execute_move(start, end, animated=False)
    return action, start, end


class TestShapedRewardCalculate:
    def _apply_one_piece_move(self, engine):
        r = ShapedReward(material_weight=0.05)
        masks = engine.action_masks()
        action = int(np.where(masks)[0][0])
        pre = r.capture_pre_state(engine, action, 'w')
        start, end = engine._decode_move(action)
        engine.execute_move(start, end, animated=False)
        post = r.capture_post_state(engine, 'w')
        return r, pre, post, action

    def test_non_terminal_is_finite(self, engine):
        r, pre, post, _ = self._apply_one_piece_move(engine)
        reward = r.calculate(pre, post, engine, 'w', terminated=False)
        assert np.isfinite(reward)

    def test_step_penalty_reduces_reward(self, engine):
        r_no = ShapedReward(material_weight=0.0, step_penalty=0.0)
        r_pen = ShapedReward(material_weight=0.0, step_penalty=0.01)

        masks = engine.action_masks()
        action = int(np.where(masks)[0][0])
        pre_no = r_no.capture_pre_state(engine, action, 'w')
        pre_pen = r_pen.capture_pre_state(engine, action, 'w')
        start, end = engine._decode_move(action)
        engine.execute_move(start, end, animated=False)
        post_no = r_no.capture_post_state(engine, 'w')
        post_pen = r_pen.capture_post_state(engine, 'w')

        reward_no = r_no.calculate(pre_no, post_no, engine, 'w', terminated=False)
        reward_pen = r_pen.calculate(pre_pen, post_pen, engine, 'w', terminated=False)
        assert reward_pen < reward_no

    def test_win_terminal_bonus(self, engine):
        r = ShapedReward(win=1.0)
        engine.game_over = True
        engine.winner = 'w'
        reward = r.calculate({}, {}, engine, 'w', terminated=True)
        assert reward == pytest.approx(1.0)

    def test_loss_terminal_bonus(self, engine):
        r = ShapedReward(loss=-1.0)
        engine.game_over = True
        engine.winner = 'b'
        reward = r.calculate({}, {}, engine, 'w', terminated=True)
        assert reward == pytest.approx(-1.0)

    def test_material_reward_positive_on_capture(self, engine):
        from DuckChess_Game.Logic.constants import PAWN, ROOK
        from DuckChess_Game.UI.pieces import Piece

        # White rook at (4,4) can capture black pawn at (4,5)
        engine.board[4][4] = Piece('w', ROOK)
        engine.bb_mgr.add_piece('w', ROOK, 4, 4)
        engine.board[4][5] = Piece('b', PAWN)
        engine.bb_mgr.add_piece('b', PAWN, 4, 5)

        # Action index: from_idx * 64 + to_idx  (row*8+col)
        from_idx = 4 * 8 + 4   # (4,4)
        to_idx   = 4 * 8 + 5   # (4,5)
        capture_action = from_idx * 64 + to_idx

        r = ShapedReward(material_weight=0.05)
        pre = r.capture_pre_state(engine, capture_action, 'w')
        engine.execute_move((4, 4), (4, 5), animated=False)
        post = r.capture_post_state(engine, 'w')
        reward = r.calculate(pre, post, engine, 'w', terminated=False)
        assert reward > 0.0, "Capturing a pawn should yield positive material reward"
