"""
mcts.py — AlphaZero-style PUCT MCTS for Duck Chess, factored over piece+duck.

Why this exists: 1-step value-greedy (search.py mode=best) throws away the
policy's move-selection skill, and the raw PPO value head is a bad evaluator.
The fix is the AlphaZero recipe: a tree search that uses the POLICY as a prior
to decide which moves to explore and the (distilled) VALUE head only to score
leaves, balanced by PUCT. This is the principled way to "see n steps ahead
including the duck" and the realistic shot at Peter depth-3.

Factoring (this is the "including the duck" part): the game's two-phase turn is
kept as two tree levels — a piece-move node whose children are duck-move nodes.
So a node is a single (engine-state, phase) and its children are single
half-moves, exactly matching how the policy/value were trained. The branching
per node stays ~25 (piece) or ~55 (duck), pruned to top-k by the prior, instead
of ~1400 combined.

Leaf value: the distilled value head (leaf_eval='value' on a v2_value model),
tanh-squashed, from the side-to-move's perspective. Terminal nodes use the real
Duck Chess rules (king capture wins; NO legal moves WINS = fowling; 50-move
draw). Values are propagated with sign flips ONLY when the side-to-move changes
(it does not change between a piece node and its own duck node — same player).

Usage:
    from DuckChess_Game.SBThree.mcts import DuckMCTS
    mcts = DuckMCTS("models/duck_ppo/v2/v2_value.zip", sims=200)
    piece_a, duck_a = mcts.choose_turn(engine)
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch

from DuckChess_Game.Logic.constants import KING
from DuckChess_Game.SBThree.search import clone_engine


def headless_snapshot(game):
    """Build a pygame-free engine holding only `game`'s logic state.

    The UI game object carries pygame surfaces that can't be deepcopied, so the
    MCTS tree must run on a clean headless copy rather than on the live game.
    """
    import copy
    from DuckChess_Game.SBThree.base.env_base import _HeadlessEngine
    e = _HeadlessEngine()
    e.board = copy.deepcopy(game.board)
    e.turn = game.turn
    e.phase = getattr(game, "phase", "move_piece")
    e.duck_pos = getattr(game, "duck_pos", (-1, -1))
    e.prev_duck_pos = getattr(game, "prev_duck_pos", (-1, -1))
    e.en_passant_target = getattr(game, "en_passant_target", None)
    e.half_move_clock = getattr(game, "half_move_clock", 0)
    e.turn_number = getattr(game, "turn_number", 1)
    e.game_over = False
    e.winner = None
    e.sync_bitboards_to_2d()
    return e


class _Node:
    __slots__ = ("engine", "to_move", "terminal", "term_value",
                 "children", "priors", "actions", "N", "W", "P", "expanded")

    def __init__(self, engine):
        self.engine = engine
        self.to_move = engine.turn
        self.terminal = getattr(engine, "game_over", False)
        self.term_value = 0.0           # from this node's to_move perspective
        self.children: Dict[int, _Node] = {}
        self.actions: List[int] = []     # legal actions kept (top-k by prior)
        self.P: Optional[np.ndarray] = None  # prior over kept actions
        self.N: Optional[np.ndarray] = None  # visit counts per kept action
        self.W: Optional[np.ndarray] = None  # total value per kept action
        self.expanded = False


class DuckMCTS:
    def __init__(
        self,
        model,
        sims: int = 200,
        c_puct: float = 1.5,
        piece_topk: int = 8,
        duck_topk: int = 6,
        dirichlet: float = 0.0,
    ) -> None:
        if isinstance(model, str):
            from sb3_contrib import MaskablePPO
            model = MaskablePPO.load(model, device="cpu")
        self.model = model
        self.sims = sims
        self.c_puct = c_puct
        self.piece_topk = piece_topk
        self.duck_topk = duck_topk
        self.dirichlet = dirichlet
        self.nodes = 0

    # ---- public API --------------------------------------------------- #

    def choose_turn(self, engine) -> Tuple[Optional[int], Optional[int]]:
        """Run MCTS from a move_piece-phase state; return (piece_a, duck_a)."""
        assert engine.phase == "move_piece"
        self.nodes = 0

        # Never search past an available king capture — it wins on the spot.
        # (Same invariant as ForcedKingCaptureMask in training/eval; the policy
        # often puts ~0 prior on the capture, so PUCT would never explore it.)
        masks0 = engine.action_masks()
        for a in np.where(masks0)[0]:
            if self._captures_king(engine, int(a)):
                return int(a), None

        root = _Node(clone_engine(engine))
        self._expand(root, add_noise=self.dirichlet > 0)
        if not root.actions:
            return None, None
        for _ in range(self.sims):
            self._simulate(root)

        # Most-visited piece action at the root.
        piece_a = int(root.actions[int(np.argmax(root.N))])
        child = root.children.get(piece_a)
        if child is None or child.terminal or not child.actions:
            return piece_a, None
        # Most-visited duck action under that piece move.
        duck_a = int(child.actions[int(np.argmax(child.N))])
        return piece_a, duck_a

    def choose_turn_with_targets(self, engine, temperature: float = 1.0, rng=None):
        """Run MCTS and return (piece_a, duck_a, targets) for Expert Iteration.

        `targets` is a list of (obs, action_idxs, visit_probs, to_move) — one
        entry for the piece node and one for the chosen duck node. visit_probs is
        the normalized root visit-count distribution: the AlphaZero policy target
        π that train_exit regresses the policy head onto. Recording the DUCK node
        too is what teaches stronger duck placement (the second exploit).

        Moves are SAMPLED from π at `temperature` (→0 = argmax) so self-play
        explores instead of collapsing to one line — the antidote to the
        repetitive-opening exploit at the search level. `to_move` carries the
        side so the outcome label z gets the right sign per position.
        """
        assert engine.phase == "move_piece"
        if rng is None:
            rng = np.random.default_rng()
        self.nodes = 0

        # Forced winning capture — degenerate but valuable target: it teaches the
        # policy to take an enemy king, which it chronically under-weights.
        masks0 = engine.action_masks()
        for a in np.where(masks0)[0]:
            if self._captures_king(engine, int(a)):
                obs = engine._get_obs().copy()
                return int(a), None, [
                    (obs, [int(a)], np.array([1.0], dtype=np.float32), engine.turn)
                ]

        root = _Node(clone_engine(engine))
        self._expand(root, add_noise=self.dirichlet > 0)
        if not root.actions:
            return None, None, []
        for _ in range(self.sims):
            self._simulate(root)

        targets = []
        piece_pi = root.N / max(1.0, root.N.sum())
        targets.append((root.engine._get_obs().copy(), list(root.actions),
                        piece_pi.astype(np.float32), root.to_move))

        piece_a = int(root.actions[self._sample_visit(root.N, temperature, rng)])
        child = root.children.get(piece_a)
        if child is None or child.terminal or not child.actions:
            return piece_a, None, targets

        duck_pi = child.N / max(1.0, child.N.sum())
        targets.append((child.engine._get_obs().copy(), list(child.actions),
                        duck_pi.astype(np.float32), child.to_move))
        duck_a = int(child.actions[self._sample_visit(child.N, temperature, rng)])
        return piece_a, duck_a, targets

    @staticmethod
    def _sample_visit(counts, temperature: float, rng) -> int:
        """Index sampled from visit counts at `temperature` (≤0 → argmax)."""
        counts = np.asarray(counts, dtype=np.float64)
        if temperature <= 1e-3 or counts.sum() <= 0:
            return int(np.argmax(counts))
        p = counts ** (1.0 / temperature)
        p /= p.sum()
        return int(rng.choice(len(counts), p=p))

    # ---- search core -------------------------------------------------- #

    def _simulate(self, node: _Node) -> float:
        """One PUCT simulation; returns value from `node.to_move` perspective."""
        if node.terminal:
            return node.term_value
        if not node.expanded:
            return self._expand(node)
        if not node.actions:
            return 0.0

        # PUCT selection over kept actions.
        total_N = max(1.0, node.N.sum())
        q = np.where(node.N > 0, node.W / np.maximum(node.N, 1), 0.0)
        u = self.c_puct * node.P * math.sqrt(total_N) / (1.0 + node.N)
        a_idx = int(np.argmax(q + u))
        action = node.actions[a_idx]

        child = node.children.get(action)
        if child is None:
            child = _Node(self._apply(node.engine, action))
            node.children[action] = child
            self.nodes += 1

        child_val = self._simulate(child)
        # Flip sign only when the side to move differs between node and child.
        v = child_val if child.to_move == node.to_move else -child_val

        node.N[a_idx] += 1
        node.W[a_idx] += v
        return v

    def _expand(self, node: _Node, add_noise: bool = False) -> float:
        """Evaluate a leaf: set priors+value, return value from its perspective."""
        node.expanded = True
        if node.terminal:
            node.term_value = self._terminal_value(node.engine)
            return node.term_value

        masks = node.engine.action_masks()
        valid = np.where(masks)[0]
        if len(valid) == 0:
            # No legal moves: fowling — the side to move WINS.
            node.terminal = True
            node.term_value = 1.0
            return 1.0

        priors_full = self._policy_probs(node.engine._get_obs(), masks)
        topk = self.piece_topk if node.engine.phase == "move_piece" else self.duck_topk
        # Always keep an immediate king capture (piece phase) — it wins now.
        keep = [int(a) for a in np.argsort(-priors_full) if masks[a]][:topk]
        if node.engine.phase == "move_piece":
            for a in valid:
                if self._captures_king(node.engine, int(a)) and int(a) not in keep:
                    keep.append(int(a))

        p = np.array([priors_full[a] for a in keep], dtype=np.float64)
        # Floor the prior on any kept king-capture so PUCT actually explores it
        # (the policy often assigns it ~0). A winning move must not be ignored.
        if node.engine.phase == "move_piece":
            for i, a in enumerate(keep):
                if self._captures_king(node.engine, a):
                    p[i] = max(p[i], 1.0)
        p = p / p.sum() if p.sum() > 0 else np.ones(len(keep)) / len(keep)
        if add_noise and len(keep) > 1:
            noise = np.random.dirichlet([self.dirichlet] * len(keep))
            p = 0.75 * p + 0.25 * noise

        node.actions = keep
        node.P = p
        node.N = np.zeros(len(keep))
        node.W = np.zeros(len(keep))
        return self._leaf_value(node.engine)

    # ---- engine + NN helpers ----------------------------------------- #

    def _apply(self, engine, action: int):
        child = clone_engine(engine)
        start, end = child._decode_move(action)
        if child.phase == "move_piece":
            child.execute_move(start, end, animated=False)
        else:
            child.place_duck(end, animated=False)
        return child

    @staticmethod
    def _terminal_value(engine) -> float:
        winner = getattr(engine, "winner", None)
        if winner in (None, "draw"):
            return 0.0
        # Node.to_move is whoever is on turn at this terminal state.
        return 1.0 if winner == engine.turn else -1.0

    def _captures_king(self, engine, action: int) -> bool:
        _, end = engine._decode_move(action)
        t = engine.board[end[0]][end[1]]
        return bool(t and t.type == KING and t.color != engine.turn)

    def _leaf_value(self, engine) -> float:
        with torch.no_grad():
            obs = torch.as_tensor(engine._get_obs()[None], device=self.model.policy.device)
            return float(np.tanh(self.model.policy.predict_values(obs).cpu().numpy().ravel()[0]))

    def _policy_probs(self, obs: np.ndarray, mask: np.ndarray) -> np.ndarray:
        with torch.no_grad():
            obs_t = torch.as_tensor(obs[None], device=self.model.policy.device)
            dist = self.model.policy.get_distribution(obs_t, action_masks=mask[None])
            return dist.distribution.probs.cpu().numpy()[0]
