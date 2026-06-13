"""Debug probes for search.py: value scale, forced king capture, threat evasion."""
import numpy as np
import torch
import warnings
warnings.filterwarnings("ignore")
torch.distributions.Distribution.set_default_validate_args(False)

from sb3_contrib import MaskablePPO
from DuckChess_Game.SBThree.base.env_base import _HeadlessEngine
from DuckChess_Game.SBThree.search import DuckSearch, clone_engine
from DuckChess_Game.UI.pieces import Piece
from DuckChess_Game.Logic.constants import KING, QUEEN, ROOK, PAWN

import sys
MODEL = sys.argv[1] if len(sys.argv) > 1 else "models/duck_ppo/baseline_eval_snapshot.zip"
LEAF = sys.argv[2] if len(sys.argv) > 2 else "value"


def make_engine(pieces, turn="w"):
    e = _HeadlessEngine()
    e.clear_board()
    for color, ptype, r, c in pieces:
        e.board[r][c] = Piece(color, ptype)
        e.bb_mgr.add_piece(color, ptype, r, c)
    e.turn = turn
    e.phase = "move_piece"
    e.prev_duck_pos = (-1, -1)
    e.duck_pos = (-1, -1)
    e.en_passant_target = None
    e.game_over = False
    e.winner = None
    e.half_move_clock = 0
    e.turn_number = 1
    return e


def sq(r, c):
    return "abcdefgh"[c] + str(8 - r)


def describe(engine, piece_a, duck_a):
    if piece_a is None:
        return "(no move)"
    (sr, sc), (er, ec) = engine._decode_move(piece_a)
    s = f"{sq(sr, sc)}->{sq(er, ec)}"
    if duck_a is not None:
        _, (dr, dc) = engine._decode_move(duck_a)
        s += f" duck@{sq(dr, dc)}"
    return s


print(f"MODEL={MODEL}  LEAF={LEAF}")
model = MaskablePPO.load(MODEL, device="cpu")
searcher = DuckSearch(model, depth=2, leaf_eval=LEAF)

# --- probe 1: raw value-head scale ---------------------------------------
e = _HeadlessEngine()
obs = e._get_obs()
with torch.no_grad():
    v = model.policy.predict_values(torch.as_tensor(obs[None]))
print(f"[1] start-position raw V = {float(v):+.3f}  (tanh -> {np.tanh(float(v)):+.3f})")
vals = []
rng = np.random.default_rng(0)
for _ in range(30):
    masks = e.action_masks()
    valid = np.where(masks)[0]
    a = int(rng.choice(valid))
    s, t = e._decode_move(a)
    if e.phase == "move_piece":
        e.execute_move(s, t, animated=False)
    else:
        e.place_duck(t, animated=False)
    if e.game_over:
        break
    with torch.no_grad():
        vals.append(float(model.policy.predict_values(
            torch.as_tensor(e._get_obs()[None]))))
print(f"[1] V over 30 random plies: min={min(vals):+.3f} max={max(vals):+.3f} "
      f"mean={np.mean(vals):+.3f}")

# --- probe 2: forced king capture ------------------------------------------
# White queen d5 attacks black king e6. choose_turn MUST capture.
e = make_engine([
    ("w", KING, 7, 0), ("w", QUEEN, 3, 3),   # Ka1, Qd5
    ("b", KING, 2, 4),                        # Ke6
], turn="w")
pa, da = searcher.choose_turn(e)
print(f"[2] king capture test: chose {describe(e, pa, da)}  "
      f"(expected d5->e6)  nodes={searcher.nodes}")

# --- probe 3: threat evasion (depth 2) --------------------------------------
# Black rook e8 will capture white king e1 next turn unless white blocks
# with the duck / moves the king off the e-file.
e = make_engine([
    ("w", KING, 7, 4), ("w", PAWN, 6, 0),     # Ke1, a2
    ("b", ROOK, 0, 4), ("b", KING, 0, 7),     # Re8, Kh8
], turn="w")
pa, da = searcher.choose_turn(e)
desc = describe(e, pa, da)
(sr, sc), (er, ec) = e._decode_move(pa)
_, (dr, dc) = e._decode_move(da) if da is not None else (None, (None, None))
king_moved_off_e = (sr, sc) == (7, 4) and ec != 4
duck_blocks = dc == 4 and (dr is not None and 0 < dr < 7)
print(f"[3] threat evasion: chose {desc}  -> "
      f"{'SAFE' if (king_moved_off_e or duck_blocks) else 'STILL LOSES TO Re1'}")

# --- probe 4: root scores of top macros (sign sanity) -----------------------
e2 = make_engine([
    ("w", KING, 7, 0), ("w", QUEEN, 3, 3),
    ("b", KING, 2, 4),
], turn="w")
print("[4] root macro scores (king-capture position):")
for piece_a, duck_a, child in searcher._macro_children(e2):
    if getattr(child, "game_over", False):
        score = searcher._terminal_score(child, mover="w", depth_left=2)
    else:
        score = -searcher._leaf_value(child)
    print(f"    {describe(e2, piece_a, duck_a):<22} score={score:+.3f}")
