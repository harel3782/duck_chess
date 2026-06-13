#!/usr/bin/env python
"""
view_one_game.py — Play one game (Stage-13 model vs Peter) and open a browser viewer.

Uses a MANUAL game loop (bypassing BaseDuckChessEnv) so every single half-move
— both the model's and Peter's — is captured and visible in the viewer.

Usage:
  python view_one_game.py
  python view_one_game.py --model "models/duck_ppo/stage 13/stage13_latest.zip" --depth 2
  python view_one_game.py --depth 3 --out my_game.html
"""
from __future__ import annotations

import argparse
import base64
import glob
import json
import os
import webbrowser
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import torch

torch.distributions.Distribution.set_default_validate_args(False)

from sb3_contrib import MaskablePPO

from DuckChess_Game.SBThree.base.env_base import _HeadlessEngine
from DuckChess_Game.SBThree.base.mask_strategy import StandardMask
from DuckChess_Game.SBThree.peter_local import PeterLocalOpponent

TYPE_NAME = {"K": "king", "Q": "queen", "R": "rook",
             "B": "bishop", "N": "knight", "P": "pawn"}
ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "pieces")


# ── helpers ───────────────────────────────────────────────────────────────────

def _b64(path: str) -> str:
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def _load_images() -> dict:
    imgs: dict = {}
    for letter, name in TYPE_NAME.items():
        for color in ("w", "b"):
            key = f"{color}{letter}"
            fpath = os.path.join(ASSET_DIR, f"{name}-{color}.png")
            if os.path.exists(fpath):
                imgs[key] = _b64(fpath)
    duck_path = os.path.join(ASSET_DIR, "duck.png")
    if os.path.exists(duck_path):
        imgs["duck"] = _b64(duck_path)
    return imgs


def _apply(engine: _HeadlessEngine, action: int) -> None:
    """Apply one half-move to the engine."""
    start, end = engine._decode_move(action)
    if engine.phase == "move_piece":
        engine.execute_move(start, end, animated=False)
    else:
        engine.place_duck(end, animated=False)


def _snapshot(engine: _HeadlessEngine, learning_color: str,
              action: int | None, mover: str, phase_before: str) -> dict:
    """Capture the full board state as a JSON-serialisable dict."""
    cells = []
    for r in range(8):
        row = []
        for c in range(8):
            p = engine.board[r][c]
            row.append({"color": p.color, "type": p.type} if p else None)
        cells.append(row)

    duck = list(engine.duck_pos) if hasattr(engine, "duck_pos") else [-1, -1]

    # Highlight squares for the last action
    highlight = []
    if action is not None:
        to_sq  = action & 63
        from_sq = action >> 6
        to_r, to_c = divmod(to_sq, 8)
        highlight.append([to_r, to_c])
        if phase_before == "move_piece" and from_sq != to_sq:
            fr, fc = divmod(from_sq, 8)
            highlight.append([fr, fc])

    return {
        "cells": cells,
        "duck": duck,
        "highlight": highlight,
        "mover": mover,           # "model" | "peter" | "start"
        "phase": phase_before,    # "move_piece" | "move_duck"
        "model_color": learning_color,
    }


# ── game loop ─────────────────────────────────────────────────────────────────

