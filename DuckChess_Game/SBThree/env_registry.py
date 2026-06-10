"""
EnvConfig registry for all 12 Duck Chess curriculum stages.

Each `make_stageN_config()` function returns a *new* EnvConfig instance
so that every environment gets its own independent strategy objects.

Usage::

    from DuckChess_Game.SBThree.env_registry import REGISTRY, make_stage11_config

    config = REGISTRY["stage11"]()         # factory call → fresh EnvConfig
    env = BaseDuckChessEnv(config, env_index=0)
"""
from __future__ import annotations

from DuckChess_Game.SBThree.base.env_base import EnvConfig
from DuckChess_Game.SBThree.base.mask_strategy import ForcedKingCaptureMask, StandardMask
from DuckChess_Game.SBThree.base.opponent_strategy import (
    GreedyOpponent,
    LeagueOpponent,
    SelfPlayOpponent,
)
from DuckChess_Game.SBThree.base.reward_calculator import ShapedReward, TerminalReward
from DuckChess_Game.SBThree.duck_env_stage13_fast import make_stage13_config
from DuckChess_Game.SBThree.duck_env_stage14_recovery import make_stage14_config


# ------------------------------------------------------------------ #
# Stage 1 — Random / SelfPlay fallback, sparse terminal rewards        #
# ------------------------------------------------------------------ #

def make_stage1_config() -> EnvConfig:
    return EnvConfig(
        stage_name="stage 1",
        opponent=SelfPlayOpponent(),
        reward=TerminalReward(win=1.0, loss=-1.0, draw=0.0),
        mask=StandardMask(),
        randomize_color=False,
        replay_every=50,
        replay_chief_only=False,
    )


# ------------------------------------------------------------------ #
# Stage 2 — Greedy captures, sparse terminal rewards                   #
# ------------------------------------------------------------------ #

def make_stage2_config() -> EnvConfig:
    return EnvConfig(
        stage_name="stage 2",
        opponent=GreedyOpponent(),
        reward=TerminalReward(),
        mask=StandardMask(),
        randomize_color=False,
        replay_every=50,
        replay_chief_only=False,
    )


# ------------------------------------------------------------------ #
# Stage 3 — SelfPlay, sparse terminal rewards, color randomisation     #
# ------------------------------------------------------------------ #

def make_stage3_config() -> EnvConfig:
    return EnvConfig(
        stage_name="stage 3",
        opponent=SelfPlayOpponent(),
        reward=TerminalReward(),
        mask=StandardMask(),
        randomize_color=True,
        replay_every=50,
        replay_chief_only=False,
    )


# ------------------------------------------------------------------ #
# Stage 4 — Material reward shaping introduced                         #
# ------------------------------------------------------------------ #

def make_stage4_config() -> EnvConfig:
    return EnvConfig(
        stage_name="stage 4",
        opponent=SelfPlayOpponent(),
        reward=ShapedReward(material_weight=0.05),
        mask=StandardMask(),
        randomize_color=True,
        replay_every=50,
        replay_chief_only=False,
    )


# ------------------------------------------------------------------ #
# Stage 5 — Duck-placement defence bonus, ForcedKingCapture mask       #
# ------------------------------------------------------------------ #

def make_stage5_config() -> EnvConfig:
    return EnvConfig(
        stage_name="stage 5",
        opponent=SelfPlayOpponent(),
        reward=ShapedReward(
            material_weight=0.15,
            defense_weight=0.03,
        ),
        mask=ForcedKingCaptureMask(),
        randomize_color=True,
        replay_every=1000,
        replay_chief_only=False,
    )


# ------------------------------------------------------------------ #
# Stage 6 — Step penalty added                                         #
# ------------------------------------------------------------------ #

def make_stage6_config() -> EnvConfig:
    return EnvConfig(
        stage_name="stage 6",
        opponent=SelfPlayOpponent(),
        reward=ShapedReward(
            material_weight=0.05,
            defense_weight=0.03,
            step_penalty=0.005,
        ),
        mask=ForcedKingCaptureMask(),
        randomize_color=True,
        replay_every=1000,
        replay_chief_only=False,
    )


# ------------------------------------------------------------------ #
# Stage 7 — Mixed opponent (15 % AlphaBeta, 5 % random, 80 % latest)  #
# ------------------------------------------------------------------ #

def make_stage7_config() -> EnvConfig:
    return EnvConfig(
        stage_name="stage 7",
        opponent=LeagueOpponent(alpha_beta_prob=0.15, random_prob=0.05, historical_fraction=0.0),
        reward=ShapedReward(
            material_weight=0.05,
            defense_weight=0.03,
            step_penalty=0.005,
        ),
        mask=ForcedKingCaptureMask(),
        randomize_color=True,
        replay_every=1000,
        replay_chief_only=False,
    )


