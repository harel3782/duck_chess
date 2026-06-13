"""
search.py — n-step lookahead (INCLUDING duck steps) on top of a MaskablePPO model.

Gives any trained checkpoint a real tactical horizon at inference time:
the policy head prunes the tree (move ordering + top-k candidates), the value
head evaluates the leaves, and alpha-beta negamax searches over FULL turns.

Tree structure mirrors the game exactly (this is what "including the duck
steps" means): one tree level = one player's full turn = piece move + duck
placement. With `depth=2` the searcher considers its own piece+duck AND the
opponent's best piece+duck reply — 4 half-moves, 2 of them duck moves.

Branching control (the part that makes duck search feasible — a raw turn has
~25 piece moves x ~55 duck squares ~ 1400 combos):
  * piece moves pruned to the top `piece_topk` by policy prior
    (any immediate king capture is always included — it wins on the spot);
  * duck squares pruned to the top `duck_topk` by the policy's own duck-phase
    prior, evaluated AFTER the piece move (so the duck choice reacts to it).

Terminal rules inside the search follow Duck Chess, not standard chess:
  king capture wins; NO legal moves wins (fowling); 50-move rule draws.

The engine has no unmake-move, so branches advance on clones. clone_engine()
detaches the unbounded history lists before deepcopying, which keeps a clone
cheap regardless of game length.

Usage:
    from DuckChess_Game.SBThree.search import DuckSearch
    searcher = DuckSearch("models/duck_ppo/v2/v2_latest.zip", depth=2)
    piece_action, duck_action = searcher.choose_turn(env.engine)
"""
from __future__ import annotations

import copy
from typing import List, Optional, Tuple

import numpy as np
import torch

from DuckChess_Game.Logic.constants import KING

WIN_SCORE = 1000.0   # terminal scores dominate tanh-squashed leaf values (within +-1)

_HEAVY_ATTRS = ("history", "move_log", "replay_actions")


def clone_engine(engine):
    """Deepcopy the engine WITHOUT its unbounded history/log lists."""
    saved = {}
    for attr in _HEAVY_ATTRS:
        if hasattr(engine, attr):
            saved[attr] = getattr(engine, attr)
            setattr(engine, attr, [])
    try:
        clone = copy.deepcopy(engine)
    finally:
        for attr, value in saved.items():
            setattr(engine, attr, value)
    return clone