def play_one_game(model_path: str, depth: int = 2) -> tuple[list, dict]:
    """
    Manual game loop — every half-move by BOTH sides is captured.
    Returns (snapshots, meta).
    """
    model  = MaskablePPO.load(model_path, device="cpu")
    peter  = PeterLocalOpponent(depth=depth)
    masker = StandardMask()

    engine = _HeadlessEngine()
    engine.reset_game_state()
    peter.reset()

    learning_color = np.random.choice(["w", "b"])
    peter_color    = "b" if learning_color == "w" else "w"

    snapshots: list = [_snapshot(engine, learning_color, None, "start", "move_piece")]

    MAX_HALFMOVES = 500
    halfmoves = 0

    def _step(who: str) -> bool:
        """Play one half-move for `who` ('model' or 'peter'). Returns True if game over."""
        nonlocal halfmoves
        phase_before = engine.phase
        masks = masker.get_masks(engine)

        if not np.any(masks):
            engine.game_over = True
            engine.winner = "draw"
            return True

        if who == "model":
            obs = engine._get_obs()
            action, _ = model.predict(obs, action_masks=masks, deterministic=False)
            action = int(action)
        else:
            action = peter.get_action(engine, masks)

        # Mirror to Peter's shadow engine (needed so Peter tracks the model's moves too)
        peter.mirror_action(action, is_duck_phase=(phase_before == "move_duck"))
        _apply(engine, action)
        halfmoves += 1
        snapshots.append(_snapshot(engine, learning_color, action, who, phase_before))
        return bool(getattr(engine, "game_over", False))

    def _play_color(color: str) -> bool:
        """Play a full turn (piece + duck) for `color`. Returns True if game over."""
        who = "model" if color == learning_color else "peter"
        # piece move
        if engine.turn != color or getattr(engine, "game_over", False):
            return getattr(engine, "game_over", False)
        if _step(who):
            return True
        # duck placement (same player continues in duck phase)
        if engine.phase == "move_duck" and not getattr(engine, "game_over", False):
            if _step(who):
                return True
        return False

    # If agent plays black, Peter goes first
    first_color = "w"   # white always moves first in chess
    turn_order = [first_color]  # we iterate one full-turn at a time

    while halfmoves < MAX_HALFMOVES:
        current = engine.turn  # whose piece-move turn it is
        if getattr(engine, "game_over", False):
            break
        if _play_color(current):
            break

    winner = getattr(engine, "winner", None)
    if winner == learning_color:
        result = "Model wins!"
        result_display = "Model wins!"
    elif winner == peter_color:
        result = f"Peter (depth {depth}) wins!"
        result_display = result
    else:
        result = "Draw"
        result_display = "Draw"

    meta = {
        "result": result,
        "halfmoves": halfmoves,
        "model_color": learning_color,
        "peter_color": peter_color,
        "peter_depth": depth,
        "model_file": os.path.basename(model_path),
    }
    print(f"  {result_display}  ({halfmoves} half-moves, {len(snapshots)} snapshots)")
    return snapshots, meta


