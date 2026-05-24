from DuckChess_Game.SBThree.base.env_base import BaseDuckChessEnv
from DuckChess_Game.SBThree.env_registry import make_stage11_config


class DuckChessEnvStage11(BaseDuckChessEnv):
    """Stage 11: Sparse terminal rewards, 30% AlphaBeta + 70% RL league opponent."""

    def __init__(self, render_mode=None, env_index=0):
        super().__init__(make_stage11_config(), env_index=env_index, render_mode=render_mode)
