from DuckChess_Game.SBThree.base.env_base import BaseDuckChessEnv
from DuckChess_Game.SBThree.env_registry import make_stage4_config


class DuckChessEnvStage4(BaseDuckChessEnv):
    """Stage 4: Material reward shaping, SelfPlay opponent."""

    def __init__(self, render_mode=None, env_index=0):
        super().__init__(make_stage4_config(), env_index=env_index, render_mode=render_mode)