# ── HTML generation ───────────────────────────────────────────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Duck Chess — Game Viewer</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #1a1a2e; color: #e0e0e0;
         font-family: 'Segoe UI', sans-serif;
         display: flex; flex-direction: column; align-items: center; padding: 20px; }
  h1 { margin: 12px 0 4px; font-size: 1.4rem; color: #c9d1d9; }
  #meta { font-size: 0.85rem; color: #8b949e; margin-bottom: 10px; }
  #result-banner { font-size: 1.1rem; font-weight: bold; color: #f0c040;
                   min-height: 1.5em; margin-bottom: 6px; }
  #board-wrap { display: flex; align-items: flex-start; gap: 20px; }
  #ranks { display: grid; grid-template-rows: repeat(8,64px);
           align-items: center; color: #666; font-size: 0.78rem;
           margin-right: 4px; text-align: right; }
  #board { display: grid; grid-template-columns: repeat(8,64px);
           grid-template-rows: repeat(8,64px); border: 2px solid #555; }
  #files { display: grid; grid-template-columns: repeat(8,64px);
           text-align: center; color: #666; font-size: 0.78rem; margin-top: 3px; }
  .sq { width:64px; height:64px; display:flex; align-items:center;
        justify-content:center; position:relative; cursor:default; }
  .sq.light { background: #f0d9b5; }
  .sq.dark  { background: #b58863; }
  .sq.hl    { outline: 3px solid #f6f669; outline-offset: -3px; z-index:1; }
  .sq img   { width:56px; height:56px; pointer-events:none; }
  #info { width: 230px; }
  #move-label   { font-size: 0.95rem; margin-bottom: 6px; color: #c9d1d9; min-height:1.3em; }
  #move-counter { font-size: 0.8rem;  color: #8b949e; margin-bottom: 10px; }
  #controls { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
  button { padding: 7px 14px; border: none; border-radius: 6px; cursor: pointer;
           font-size: 0.85rem; background: #30363d; color: #c9d1d9; transition: background .15s; }
  button:hover   { background: #444d56; }
  button:disabled { opacity: .4; cursor: default; }
  #play-btn { background: #1f6feb; color: #fff; }
  #play-btn:hover { background: #388bfd; }
  #move-list { max-height: 420px; overflow-y: auto; font-size: 0.78rem; }
  .mv { padding: 3px 7px; cursor: pointer; border-radius: 4px; color: #8b949e; }
  .mv:hover { background: #21262d; color: #c9d1d9; }
  .mv.active { background: #1f6feb33; color: #c9d1d9; font-weight: bold; }
  .mv.model  { color: #79c0ff; }
  .mv.peter  { color: #ffa657; }
  .mv.start  { color: #666; }
  #legend { display:flex; gap:14px; font-size:0.78rem; margin-bottom:10px; color:#8b949e; }
  .dot { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:4px; }
  .dot.model { background:#79c0ff; }
  .dot.peter { background:#ffa657; }
</style>
</head>
<body>
<h1>🦆 Duck Chess — Game Viewer</h1>
<div id="meta"></div>
<div id="result-banner"></div>
<div id="board-wrap">
  <div style="display:flex;align-items:flex-start">
    <div id="ranks"></div>
    <div>
      <div id="board"></div>
      <div id="files"></div>
    </div>
  </div>
  <div id="info">
    <div id="legend">
      <span><span class="dot model"></span>Model</span>
      <span><span class="dot peter"></span>Peter</span>
    </div>
    <div id="move-label"></div>
    <div id="move-counter"></div>
    <div id="controls">
      <button id="prev-btn" onclick="step(-1)">◀</button>
      <button id="next-btn" onclick="step(+1)">▶</button>
      <button id="play-btn" onclick="togglePlay()">▶ Play</button>
    </div>
    <div id="move-list"></div>
  </div>
</div>

<script>
const IMAGES    = %%IMAGES%%;
const SNAPSHOTS = %%SNAPSHOTS%%;
const META      = %%META%%;

let idx = 0, playing = false, timer = null;

// Build board squares
const boardEl = document.getElementById('board');
for (let r = 0; r < 8; r++)
  for (let c = 0; c < 8; c++) {
    const el = document.createElement('div');
    el.className = 'sq ' + ((r+c)%2===0 ? 'light' : 'dark');
    el.id = 'sq'+(r*8+c);
    boardEl.appendChild(el);
  }

const ranksEl = document.getElementById('ranks');
for (let r = 0; r < 8; r++) {
  const el = document.createElement('div');
  el.textContent = 8 - r;
  ranksEl.appendChild(el);
}
const filesEl = document.getElementById('files');
'abcdefgh'.split('').forEach(f => {
  const el = document.createElement('div');
  el.textContent = f;
  filesEl.appendChild(el);
});

// Build move list
const mlEl = document.getElementById('move-list');
SNAPSHOTS.forEach((s, i) => {
  const el = document.createElement('div');
  el.id = 'mv' + i;
  const half = Math.ceil(i / 2);
  const phStr = s.phase === 'move_piece' ? 'piece' : 'duck';
  let label = i === 0 ? 'Start' :
    (s.mover === 'model' ? '🤖 Model' : '🔥 Peter') + ' — ' + phStr + ' (' + half + ')';
  el.textContent = label;
  el.className = 'mv ' + s.mover;
  el.onclick = () => render(i);
  mlEl.appendChild(el);
});

function render(newIdx) {
  idx = Math.max(0, Math.min(newIdx, SNAPSHOTS.length - 1));
  const s = SNAPSHOTS[idx];

  // Clear squares
  for (let i = 0; i < 64; i++) {
    const el = document.getElementById('sq'+i);
    el.innerHTML = '';
    const r = Math.floor(i/8), c = i%8;
    el.className = 'sq ' + ((r+c)%2===0 ? 'light' : 'dark');
  }

  // Highlights
  (s.highlight || []).forEach(([r,c]) => {
    document.getElementById('sq'+(r*8+c)).classList.add('hl');
  });

  // Pieces
  for (let r = 0; r < 8; r++)
    for (let c = 0; c < 8; c++) {
      const p = s.cells[r][c];
      if (!p) continue;
      const key = p.color + p.type;
      if (!IMAGES[key]) continue;
      const img = document.createElement('img');
      img.src = IMAGES[key];
      document.getElementById('sq'+(r*8+c)).appendChild(img);
    }

  // Duck
  const [dr, dc] = s.duck;
  if (dr >= 0 && IMAGES['duck']) {
    const img = document.createElement('img');
    img.src = IMAGES['duck'];
    document.getElementById('sq'+(dr*8+dc)).appendChild(img);
  }

  // Labels
  const half = Math.ceil(idx / 2);
  const pColor = s.model_color === 'w' ? 'b' : 'w';
  const phStr = s.phase === 'move_piece' ? 'piece move' : 'duck placement';
  document.getElementById('move-label').textContent =
    idx === 0 ? 'Starting position' :
    s.mover === 'model'
      ? `🤖 Model (${s.model_color}) — ${phStr}`
      : `🔥 Peter d${META.peter_depth} (${pColor}) — ${phStr}`;
  document.getElementById('move-counter').textContent =
    `Half-move ${idx} / ${SNAPSHOTS.length - 1}`;
  document.getElementById('result-banner').textContent =
    idx === SNAPSHOTS.length - 1 ? META.result : '';

  // Buttons
  document.getElementById('prev-btn').disabled = idx === 0;
  document.getElementById('next-btn').disabled = idx === SNAPSHOTS.length - 1;

  // Sync move list
  document.querySelectorAll('.mv').forEach((el, i) => {
    el.className = 'mv ' + SNAPSHOTS[i].mover + (i === idx ? ' active' : '');
  });
  const act = document.getElementById('mv'+idx);
  if (act) act.scrollIntoView({block:'nearest'});
}

function step(d) { render(idx + d); }

function togglePlay() {
  playing = !playing;
  document.getElementById('play-btn').textContent = playing ? '⏸ Pause' : '▶ Play';
  if (playing) tick(); else { clearTimeout(timer); timer = null; }
}

function tick() {
  if (!playing) return;
  if (idx >= SNAPSHOTS.length - 1) {
    playing = false;
    document.getElementById('play-btn').textContent = '▶ Play';
    return;
  }
  step(+1);
  timer = setTimeout(tick, 650);
}

document.getElementById('meta').textContent =
  `Model: ${META.model_file}  |  Peter depth ${META.peter_depth}  |  ${META.halfmoves} half-moves`;

render(0);

document.addEventListener('keydown', e => {
  if (e.key === 'ArrowRight' || e.key === 'ArrowDown') step(+1);
  if (e.key === 'ArrowLeft'  || e.key === 'ArrowUp')   step(-1);
  if (e.key === ' ') { e.preventDefault(); togglePlay(); }
});
</script>
</body>
</html>
"""


def generate_html(snapshots: list, meta: dict, out_path: str) -> None:
    imgs = _load_images()
    html = HTML_TEMPLATE \
        .replace("%%IMAGES%%",    json.dumps(imgs)) \
        .replace("%%SNAPSHOTS%%", json.dumps(snapshots)) \
        .replace("%%META%%",      json.dumps(meta))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  HTML written: {out_path}")


def _find_model() -> str:
    candidates = [
        os.path.join("models", "duck_ppo", "stage 13", "stage13_latest.zip"),
        os.path.join("models", "duck_ppo", "strong", "strong_final.zip"),
        os.path.join("models", "duck_ppo", "stage 12", "stage12_final_v52.zip"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    found = glob.glob(os.path.join("models", "duck_ppo", "stage 12", "*.zip"))
    if found:
        return max(found, key=os.path.getmtime)
    raise FileNotFoundError("No model found — pass --model explicitly.")


def main():
    p = argparse.ArgumentParser(description="Play one game and open browser viewer")
    p.add_argument("--model", default=None,         help="Path to model .zip")
    p.add_argument("--depth", type=int, default=2,  help="Peter search depth (default 2)")
    p.add_argument("--out",   default="game_viewer.html", help="Output HTML file")
    args = p.parse_args()

    model_path = args.model or _find_model()
    print(f"Model : {model_path}")
    print(f"Peter : depth {args.depth}")
    print("Playing game ...")

    snapshots, meta = play_one_game(model_path, depth=args.depth)

    out = os.path.abspath(args.out)
    generate_html(snapshots, meta, out)

    url = "file:///" + out.replace("\\", "/")
    print(f"Opening: {url}")
    webbrowser.open(url)


if __name__ == "__main__":
    main()
