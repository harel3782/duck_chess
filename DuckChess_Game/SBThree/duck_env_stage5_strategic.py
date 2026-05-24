from DuckChess_Game.SBThree.base.env_base import BaseDuckChessEnv
from DuckChess_Game.SBThree.env_registry import make_stage5_config


class DuckChessEnvStage5(BaseDuckChessEnv):
    """Stage 5: Duck-placement defence bonus, ForcedKingCapture mask."""

    def __init__(self, render_mode=None, env_index=0):
        super().__init__(make_stage5_config(), env_index=env_index, render_mode=render_mode)
