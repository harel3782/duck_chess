from DuckChess_Game.SBThree.base.env_base import BaseDuckChessEnv
from DuckChess_Game.SBThree.env_registry import make_stage1_config


class DuckChessEnv(BaseDuckChessEnv):
    """Stage 1: Random / SelfPlay opponent, sparse terminal rewards, always white."""

    def __init__(self, render_mode=None, env_index=0):
        super().__init__(make_stage1_config(), env_index=env_index, render_mode=render_mode)
