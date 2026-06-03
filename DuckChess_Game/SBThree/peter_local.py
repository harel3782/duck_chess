"""
peter_local.py — Duck Chess opponent and Gymnasium environment backed by the
locally-built Peter engine (pyo3 Python bindings from petersn/duckchess).

Public API
----------
PeterLocalOpponent   — OpponentStrategy that calls the local Peter engine.
PeterLocalEnv        — BaseDuckChessEnv subclass that keeps Peter's engine
                       in sync with every half-move (agent + opponent alike).

Coordinate convention
---------------------
Our game uses:
    sq = row * 8 + col    where row 0 = rank 8 (top), row 7 = rank 1 (bottom)
    action_index = from_sq * 64 + to_sq
    duck moves:  from_sq is ALWAYS 0  (action_masker encodes (0,0) → target)

Peter's engine uses:
    sq = rank * 8 + file  where rank 0 = rank 1 (bottom), rank 7 = rank 8 (top)
    duck moves:  from == to == target_square

This module handles all necessary conversions transparently.
"""
from __future__ import annotations

import json
import logging
from typing import List, Optional

import numpy as np

from DuckChess_Game.SBThree.base.env_base import BaseDuckChessEnv, EnvConfig
from DuckChess_Game.SBThree.base.opponent_strategy import OpponentStrategy

log = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Coordinate conversion helpers                                        #
# ------------------------------------------------------------------ #

def _peter_sq_to_our_sq(p: int) -> int:
    """Convert Peter square index (a1=0) to our square index (a8=0)."""
    peter_rank = p >> 3    # // 8
    peter_file = p & 7     # % 8
    our_row = 7 - peter_rank
    return our_row * 8 + peter_file


def _our_sq_to_peter_sq(s: int) -> int:
    """Convert our square index (a8=0) to Peter square index (a1=0)."""
    our_row = s >> 3       # // 8
    our_col = s & 7        # % 8
    peter_rank = 7 - our_row
    return peter_rank * 8 + our_col


def _peter_move_to_our_action(peter_from: int, peter_to: int) -> int:
    """
    Convert a Peter move (from, to in Peter's sq numbering) to our action index.

    Peter encodes duck placements as from == to == target_square.
    Our action_masker always encodes duck moves with from_sq = 0
    (i.e. action = 0 * 64 + target_our_sq = target_our_sq).
    """
    our_to = _peter_sq_to_our_sq(peter_to)
    if peter_from == peter_to:
        # Duck placement: our encoding is 0 * 64 + our_to_sq
        return our_to
    our_from = _peter_sq_to_our_sq(peter_from)
    return our_from * 64 + our_to


def _our_action_to_peter_move_json(action_idx: int, is_duck_phase: bool) -> str:
    """
    Convert our action index + phase flag to a Peter move JSON string.

    For duck placements, Peter requires from == to == target_square.
    For regular moves, from and to differ.
    """
    action_idx = int(action_idx)     # may arrive as numpy.int64 from the policy
    our_from_sq = action_idx >> 6    # // 64
    our_to_sq   = action_idx & 63    # % 64
    peter_to = int(_our_sq_to_peter_sq(our_to_sq))

    if is_duck_phase:
        # Duck: both from and to map to the target square in Peter's coords
        return json.dumps({"from": peter_to, "to": peter_to})
    peter_from = int(_our_sq_to_peter_sq(our_from_sq))
    return json.dumps({"from": peter_from, "to": peter_to})


# ------------------------------------------------------------------ #
# PeterLocalOpponent                                                   #
# ------------------------------------------------------------------ #

