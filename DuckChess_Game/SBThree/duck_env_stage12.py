from DuckChess_Game.SBThree.base.env_base import BaseDuckChessEnv
from DuckChess_Game.SBThree.env_registry import make_stage12_config


class DuckChessEnvStage12(BaseDuckChessEnv):
    """Stage 12: Pure self-play, sparse rewards with draw=+0.1."""

    def __init__(self, render_mode=None, env_index=0):
        super().__init__(make_stage12_config(), env_index=env_index, render_mode=render_mode)
