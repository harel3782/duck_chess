from DuckChess_Game.SBThree.base.env_base import BaseDuckChessEnv
from DuckChess_Game.SBThree.env_registry import make_stage7_config


class DuckChessEnvStage7(BaseDuckChessEnv):
    """Stage 7: Mixed opponent (15% AlphaBeta, 5% random, 80% latest), step penalty."""

    def __init__(self, render_mode=None, env_index=0):
        super().__init__(make_stage7_config(), env_index=env_index, render_mode=render_mode)