class PeterLocalOpponent(OpponentStrategy):
    """
    Opponent that queries a locally-built Peter engine (pyo3 bindings).

    The engine keeps a *shadow* game state that must be kept in sync
    with our game via `mirror_action()`.  PeterLocalEnv handles this
    automatically; do not use this class with a plain BaseDuckChessEnv.

    Parameters
    ----------
    depth : int
        Alpha-beta search depth passed to ``engine.Engine.run(depth)``.
        Typical values and approximate latency at starting position:
            1 → ~1 ms    (very fast, lower quality)
            2 → ~6 ms
            3 → ~15 ms   (good balance for training)
            4 → ~4 s     (strong but slow at opening)
    seed : int
        Random seed for Peter's internal RNG (tie-breaking).
    """

    def __init__(self, depth: int = 3, seed: int = 42) -> None:
        self.depth = depth
        self.seed  = seed
        self._peter = None           # engine.Engine; created in reset()
        self._engine_mod = None      # cached module reference
        self._duck_peter_sq: Optional[int] = None  # Peter sq of duck, None = not yet placed

    # ---- lifecycle ------------------------------------------------- #

    def reset(self) -> None:
        """Reinitialise Peter's engine to the standard starting position."""
        if self._engine_mod is None:
            import engine as _eng   # pyo3 wheel — imported lazily
            self._engine_mod = _eng
        self._peter = self._engine_mod.Engine(
            seed=self.seed,
            care_about_threefold=True,
        )
        self._duck_peter_sq = None   # duck not yet placed

    # ---- sync hook (called by PeterLocalEnv._apply_action) --------- #

    def mirror_action(self, action_idx: int, is_duck_phase: bool) -> None:
        """
        Apply one half-move from our game to Peter's shadow engine.
        Called for *every* half-move (agent and opponent alike) so the
        two engines stay in lockstep.

        Duck-move encoding in Peter's engine:
          - First-ever placement (duck not on board): from == to == target_sq
          - All subsequent placements:               from == current_duck_sq, to == target_sq
        We track _duck_peter_sq to supply the correct `from`.
        """
        if self._peter is None:
            return

        action_idx = int(action_idx)   # may arrive as numpy.int64 from the policy
        our_from_sq = action_idx >> 6
        our_to_sq   = action_idx & 63
        peter_to    = int(_our_sq_to_peter_sq(our_to_sq))

        if is_duck_phase:
            if self._duck_peter_sq is None:
                # First-ever duck placement: from == to == target
                peter_from = peter_to
            else:
                # Subsequent moves: from == current duck square
                peter_from = int(self._duck_peter_sq)
            self._duck_peter_sq = peter_to          # update tracked position
        else:
            peter_from = int(_our_sq_to_peter_sq(our_from_sq))

        peter_move = json.dumps({"from": peter_from, "to": peter_to})
        err = self._peter.apply_move(peter_move)
        if err is not None:
            log.warning("Peter shadow-engine rejected move %s: %s", peter_move, err)

    # ---- OpponentStrategy interface -------------------------------- #

    def get_action(self, engine, masks: np.ndarray) -> int:
        """
        Return Peter's best half-move as our action index.

        Peter's engine is in the correct state (already mirrored) so we
        just call run() and convert the top move from the PV.

        Duck moves returned by Peter's engine use:
          - from == to == target  on the first ever placement
          - from == duck_current_sq, to == new_sq  thereafter
        In both cases we only need `to` for our duck action index
        (action_masker always encodes duck moves as 0*64 + target_sq).

        Falls back to a random legal action if the search returns nothing
        or if Peter's move is not in our legal-move mask.
        """
        if self._peter is None:
            valid = np.where(masks)[0]
            return int(np.random.choice(valid)) if len(valid) else 0

        result = self._peter.run(self.depth)
        pv: dict = json.loads(result)

        action: Optional[int] = None
        is_duck_phase = (engine.phase == "move_duck")

        if pv.get("moves"):
            best      = pv["moves"][0]
            peter_to  = best["to"]
            our_to    = _peter_sq_to_our_sq(peter_to)

            if is_duck_phase:
                # Duck placement: action_masker encodes as 0 * 64 + our_to
                action = our_to
            else:
                peter_from = best["from"]
                our_from   = _peter_sq_to_our_sq(peter_from)
                action     = our_from * 64 + our_to

        # Sanity-check: Peter's chosen action must be in our legal mask
        if action is None or not masks[action]:
            valid = np.where(masks)[0]
            if len(valid) == 0:
                return 0
            if action is not None:
                log.debug("Peter's action %d not in mask; falling back to random", action)
            action = int(np.random.choice(valid))

        return action

    # ---- model hot-swap (no-op for a fixed engine) ----------------- #

    def set_model(self, *args, **kwargs) -> None:
        """No-op: the local Peter engine is not a learned model."""


