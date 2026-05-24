from DuckChess_Game.SBThree.base.env_base import BaseDuckChessEnv
from DuckChess_Game.SBThree.env_registry import make_stage3_config


class DuckChessEnv(BaseDuckChessEnv):
    """Stage 3: SelfPlay opponent, sparse terminal rewards, randomised color."""

    def __init__(self, render_mode=None, env_index=0):
        super().__init__(make_stage3_config(), env_index=env_index, render_mode=render_mode)
