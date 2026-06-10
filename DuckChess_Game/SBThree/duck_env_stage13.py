from DuckChess_Game.SBThree.base.env_base import BaseDuckChessEnv
from DuckChess_Game.SBThree.env_registry import make_stage13_config


class DuckChessEnvStage13(BaseDuckChessEnv):
    """Stage 13: stage-12 league + Peter, sparse rewards, draw=+0.1."""

    def __init__(self, render_mode=None, env_index=0):
        super().__init__(make_stage13_config(), env_index=env_index, render_mode=render_mode)
