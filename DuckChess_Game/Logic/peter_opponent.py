import subprocess
import re

from DuckChess_Game.Logic.action_masker import ActionMasker

class PeterOpponent:
    """Wrapper that mimics an SB3 model but calls Peter's Rust Engine.

    This is the *binary* opponent path (offline search via a local executable),
    separate from the live-website PeterSiteConnector used by DuckPeterEnv.

    Two-call protocol (mirrors the RL env's phase loop):
      call 1 — predict() returns the piece-move action index and caches the duck action.
      call 2 — the caller reads cached_duck_action for the duck placement.
    """
    def __init__(self, binary_path):
        self.binary_path = binary_path
        self.cached_duck_action = None
        self._masker = ActionMasker()

    def predict(self, env_engine):
        fen = env_engine.bb_mgr.generate_fen(env_engine.turn, env_engine.duck_pos)

        # 5000 nodes is enough for a strong move without blocking the UI.
        cmd = [self.binary_path, "search", fen, "--nodes", "5000"]
        result = subprocess.run(cmd, capture_output=True, text=True)

        # Peter's engine returns moves in the format "e2e4@g5" (piece move @ duck dest).
        move_match = re.search(r"([a-h][1-8])([a-h][1-8])@([a-h][1-8])", result.stdout)
        if not move_match:
            # Binary failed or produced unexpected output; return action 0 as a safe fallback.
            # Action 0 decodes to ((0,0)→(0,0)) which the engine will reject as a null move.
            return 0

        start_note, end_note, duck_note = move_match.groups()

        # Peter's notation uses rank 1-8 from the bottom, so rank→row = rank-1.
        # NOTE: this is the opposite of the internal convention elsewhere (row 0 = rank 8).
        def to_coords(note):
            return int(note[1]) - 1, ord(note[0]) - ord('a')

        start, end = to_coords(start_note), to_coords(end_note)
        duck_end = to_coords(duck_note)

        # Duck moves only care about the destination; duck_pos is used as a dummy
        # "start" so encode_move produces a valid index the phase-based decoder ignores.
        self.cached_duck_action = self._masker.encode_move(env_engine.duck_pos, duck_end)
        return self._masker.encode_move(start, end), None
