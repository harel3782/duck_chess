from DuckChess_Game.SBThree.base.env_base import BaseDuckChessEnv
from DuckChess_Game.SBThree.env_registry import make_stage9_config


class DuckChessEnvStage9(BaseDuckChessEnv):
    """Stage 9: SelfPlay with full positional shaping, ForcedKingCapture mask."""

    def __init__(self, render_mode=None, env_index=0):
        super().__init__(make_stage9_config(), env_index=env_index, render_mode=render_mode)