# ------------------------------------------------------------------ #
# Stage 8 — Full positional rewards: castling, development, blocking   #
# ------------------------------------------------------------------ #

def make_stage8_config() -> EnvConfig:
    return EnvConfig(
        stage_name="stage 8",
        opponent=LeagueOpponent(alpha_beta_prob=0.30, random_prob=0.05, historical_fraction=0.0),
        reward=ShapedReward(
            material_weight=0.05,
            loss_multiplier=1.5,
            castling_bonus=0.20,
            development_bonus=0.05,
            defense_weight=0.03,
            blocking_scale=0.015,
            step_penalty=0.005,
        ),
        mask=ForcedKingCaptureMask(),
        randomize_color=True,
        replay_every=1000,
        replay_chief_only=False,
    )


# ------------------------------------------------------------------ #
# Stage 9 — SelfPlay with full positional shaping                      #
# ------------------------------------------------------------------ #

def make_stage9_config() -> EnvConfig:
    return EnvConfig(
        stage_name="stage 9",
        opponent=SelfPlayOpponent(),
        reward=ShapedReward(
            material_weight=0.05,
            loss_multiplier=1.5,
            castling_bonus=0.20,
            development_bonus=0.05,
            defense_weight=0.03,
            blocking_scale=0.015,
            step_penalty=0.005,
        ),
        mask=ForcedKingCaptureMask(),
        randomize_color=True,
        replay_every=1000,
        replay_chief_only=False,
    )


# ------------------------------------------------------------------ #
# Stage 10 — League opponent, anti-farming endgame scaling             #
# ------------------------------------------------------------------ #

def make_stage10_config() -> EnvConfig:
    # LeagueOpponent: 20% random, 30% historical, 50% latest
    # remaining 80% after random split as: hist_frac=0.375 → 30% hist, 50% latest
    return EnvConfig(
        stage_name="stage 10",
        opponent=LeagueOpponent(
            alpha_beta_prob=0.0,
            random_prob=0.20,
            historical_fraction=0.375,
        ),
        reward=ShapedReward(
            material_weight=0.05,
            loss_multiplier=1.2,
            castling_bonus=0.15,
            defense_weight=0.02,
            blocking_scale=0.01,
            mobility_scale=0.003,
            step_penalty=0.007,
            endgame_threshold=5.0,
            king_push_bonus=0.05,
        ),
        mask=ForcedKingCaptureMask(),
        randomize_color=True,
        replay_every=1000,
        replay_chief_only=False,
    )


# ------------------------------------------------------------------ #
# Stage 11 — Sparse rewards, 30 % AlphaBeta + 70 % RL league          #
# ------------------------------------------------------------------ #

def make_stage11_config() -> EnvConfig:
    # LeagueOpponent: 30% alpha-beta, 35% historical, 35% latest
    return EnvConfig(
        stage_name="stage 11",
        opponent=LeagueOpponent(
            alpha_beta_prob=0.30,
            random_prob=0.00,
            historical_fraction=0.50,
        ),
        reward=TerminalReward(win=1.0, loss=-1.0, draw=0.0),
        mask=StandardMask(),
        randomize_color=True,
        replay_every=1000,
        replay_chief_only=True,
    )


# ------------------------------------------------------------------ #
# Stage 12 — Pure self-play, sparse rewards, draw=+0.1                 #
# ------------------------------------------------------------------ #

def make_stage12_config() -> EnvConfig:
    # LeagueOpponent: 50% historical, 50% latest
    return EnvConfig(
        stage_name="stage 12",
        opponent=LeagueOpponent(
            alpha_beta_prob=0.00,
            random_prob=0.00,
            historical_fraction=0.50,
        ),
        reward=TerminalReward(win=1.0, loss=-1.0, draw=0.1),
        mask=StandardMask(),
        randomize_color=True,
        replay_every=1000,
        replay_chief_only=True,
    )


# ------------------------------------------------------------------ #
# Registry — maps short names to factory callables                     #
# ------------------------------------------------------------------ #

REGISTRY: dict = {
    "stage1":  make_stage1_config,
    "stage2":  make_stage2_config,
    "stage3":  make_stage3_config,
    "stage4":  make_stage4_config,
    "stage5":  make_stage5_config,
    "stage6":  make_stage6_config,
    "stage7":  make_stage7_config,
    "stage8":  make_stage8_config,
    "stage9":  make_stage9_config,
    "stage10": make_stage10_config,
    "stage11": make_stage11_config,
    "stage12": make_stage12_config,
    "stage13": make_stage13_config,
    "stage14": make_stage14_config,
}
