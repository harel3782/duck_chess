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

from DuckChess_Game.Logic.constants import KING, PIECE_VALUES, QUEEN, ROOK, BISHOP, KNIGHT, PAWN
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
        tactical_override: bool = False,
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
        self.tactical_override = tactical_override
        self.nodes = 0

    # ---- public API --------------------------------------------------- #

    def choose_turn(self, engine, debug: bool = False) -> Tuple[Optional[int], Optional[int]]:
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

        # Tactical override: force a clearly winning capture before the value
        # head gets a chance to mis-score it. Only active in web-UI mode
        # (tactical_override=True); desktop/training are unchanged.
        if self.tactical_override:
            tactical = self.find_best_tactical_move(engine)
            if tactical is not None:
                after = self._apply(engine, tactical)
                if getattr(after, "game_over", False):
                    return tactical, None
                duck_a = self._policy_top_duck(after)
                return tactical, duck_a

        root = _Node(clone_engine(engine))
        self._expand(root, add_noise=self.dirichlet > 0)
        if not root.actions:
            return None, None
        for _ in range(self.sims):
            self._simulate(root)

        # Most-visited piece action at the root.
        piece_a = int(root.actions[int(np.argmax(root.N))])

        if debug:
            self._debug_root(engine, root, piece_a)

        child = root.children.get(piece_a)
        if child is None or child.terminal or not child.actions:
            return piece_a, None
        # Most-visited duck action under that piece move.
        duck_a = int(child.actions[int(np.argmax(child.N))])
        return piece_a, duck_a

    def _debug_root(self, engine, root: "_Node", chosen_a: int) -> None:
        """Print root-node priors and visit counts for all candidates and captures."""
        from DuckChess_Game.Logic.notation_helper import NotationHelper
        def alg(a):
            start, end = engine._decode_move(a)
            return f"{NotationHelper.get_notation_coords(*start)}{NotationHelper.get_notation_coords(*end)}"

        total_n = max(1, root.N.sum())
        capture_rows, other_rows = [], []
        for idx, a in enumerate(root.actions):
            n   = int(root.N[idx])
            p   = float(root.P[idx])
            q   = float(root.W[idx] / n) if n > 0 else 0.0
            is_cap = self._captures_enemy(engine, a)
            is_king = self._captures_king(engine, a)
            tag = " [KING-CAP]" if is_king else (" [CAP]" if is_cap else "")
            row = f"  {'>>>' if a == chosen_a else '   '} {alg(a)}{tag:12s}  prior={p:.4f}  N={n:4d} ({100*n/total_n:5.1f}%)  Q={q:+.3f}"
            (capture_rows if is_cap else other_rows).append(row)

        fen = getattr(engine.bb_mgr, "generate_fen", lambda *a: "?")
        try:
            fen_str = engine.bb_mgr.generate_fen(engine.turn, engine.duck_pos)
        except Exception:
            fen_str = "unavailable"

        print(f"\n[MCTS DEBUG] sims={self.sims}  to_move={engine.turn}  FEN={fen_str}", flush=True)
        print(f"[MCTS DEBUG] chosen: {alg(chosen_a)}  ({int(root.N[root.actions.index(chosen_a)])} visits)", flush=True)
        if capture_rows:
            print("[MCTS DEBUG] --- capturing candidates ---", flush=True)
            for r in capture_rows:
                print(r, flush=True)
        else:
            print("[MCTS DEBUG] --- no capturing moves in candidate set ---", flush=True)
        print("[MCTS DEBUG] --- non-capturing candidates ---", flush=True)
        for r in other_rows:
            print(r, flush=True)
        print(flush=True)

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

    # ---- tactical safety net ------------------------------------------ #

    def find_best_tactical_move(self, engine) -> Optional[int]:
        """Return a clearly winning capture action, or None to defer to MCTS.

        Priority:
          a) King capture — bulletproof guard (should already be caught above,
             but kept here as a final safety net).
          b) Free/winning capture — destination square has net material gain >= 1
             after accounting for the cheapest enemy recapture (1-ply SEE).

        Only considers the piece phase. Returns None if no such move exists.
        """
        masks = engine.action_masks()
        valid = [int(a) for a in np.where(masks)[0]]
        enemy = "b" if engine.turn == "w" else "w"
        best_action, best_gain = None, 0

        for a in valid:
            _, end = engine._decode_move(a)
            target = engine.board[end[0]][end[1]]
            if target is None or target.color == engine.turn:
                continue  # not a capture

            target_val = PIECE_VALUES.get(target.type, 0)

            # (a) King capture — immediate win, return now.
            if target.type == KING:
                return a

            # (b) 1-ply SEE: find all enemy pieces that can recapture on `end`
            # after we land there. Duck blocks sliding rays; use current duck_pos.
            recaptors = self._attackers_of(
                engine.board, end[0], end[1], enemy, engine.duck_pos
            )
            if not recaptors:
                # No recapture possible — pure free piece.
                net = target_val
            else:
                # Worst case: enemy recaptures with their cheapest attacker.
                net = target_val - min(recaptors)

            if net >= 1 and net > best_gain:
                best_gain = net
                best_action = a

        return best_action

    @staticmethod
    def _attackers_of(board, r: int, c: int, color: str, duck_pos) -> List[int]:
        """Return a list of piece values for every `color` piece attacking (r, c).

        Mirrors RulesChecker's attack detection but collects values instead of
        returning True/False, so the caller can compute worst-case recapture cost.
        Duck blocks sliding rays exactly as in normal play.
        """
        values: List[int] = []

        # Knights
        for dr, dc in [(2,1),(2,-1),(-2,1),(-2,-1),(1,2),(1,-2),(-1,2),(-1,-2)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < 8 and 0 <= nc < 8:
                p = board[nr][nc]
                if p and p.color == color and p.type == KNIGHT:
                    values.append(PIECE_VALUES[KNIGHT])

        # Sliding: rooks + queens (orthogonal)
        for dr, dc in [(1,0),(-1,0),(0,1),(0,-1)]:
            for i in range(1, 8):
                nr, nc = r + dr*i, c + dc*i
                if not (0 <= nr < 8 and 0 <= nc < 8) or (nr, nc) == duck_pos:
                    break
                p = board[nr][nc]
                if p:
                    if p.color == color and p.type in (ROOK, QUEEN):
                        values.append(PIECE_VALUES[p.type])
                    break

        # Sliding: bishops + queens (diagonal)
        for dr, dc in [(1,1),(1,-1),(-1,1),(-1,-1)]:
            for i in range(1, 8):
                nr, nc = r + dr*i, c + dc*i
                if not (0 <= nr < 8 and 0 <= nc < 8) or (nr, nc) == duck_pos:
                    break
                p = board[nr][nc]
                if p:
                    if p.color == color and p.type in (BISHOP, QUEEN):
                        values.append(PIECE_VALUES[p.type])
                    break

        # Pawns — attack diagonally in their forward direction
        # white pawns attack upward (toward row 0), black downward (toward row 7)
        pawn_dr = 1 if color == "w" else -1  # row the pawn sits on relative to target
        for dc in [-1, 1]:
            nr, nc = r + pawn_dr, c + dc
            if 0 <= nr < 8 and 0 <= nc < 8:
                p = board[nr][nc]
                if p and p.color == color and p.type == PAWN:
                    values.append(PIECE_VALUES[PAWN])

        # King
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if 0 <= nr < 8 and 0 <= nc < 8:
                    p = board[nr][nc]
                    if p and p.color == color and p.type == KING:
                        values.append(PIECE_VALUES[KING])

        return values

    def _policy_top_duck(self, engine) -> Optional[int]:
        """Return the policy's highest-probability legal duck action.

        Used after a tactical piece move to pick the duck placement cheaply
        (one forward pass) rather than running a full MCTS tree.
        """
        masks = engine.action_masks()
        if not masks.any():
            return None
        probs = self._policy_probs(engine._get_obs(), masks)
        for a in np.argsort(-probs):
            if masks[int(a)]:
                return int(a)
        return None

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
            keep_set = set(keep)
            for a in valid:
                a = int(a)
                if a not in keep_set and self._captures_enemy(node.engine, a):
                    keep.append(a)
                    keep_set.add(a)

        p = np.array([priors_full[a] for a in keep], dtype=np.float64)
        # Floor the prior on king-captures only — they're forced wins the policy
        # chronically ignores. Other captures are left at their natural prior so
        # bad trades rank low by visit count and get rejected by the value head.
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

    def _captures_enemy(self, engine, action: int) -> bool:
        _, end = engine._decode_move(action)
        t = engine.board[end[0]][end[1]]
        return bool(t and t.color != engine.turn)

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
