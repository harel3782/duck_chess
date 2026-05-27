import subprocess
import re

from DuckChess_Game.Logic.action_masker import ActionMasker

class PeterOpponent:
    """Wrapper that mimics an SB3 model but calls Peter's Rust Engine.

    This is the *binary* opponent path (offline search via a local executable),
    separate from the live-website PeterSiteConnector used by DuckPeterEnv.
    """
    def __init__(self, binary_path):
        self.binary_path = binary_path
        self.cached_duck_action = None
        # The engine builds ActionMasker locally per call, so own one here.
        self._masker = ActionMasker()

    def predict(self, env_engine):
        # 1. Generate FEN from your current board state
        fen = env_engine.bb_mgr.generate_fen(env_engine.turn, env_engine.duck_pos)

        # 2. Call the binary (running 'search' on the FEN)
        # We limit nodes for speed; 5000 is usually enough for a strong move
        cmd = [self.binary_path, "search", fen, "--nodes", "5000"]
        result = subprocess.run(cmd, capture_output=True, text=True)

        # Peter's engine returns moves like "e2e4@g5"
        move_match = re.search(r"([a-h][1-8])([a-h][1-8])@([a-h][1-8])", result.stdout)
        if not move_match:
            return 0  # Fallback to a random move if something fails

        start_note, end_note, duck_note = move_match.groups()

        # 3. Convert back to your coordinates (r, c): r = rank-1, c = file index
        def to_coords(note):
            return int(note[1]) - 1, ord(note[0]) - ord('a')

        start, end = to_coords(start_note), to_coords(end_note)
        duck_end = to_coords(duck_note)

        # 4. Return the first action (Piece move) and cache the duck for the next step
        self.cached_duck_action = self._masker.encode_move(env_engine.duck_pos, duck_end)
        return self._masker.encode_move(start, end), None