# ------------------------------------------------------------------ #
# PeterLocalEnv                                                        #
# ------------------------------------------------------------------ #

class PeterLocalEnv(BaseDuckChessEnv):
    """
    Duck Chess Gymnasium environment where the opponent is the local Peter engine.

    Overrides:
      * ``reset()``         — reinitialises Peter's shadow engine before
                              the inherited reset resets the board.
      * ``_apply_action()`` — calls ``mirror_action`` on the opponent so
                              Peter's engine tracks every half-move.

    Instantiate with an EnvConfig whose ``opponent`` is a PeterLocalOpponent.
    """

    def reset(self, seed=None, options=None):
        # Reinitialise Peter's shadow engine first (before the board resets)
        if isinstance(self._opponent, PeterLocalOpponent):
            self._opponent.reset()
        return super().reset(seed=seed, options=options)

    def _apply_action(self, action: int) -> None:
        # Capture the phase BEFORE applying (apply changes it)
        is_duck = (self.engine.phase == "move_duck")
        super()._apply_action(action)
        if isinstance(self._opponent, PeterLocalOpponent):
            self._opponent.mirror_action(action, is_duck_phase=is_duck)


# ------------------------------------------------------------------ #
# Config factories                                                     #
# ------------------------------------------------------------------ #

def make_peter_config(
    depth: int = 3,
    stage_name: str = "peter_local",
    win: float = 1.0,
    loss: float = -1.0,
    draw: float = 0.0,
    randomize_color: bool = True,
    replay_every: int = 500,
) -> EnvConfig:
    """
    Return an EnvConfig for training against the local Peter engine at `depth`.

    Reward is sparse terminal (win/loss/draw) with configurable values.
    """
    from DuckChess_Game.SBThree.base.mask_strategy import ForcedKingCaptureMask
    from DuckChess_Game.SBThree.base.reward_calculator import TerminalReward

    return EnvConfig(
        stage_name=stage_name,
        opponent=PeterLocalOpponent(depth=depth),
        reward=TerminalReward(win=win, loss=loss, draw=draw),
        mask=ForcedKingCaptureMask(),
        randomize_color=randomize_color,
        replay_every=replay_every,
        replay_chief_only=True,
    )


# Convenience presets matching website mode names
def make_peter_easy_config()   -> EnvConfig: return make_peter_config(depth=1, stage_name="peter_easy")
def make_peter_medium_config() -> EnvConfig: return make_peter_config(depth=3, stage_name="peter_medium")
def make_peter_hard_config()   -> EnvConfig: return make_peter_config(depth=5, stage_name="peter_hard")


def make_peter_mixed_env_factories(depths: List[int] = (1, 2, 3, 3)) -> List:
    """
    Return a list of zero-argument factory callables, one per parallel env,
    each with a different search depth.  Pass this list to SubprocVecEnv.

    Example::

        from stable_baselines3.common.vec_env import SubprocVecEnv
        vec = SubprocVecEnv(make_peter_mixed_env_factories())
    """
    factories = []
    for idx, depth in enumerate(depths):
        config = make_peter_config(
            depth=depth,
            stage_name=f"peter_d{depth}",
            replay_every=500,
        )

        def _make(cfg=config, rank=idx):
            return PeterLocalEnv(cfg, env_index=rank)

        factories.append(_make)
    return factories
