from DuckChess_Game.SBThree.base.env_base import BaseDuckChessEnv
from DuckChess_Game.SBThree.env_registry import make_stage10_config


class DuckChessEnvStage10(BaseDuckChessEnv):
    """Stage 10: League opponent, full shaped rewards, anti-farming endgame scaling."""

    def __init__(self, render_mode=None, env_index=0):
        super().__init__(make_stage10_config(), env_index=env_index, render_mode=render_mode)