class DuckSearch:
    """Alpha-beta negamax over full turns, guided by a MaskablePPO checkpoint."""

    def __init__(
        self,
        model,
        depth: int = 2,
        piece_topk: int = 8,
        duck_topk: int = 4,
        leaf_eval: str = "value",
        mode: str = "best",
        veto_margin: float = 0.2,
    ) -> None:
        """leaf_eval:
        'value'    — the model's value head (correct for sparse-reward models,
                     e.g. v2; on dense-reward checkpoints it saturates and misleads)
        'material' — engine material balance (model-free, robust on any checkpoint)
        'mix'      — 0.5 * material + 0.5 * value
        Candidates are expanded best-first by policy prior and ties keep the
        earlier candidate, so a flat evaluator degrades to the policy's own
        preference instead of noise.

        mode:
        'best' — always play the search's best-scoring macro.
        'veto' — play the POLICY's argmax macro (the first candidate, since
                 expansion is prior-ordered) unless the search scores it more
                 than `veto_margin` below the best macro. Deterministic: every
                 same-color game repeats the same line — measured WEAKER than
                 raw stochastic play; kept for analysis.
        'sample-veto' — SAMPLE the macro from the policy (matches how the raw
                 policy is evaluated and how it wins), then let the search veto
                 it: if its searched score is more than `veto_margin` below the
                 search best, play the search best instead. Safety net + the
                 policy's stochastic game plan.
        """
        if isinstance(model, str):
            from sb3_contrib import MaskablePPO
            model = MaskablePPO.load(model, device="cpu")
        assert leaf_eval in ("value", "material", "mix")
        assert mode in ("best", "veto", "sample-veto")
        self.model = model
        self.depth = depth
        self.piece_topk = piece_topk
        self.duck_topk = duck_topk
        self.leaf_eval = leaf_eval
        self.mode = mode
        self.veto_margin = veto_margin
        self.nodes = 0          # diagnostics: clones created on the last choose_turn
        self.nn_calls = 0       # diagnostics: batched NN forward passes

    # ---- public API --------------------------------------------------- #

    def choose_turn(self, engine) -> Tuple[Optional[int], Optional[int]]:
        """Return (piece_action, duck_action) for the side to move.

        duck_action is None when the piece move ends the game (king capture).
        Returns (None, None) if the side to move has no legal moves (fowling
        — in that case the mover has already won and there is nothing to play).
        """
        assert engine.phase == "move_piece", "choose_turn must start a full turn"
        self.nodes = 0
        self.nn_calls = 0

        best: Tuple[Optional[int], Optional[int]] = (None, None)
        best_score = -np.inf
        first: Optional[Tuple[int, Optional[int], float]] = None
        alpha, beta = -np.inf, np.inf

        for piece_a, duck_a, child in self._macro_children(engine):
            if getattr(child, "game_over", False):
                score = self._terminal_score(child, mover=engine.turn, depth_left=self.depth)
            elif self.depth <= 1:
                score = -self._leaf_value(child)
            else:
                score = -self._negamax(child, self.depth - 1, -beta, -alpha)
            if first is None:
                # Expansion is prior-ordered, so the first candidate IS the
                # policy's preferred macro — searched with a full window, its
                # score is exact (needed for veto mode).
                first = (piece_a, duck_a, score)
            if score > best_score:
                best_score, best = score, (piece_a, duck_a)
            alpha = max(alpha, score)

        if (
            self.mode == "veto"
            and first is not None
            and first[2] >= best_score - self.veto_margin
        ):
            return first[0], first[1]

        if self.mode == "sample-veto":
            sampled = self._sample_policy_macro(engine)
            if sampled is not None:
                s_piece, s_duck, s_child = sampled
                if getattr(s_child, "game_over", False):
                    s_score = self._terminal_score(s_child, mover=engine.turn,
                                                   depth_left=self.depth)
                elif self.depth <= 1:
                    s_score = -self._leaf_value(s_child)
                else:
                    s_score = -self._negamax(s_child, self.depth - 1, -np.inf, np.inf)
                if s_score >= best_score - self.veto_margin:
                    return s_piece, s_duck
        return best

    def _sample_policy_macro(self, engine):
        """Sample (piece, duck) the way raw evaluation plays the policy."""
        masks = engine.action_masks()
        if not np.any(masks):
            return None
        piece_a, _ = self.model.predict(engine._get_obs(), action_masks=masks,
                                        deterministic=False)
        child = clone_engine(engine)
        start, end = child._decode_move(int(piece_a))
        child.execute_move(start, end, animated=False)
        self.nodes += 1
        if getattr(child, "game_over", False):
            return int(piece_a), None, child
        duck_masks = child.action_masks()
        if not np.any(duck_masks):
            return None
        duck_a, _ = self.model.predict(child._get_obs(), action_masks=duck_masks,
                                       deterministic=False)
        _, duck_to = child._decode_move(int(duck_a))
        child.place_duck(duck_to, animated=False)
        self.nodes += 1
        return int(piece_a), int(duck_a), child

    # ---- search core --------------------------------------------------- #

    def _negamax(self, engine, depth: int, alpha: float, beta: float) -> float:
        """Value from the perspective of engine.turn (phase == move_piece)."""
        if depth == 0:
            return self._leaf_value(engine)

        children = list(self._macro_children(engine))
        if not children:
            # Fowling: the side to move has no legal moves -> it WINS.
            return WIN_SCORE + depth

        if depth == 1:
            # All grandchildren are leaves: evaluate them in ONE batched forward.
            return self._batched_last_level(engine, children, alpha, beta)

        best = -np.inf
        for _, _, child in children:
            if getattr(child, "game_over", False):
                score = self._terminal_score(child, mover=engine.turn, depth_left=depth)
            else:
                score = -self._negamax(child, depth - 1, -beta, -alpha)
            best = max(best, score)
            alpha = max(alpha, score)
            if alpha >= beta:
                break
        return best

    def _batched_last_level(self, engine, children, alpha: float, beta: float) -> float:
        terminal_scores: List[float] = []
        leaf_engines: List = []
        leaf_idx: List[int] = []
        for i, (_, _, child) in enumerate(children):
            if getattr(child, "game_over", False):
                terminal_scores.append(
                    self._terminal_score(child, mover=engine.turn, depth_left=1))
            else:
                terminal_scores.append(np.nan)
                leaf_engines.append(child)
                leaf_idx.append(i)
        if leaf_engines:
            values = self._leaf_values(leaf_engines)
            for j, i in enumerate(leaf_idx):
                # leaf value is from the CHILD mover's perspective -> negate
                terminal_scores[i] = -float(values[j])
        return max(terminal_scores)

    def _macro_children(self, engine):
        """Yield (piece_action, duck_action, child_engine) candidates, best-first."""
        piece_masks = engine.action_masks()
        valid = np.where(piece_masks)[0]
        if len(valid) == 0:
            return

        obs = engine._get_obs()
        priors = self._policy_probs(obs[None], piece_masks[None])[0]

        # Immediate king captures always searched first (they win on the spot).
        king_caps = [a for a in valid if self._captures_king(engine, int(a))]
        ranked = [int(a) for a in np.argsort(-priors) if piece_masks[a]]
        picks = king_caps + [a for a in ranked if a not in king_caps][: self.piece_topk]

        for piece_a in picks:
            child = clone_engine(engine)
            start, end = child._decode_move(piece_a)
            child.execute_move(start, end, animated=False)
            self.nodes += 1
            if getattr(child, "game_over", False):
                yield piece_a, None, child
                continue

            duck_masks = child.action_masks()
            d_valid = np.where(duck_masks)[0]
            if len(d_valid) == 0:
                continue
            d_priors = self._policy_probs(child._get_obs()[None], duck_masks[None])[0]
            d_ranked = [int(a) for a in np.argsort(-d_priors) if duck_masks[a]]
            for duck_a in d_ranked[: self.duck_topk]:
                gchild = clone_engine(child)
                _, duck_to = gchild._decode_move(duck_a)
                gchild.place_duck(duck_to, animated=False)
                self.nodes += 1
                yield piece_a, duck_a, gchild

    # ---- evaluation ----------------------------------------------------- #

    @staticmethod
    def _terminal_score(child, mover: str, depth_left: int) -> float:
        """Score a finished game from `mover`'s perspective; quicker wins rank higher."""
        winner = getattr(child, "winner", None)
        if winner in (None, "draw"):
            return 0.0
        return (WIN_SCORE + depth_left) if winner == mover else -(WIN_SCORE + depth_left)

    def _leaf_value(self, engine) -> float:
        """Leaf evaluation in [-1, 1], from the perspective of the side to move."""
        return float(self._leaf_values([engine])[0])

    def _leaf_values(self, engines: List) -> np.ndarray:
        """Vectorized leaf evaluation, side-to-move perspective, range [-1, 1]."""
        if self.leaf_eval in ("material", "mix"):
            mats = np.array([
                e.calculate_material_score(e.board) * (1.0 if e.turn == "w" else -1.0)
                for e in engines
            ])
            material = np.tanh(mats / 10.0)
            if self.leaf_eval == "material":
                return material
        values = self._values_batch(np.stack([e._get_obs() for e in engines]))
        value = np.tanh(values)
        if self.leaf_eval == "mix":
            return 0.5 * material + 0.5 * value
        return value

    def _captures_king(self, engine, action: int) -> bool:
        _, end = engine._decode_move(action)
        target = engine.board[end[0]][end[1]]
        return bool(target and target.type == KING and target.color != engine.turn)

    # ---- NN helpers (batched) -------------------------------------------- #

    def _policy_probs(self, obs_batch: np.ndarray, mask_batch: np.ndarray) -> np.ndarray:
        self.nn_calls += 1
        with torch.no_grad():
            obs_t = torch.as_tensor(obs_batch, device=self.model.policy.device)
            dist = self.model.policy.get_distribution(obs_t, action_masks=mask_batch)
            return dist.distribution.probs.cpu().numpy()

    def _values_batch(self, obs_batch: np.ndarray) -> np.ndarray:
        self.nn_calls += 1
        with torch.no_grad():
            obs_t = torch.as_tensor(obs_batch, device=self.model.policy.device)
            return self.model.policy.predict_values(obs_t).cpu().numpy().ravel()
