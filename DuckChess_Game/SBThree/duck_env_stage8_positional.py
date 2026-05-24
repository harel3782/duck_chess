from DuckChess_Game.SBThree.base.env_base import BaseDuckChessEnv
from DuckChess_Game.SBThree.env_registry import make_stage8_config


class DuckChessEnvStage8(BaseDuckChessEnv):
    """Stage 8: Full positional rewards — castling, development, blocking, loss multiplier."""

    def __init__(self, render_mode=None, env_index=0):
        super().__init__(make_stage8_config(), env_index=env_index, render_mode=render_mode)
