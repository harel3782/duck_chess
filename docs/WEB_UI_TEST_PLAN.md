# Duck Chess Web UI — Comprehensive Test Plan

## Overview

The Duck Chess Web UI consists of:
- **Backend**: FastAPI application (`web_ui/server.py`) managing game sessions, model inference, persistence
- **Frontend**: Single-page HTML/JavaScript application (`web_ui/index.html`) with game board UI, replay mode, save/load
- **Game Engine Bridge**: `_HeadlessEngine` from `DuckChess_Game.SBThree.base.env_base` for move validation and execution
- **Models**: MaskablePPO checkpoints loaded lazily and cached per-session

This test plan prioritizes testing the **integration points** where bugs are most likely: API contract violations, state synchronization, and game-logic edge cases exposed through the web layer.

---

## 1. Backend API Tests (`test_web_server.py`)

### 1.1 Model Management & Initialization

**Complexity**: Low  
**Priority**: High (blocks all game functionality)

#### Test Cases:
- [ ] `test_list_models_returns_existing_files_only` — Verify only valid model paths are listed in `/api/models`
- [ ] `test_list_models_empty_when_no_models` — Return `{"models": []}` if `models/duck_ppo/` is empty
- [ ] `test_get_model_loads_and_caches` — Same model ID loads once, cached on second call
- [ ] `test_get_model_falls_back_to_first_if_missing` — Invalid model ID → use first available
- [ ] `test_get_model_404_when_no_models` — HTTPException(500) when zero models available
- [ ] `test_get_model_thread_safe_load` — Concurrent requests for same model don't double-load
- [ ] `test_model_device_cpu_only` — Verify models load with `device="cpu"` regardless of system

### 1.2 Session Management & Game Lifecycle

**Complexity**: Medium  
**Priority**: Critical

#### Test Cases:
- [ ] `test_new_game_2player_creates_session` — POST `/api/new-game` with `model=null` creates valid game ID
- [ ] `test_new_game_vs_model_preloads_model` — `model="stage12"` validates & preloads that model
- [ ] `test_new_game_white_vs_model_ai_moves_first` — Player color black → AI move returned in response
- [ ] `test_new_game_black_vs_model_no_ai_move` — Player color white → no AI move in response
- [ ] `test_new_game_2player_no_model_label` — 2-player game returns `modelLabel: "2 Players"`
- [ ] `test_session_stored_in_memory_keyed_by_game_id` — Session persists across API calls with same ID
- [ ] `test_session_not_found_returns_404` — Unknown game ID → HTTPException(404, "Game not found")
- [ ] `test_session_initial_board_is_standard_start` — All sessions start with standard chess position
- [ ] `test_session_initial_duck_position` — Duck begins at (-1, -1) (off-board)

### 1.3 Move Execution & Validation

**Complexity**: High  
**Priority**: Critical

#### Test Cases:
- [ ] `test_move_piece_basic_pawn_push` — e2e4 returns valid board state
- [ ] `test_move_piece_updates_turn_after_piece_move` — After white moves, `turn` still "w" (pending duck)
- [ ] `test_move_piece_invalid_piece_no_piece_on_from_square` — HTTPException(400, "No piece of yours")
- [ ] `test_move_piece_invalid_illegal_destination` — HTTPException(400, "Illegal move for that piece")
- [ ] `test_move_piece_blocks_opponent_color_in_vs_model` — Player color white cannot move black piece
- [ ] `test_move_piece_allows_any_color_in_2player` — Both colors movable (turn-based)
- [ ] `test_move_piece_wrong_phase_not_in_move_piece` — If phase is "move_duck", HTTPException(400, "Not your move-piece phase")
- [ ] `test_move_piece_game_over_blocks_move` — After win/loss/draw, HTTPException(400, "Game is over")
- [ ] `test_move_piece_king_capture_instant_win` — Piece move captures opponent king → immediate game over, no duck phase
- [ ] `test_move_piece_sets_pending_state` — After valid piece move, `sess.pending` = (from, to)
- [ ] `test_move_piece_response_includes_valid_duck_squares` — `validDuck` field populated with legal duck placements
- [ ] `test_move_piece_castling_allowed_under_attack` — White can castle while king under attack (no check in Duck Chess)
- [ ] `test_move_piece_en_passant_if_applicable` — Pawn capture en passant returns correct board state
- [ ] `test_move_piece_promotion_if_pawn_reaches_end` — Pawn to 8th rank → promotion executed (assumed automatic)

### 1.4 Duck Placement & Phase Transition

**Complexity**: High  
**Priority**: Critical

#### Test Cases:
- [ ] `test_place_duck_basic_valid_square` — Valid duck square → updates duck position
- [ ] `test_place_duck_invalid_square_not_in_valid_list` — HTTPException(400, "Illegal duck square")
- [ ] `test_place_duck_invalid_occupied_square` — Duck cannot land on piece-occupied square (caught by action masking)
- [ ] `test_place_duck_cannot_stay_on_current_square` — Duck must move each turn (caught by action masking)
- [ ] `test_place_duck_wrong_phase_not_in_move_duck` — If phase is "move_piece", HTTPException(400, "Not your move-duck phase")
- [ ] `test_place_duck_advances_turn` — After duck placement, `turn` flips (w→b or b→w)
- [ ] `test_place_duck_clears_pending_state` — `sess.pending` = None after duck
- [ ] `test_place_duck_appends_halfmove_history` — Move + duck recorded as single halfmove with duck emoji
- [ ] `test_place_duck_ai_plays_next_turn_if_vs_model` — After player duck placement, model plays full turn (or game ends)
- [ ] `test_place_duck_game_over_blocks` — HTTPException(400, "Game is over") if already finished
- [ ] `test_place_duck_2player_turn_based` — Both players can place duck (turn-based)
- [ ] `test_place_duck_fowling_no_legal_moves` — If player has no legal duck move → instant win for opponent

### 1.5 Legal Moves Query

**Complexity**: Medium  
**Priority**: High

#### Test Cases:
- [ ] `test_legal_moves_returns_valid_targets` — POST `/api/legal-moves` with square holding a piece → array of legal targets
- [ ] `test_legal_moves_empty_no_piece` — Empty square → `{"moves": []}`
- [ ] `test_legal_moves_opponent_piece_in_vs_model` — Player cannot query opponent's piece legal moves
- [ ] `test_legal_moves_wrong_phase_returns_empty` — If not in "move_piece" phase, `moves: []`
- [ ] `test_legal_moves_game_over_returns_empty` — If game over, `moves: []`
- [ ] `test_legal_moves_knight_can_jump_over_duck` — Knight to square behind duck is in move list (duck doesn't block knights)
- [ ] `test_legal_moves_pawn_blocked_by_duck` — Pawn cannot move through/to duck-occupied square
- [ ] `test_legal_moves_respects_pin_mechanics` — If king move would expose to attack, blocked
- [ ] `test_legal_moves_castling_available_if_rights_intact` — Unmoved rook/king → castling in move list
- [ ] `test_legal_moves_castling_unavailable_after_move` — After rook/king move, castling unavailable

### 1.6 Game Termination

**Complexity**: High  
**Priority**: Critical

#### Test Cases:
- [ ] `test_resign_sets_game_over_true` — POST `/api/resign` → `gameOver: true`
- [ ] `test_resign_sets_winner_to_opponent` — Resigner's model/color becomes winner
- [ ] `test_resign_appends_message_field` — Response includes `message: "resign"`
- [ ] `test_king_capture_sets_game_over` — Move capturing king → immediate win, `gameOver: true`, `winner: moving_color`
- [ ] `test_50_move_rule_draw` — 50 moves by each side without capture/pawn move → draw
- [ ] `test_fowling_win_no_legal_moves` — Side with no legal moves wins (Duck Chess inverse stalemate)
- [ ] `test_game_over_blocks_all_actions` — After game over, `/api/move-piece` and `/api/place-duck` return HTTPException(400)

### 1.7 Game Serialization

**Complexity**: Medium  
**Priority**: High

#### Test Cases:
- [ ] `test_serialize_returns_all_required_fields` — Check keys: `board`, `duck`, `turn`, `phase`, `gameOver`, `winner`, `playerColor`, etc.
- [ ] `test_board_to_grid_standard_format` — 8x8 array, pieces as "wP"/"bR"/None
- [ ] `test_captured_lists_correct_counts` — `capturedByWhite` and `capturedByBlack` match pieces removed
- [ ] `test_material_diff_white_ahead` — `evalDiff > 0` when white has more material
- [ ] `test_material_diff_black_ahead` — `evalDiff < 0` when black has more material
- [ ] `test_duck_position_serialization` — Duck at (3, 4) → `duck: [3, 4]`; off-board → `duck: null`

### 1.8 Model vs AI Opponent Logic

**Complexity**: High  
**Priority**: Critical

#### Test Cases:
- [ ] `test_play_model_turn_executes_piece_move` — Model move phase updates board
- [ ] `test_play_model_turn_executes_duck_move` — Model duck phase updates duck position
- [ ] `test_play_model_turn_returns_aiMove_dict` — Response includes piece from/to and duck position
- [ ] `test_play_model_turn_appends_halfmove_history` — Model move recorded in `sess.halfmoves`
- [ ] `test_play_model_turn_respects_action_masks` — Model only selects from legal actions
- [ ] `test_play_model_turn_king_capture_stops_early` — Model captures king → no duck phase, instant win
- [ ] `test_play_model_turn_fowling_stops_early` — Model fowled (no legal move) → instant win
- [ ] `test_play_model_turn_uses_deterministic_mode` — Model calls `predict(..., deterministic=True)`
- [ ] `test_play_model_turn_loop_guards_game_over` — If game_over flag set mid-turn, break out

### 1.9 Threading & Concurrency

**Complexity**: Medium  
**Priority**: Medium

#### Test Cases:
- [ ] `test_session_lock_acquired_during_moves` — All game-modifying endpoints use `with sess.lock`
- [ ] `test_concurrent_moves_same_session_serialized` — Two moves to same game ID processed sequentially
- [ ] `test_concurrent_games_independent` — Moves in game A don't affect game B
- [ ] `test_model_cache_lock_prevents_double_load` — Concurrent new-game calls don't trigger duplicate model loads

---

## 2. Persistence Layer Tests (`test_web_persistence.py`)

### 2.1 Save Game

**Complexity**: Medium  
**Priority**: High

#### Test Cases:
- [ ] `test_save_game_creates_json_file` — POST `/api/save-game` writes to `saved_replays/{username}_{timestamp}.json`
- [ ] `test_save_game_directory_created_if_missing` — `saved_replays/` auto-created if needed
- [ ] `test_save_game_includes_all_fields` — JSON contains: `label`, `username`, `timestamp`, `board`, `duck`, `history`, `board_snapshots`, `game_over`, `winner`
- [ ] `test_save_game_returns_filename` — Response: `{"filename": "...", "message": "..."}` where filename is the saved file
- [ ] `test_save_game_history_with_notation` — `history` includes enhanced `notation` field (e.g., "e2 × e4")
- [ ] `test_save_game_board_snapshots_generated` — `board_snapshots` is array of board states, one per move
- [ ] `test_save_game_game_over_false_for_incomplete` — In-progress game saved with `game_over: false`
- [ ] `test_save_game_invalid_game_id_404` — Unknown game ID → HTTPException(404)
- [ ] `test_save_game_special_characters_in_label` — Unicode label (e.g., "Game™ #1") encoded correctly

### 2.2 List Saved Games

**Complexity**: Medium  
**Priority**: High

#### Test Cases:
- [ ] `test_list_saved_games_returns_user_games_only` — GET `/api/saved-games?username=alice` returns only alice's games
- [ ] `test_list_saved_games_sorted_newest_first` — Most recent saves appear first
- [ ] `test_list_saved_games_empty_list_if_none` — User with no saves → `{"games": []}`
- [ ] `test_list_saved_games_includes_metadata` — Each game has `filename`, `label`, `timestamp`, `model_label`, `result`
- [ ] `test_list_saved_games_result_won_if_winner_matches_player` — Game won by player → `result: "Won"`
- [ ] `test_list_saved_games_result_lost_if_winner_mismatches` — Game won by opponent → `result: "Lost"`
- [ ] `test_list_saved_games_result_in_progress_if_not_over` — Incomplete game → `result: "In Progress"`
- [ ] `test_list_saved_games_skips_corrupt_files` — Malformed JSON files don't crash the endpoint
- [ ] `test_list_saved_games_no_directory_returns_empty` — If `saved_replays/` doesn't exist, return `[]`

### 2.3 Load Game & Replay

**Complexity**: High  
**Priority**: High

#### Test Cases:
- [ ] `test_load_game_returns_full_game_state` — GET `/api/load-game/{filename}` returns all fields
- [ ] `test_load_game_invalid_filename_404` — Unknown filename → HTTPException(404, "Game file not found")
- [ ] `test_load_game_corrupt_json_400` — Malformed JSON → HTTPException(400, "Corrupt game file")
- [ ] `test_load_game_reconstructs_snapshots_if_missing` — Old saves without `board_snapshots` field → snapshots regenerated by replaying moves
- [ ] `test_load_game_snapshot_regeneration_accurate` — Replayed board matches stored final board
- [ ] `test_load_game_snapshot_for_each_move_phase` — `board_snapshots[i]` captures state after i-th move (including intermediate duck phases)
- [ ] `test_load_game_handles_special_move_notation` — Duck emoji (🦆) and @ symbol in move text parsed correctly during replay
- [ ] `test_load_game_malformed_move_text_skipped` — Move with < 4 chars or parsing error doesn't crash

### 2.4 Board Snapshot Generation

**Complexity**: High  
**Priority**: High

#### Test Cases:
- [ ] `test_generate_board_snapshots_empty_game` — Game with no moves → snapshots = [initial_board]
- [ ] `test_generate_board_snapshots_single_move` — 1 move (piece + duck) → 3 snapshots (start, after piece, after duck)
- [ ] `test_generate_board_snapshots_multiple_turns` — Each full turn adds 2 snapshots
- [ ] `test_generate_board_snapshots_king_capture_early_exit` — Move with "#" suffix (king capture) → snapshot count matches move count
- [ ] `test_generate_board_snapshots_handles_en_passant` — En passant move replayed correctly in snapshots
- [ ] `test_generate_board_snapshots_algebraic_parsing` — Notation "e2e4" correctly parsed to row/col coordinates

---

## 3. Frontend Integration Tests (`test_web_frontend.js` or Playwright/Cypress)

### 3.1 Authentication & Navigation

**Complexity**: Low  
**Priority**: Medium

#### Test Cases (E2E):
- [ ] User enters username → stored in `curUsername` global
- [ ] Login tab active by default, Register hidden
- [ ] Click Register tab → "Confirm password" field appears
- [ ] Enter any username → can proceed (open auth, no backend validation)
- [ ] Splash screen fades after 1.5s
- [ ] After auth, screen switches to menu

### 3.2 Game Initialization

**Complexity**: Medium  
**Priority**: High

#### Test Cases (E2E):
- [ ] Model dropdown populates from `/api/models` on page load
- [ ] "Play as White" card calls `/api/new-game` with `color: "white"`, `model: selected`
- [ ] "Play as Black" card calls `/api/new-game` with `color: "black"`, `model: selected`
- [ ] "2 Players" card calls `/api/new-game` with `model: null`
- [ ] Game screen appears after new-game response
- [ ] Board flips when player is black (flipped=true)
- [ ] Player/opponent names displayed correctly per mode (username vs Duck PPO vs Player 2)

### 3.3 Board Rendering & Interaction

**Complexity**: High  
**Priority**: Critical

#### Test Cases (E2E):
- [ ] All 64 squares render with correct colors (light/dark alternating)
- [ ] Chess pieces display as correct SVG images from Wikimedia
- [ ] Standard starting position pieces placed correctly
- [ ] Duck displays at initial position (off-board, no rendering)
- [ ] Click on friendly piece → legal move targets highlight (orange dots for empty, red boxes for captures)
- [ ] Click on legal target → piece moves via `/api/move-piece`
- [ ] Board updates after move response
- [ ] Board flips when "Flip" button clicked
- [ ] Coordinates display on edges (a-h, 1-8), flip with board

### 3.4 Move Execution & Validation Feedback

**Complexity**: High  
**Priority**: Critical

#### Test Cases (E2E):
- [ ] Illegal move (e.g., pawn backward) → red flash on target square + error toast
- [ ] Piece move after game over → board locked (no click response)
- [ ] After piece move, phase pill shows "🦆 Move duck"
- [ ] Valid duck squares show circles (duckable class)
- [ ] Click invalid duck square → red flash + error toast, awaiting duck state remains
- [ ] Click valid duck square → board updates, turn advances
- [ ] Keyboard shortcut 'F' toggles flip
- [ ] Keyboard shortcut 'R' triggers resign confirmation

### 3.5 Move History Display

**Complexity**: Medium  
**Priority**: High

#### Test Cases (E2E):
- [ ] Move history empty at start: "No moves yet."
- [ ] After first move, history shows "1. e2e4 ..."
- [ ] History pairs white and black moves on same line (e.g., "1. e2e4 e7e5")
- [ ] Duck moves shown with emoji: "1. e2e4 🦆e4"
- [ ] History auto-scrolls to latest move
- [ ] Move numbers increment correctly per full turn

### 3.6 Captured Pieces Display

**Complexity**: Medium  
**Priority**: Medium

#### Test Cases (E2E):
- [ ] Left sidebar shows "Captured by White" and "Captured by Black"
- [ ] At start, both empty ("none")
- [ ] After white captures black pawn, bP appears in white's captured list
- [ ] Material diff shown as "+1" for white side
- [ ] Captured pieces displayed as small SVG images in correct order (Q, R, B, N, P)

### 3.7 Evaluation & Turn Status

**Complexity**: Medium  
**Priority**: Medium

#### Test Cases (E2E):
- [ ] Eval bar shows material advantage
- [ ] "White advantage" / "Black advantage" label matches fill direction
- [ ] Eval score shows "+3" for white ahead, "-2" for black ahead
- [ ] Turn indicator pulses during model thinking
- [ ] Turn text shows "Your move" vs "Model thinking…"
- [ ] Phase pill shows "♟ Move piece" or "🦆 Move duck"
- [ ] Player cards highlight current player (active/inactive styling)

### 3.8 Game Over Modal

**Complexity**: Medium  
**Priority**: High

#### Test Cases (E2E):
- [ ] King capture by player → modal shows "You Win! 🎉" (gold)
- [ ] King capture by opponent → modal shows "You Lost" (red)
- [ ] Resign by player → modal shows "You Lost" with "Opponent resigned" reason
- [ ] 50-move draw → modal shows "Draw" (blue)
- [ ] "New Game" button restarts with same settings
- [ ] "Menu" button returns to home screen
- [ ] "Save" button visible and clickable

### 3.9 Save & Load Games

**Complexity**: High  
**Priority**: High

#### Test Cases (E2E):
- [ ] Click "Save" in game-over modal → prompt for game name
- [ ] Save button transitions to "⏳ Saving..." during request
- [ ] On success: "✅ Saved!" + toast "Game saved! You can load it…"
- [ ] On failure: "❌ Save failed" + "Retry" button
- [ ] Saved games appear in menu's "Saved Games" section
- [ ] Each card shows: game label, timestamp, result (Won/Lost/In Progress), model name
- [ ] Click "Load & Review" → board displays final position, replay controls appear
- [ ] Replay mode locks board (no moves allowed), shows move counter

### 3.10 Replay Mode

**Complexity**: High  
**Priority**: High

#### Test Cases (E2E):
- [ ] Replay controls appear at bottom: "⏮ Prev", "▶ Play", "Next ⏭", "Exit ✕"
- [ ] "Prev" button steps backward through board snapshots
- [ ] "Next" button steps forward through snapshots
- [ ] "Play" starts auto-stepping at 1.5s intervals
- [ ] "Pause" pauses playback
- [ ] Move counter shows "Move: 1/25" (current/total)
- [ ] Exit replay returns to menu
- [ ] Board in replay mode is locked (no clicks processed)
- [ ] History highlights the current move

---

## 4. Game Logic Integration Tests (`test_web_logic_bridge.py`)

### 4.1 Action Masking

**Complexity**: High  
**Priority**: Critical

#### Test Cases:
- [ ] `test_valid_duck_squares_respects_action_masks` — `valid_duck_squares()` returns only mask-legal squares
- [ ] `test_valid_duck_squares_excludes_occupied` — Squares with pieces excluded (caught by mask)
- [ ] `test_valid_duck_squares_excludes_current_duck_pos` — Duck cannot stay in place (caught by mask)
- [ ] `test_valid_duck_squares_empty_list_if_no_moves` — Fowled position → empty list
- [ ] `test_action_mask_shape_4096` — Masks are 4096-element boolean arrays (64×64 from/to)

### 4.2 Observation Encoding

**Complexity**: Medium  
**Priority**: Medium

#### Test Cases:
- [ ] `test_observation_19_channels` — `_get_obs()` returns shape (19, 8, 8) or flattened equivalent
- [ ] `test_observation_piece_planes` — Channels 0-11 encode white/black pieces (P, N, B, R, Q, K)
- [ ] `test_observation_duck_plane` — Channel 12 encodes duck position
- [ ] `test_observation_metadata_planes` — Channels 13-18 encode en passant, castling, turn, phase
- [ ] `test_observation_after_move_updates` — Board state change reflected in next observation

### 4.3 Move Encoding & Decoding

**Complexity**: Medium  
**Priority**: High

#### Test Cases:
- [ ] `test_decode_move_action_0_to_0` — Action 0 → from (0,0), to (0,0)
- [ ] `test_decode_move_action_4095_to_63_63` — Action 4095 → from (7,7), to (7,7) (last square)
- [ ] `test_decode_move_piece_phase` — During move_piece phase, decodes piece move
- [ ] `test_decode_move_duck_phase` — During move_duck phase, decodes duck placement (dummy from, real to)
- [ ] `test_move_encoding_consistent` — Same action always decodes to same coordinates

### 4.4 Turn & Phase Management

**Complexity**: Medium  
**Priority**: High

#### Test Cases:
- [ ] `test_turn_advances_after_duck_phase` — After place_duck(), engine.turn flips
- [ ] `test_phase_cycles_move_piece_move_duck` — After execute_move(), phase = "move_duck"
- [ ] `test_phase_cycles_move_duck_move_piece` — After place_duck(), phase = "move_piece"
- [ ] `test_game_over_flag_set_on_king_capture` — execute_move capturing king → game_over = True
- [ ] `test_winner_field_set_on_termination` — game_over = True implies winner is set

### 4.5 Duck Blocking Rules

**Complexity**: High  
**Priority**: Critical

#### Test Cases:
- [ ] `test_duck_blocks_all_pieces_except_knights` — Pawn, rook, bishop, queen, king cannot move through duck
- [ ] `test_knights_jump_over_duck` — Knight L-move over duck is legal (if destination not duck)
- [ ] `test_knights_cannot_land_on_duck` — Knight cannot land on duck square (no piece can)
- [ ] `test_duck_blocks_castling_if_in_path` — Rook to king path blocked by duck → no castling
- [ ] `test_duck_blocks_pawn_capture_if_on_target` — Pawn capture diagonal blocked if duck on target

---

## 5. Error Handling & Edge Cases (`test_web_edge_cases.py`)

### 5.1 Malformed Requests

**Complexity**: Low  
**Priority**: Medium

#### Test Cases:
- [ ] `test_move_piece_missing_frm_field` — HTTPException(422) or validation error
- [ ] `test_move_piece_wrong_type_r_c` — Pass string "a" instead of int → validation error
- [ ] `test_place_duck_out_of_bounds_row` — Row > 7 → HTTPException(400)
- [ ] `test_place_duck_out_of_bounds_col` — Col < 0 → HTTPException(400)
- [ ] `test_new_game_invalid_color` — color="red" → falls back to default or error
- [ ] `test_new_game_invalid_model` — model="nonexistent" → uses first available

### 5.2 State Desynchronization

**Complexity**: High  
**Priority**: High

#### Test Cases:
- [ ] `test_move_piece_while_awaiting_duck` — POST `/api/move-piece` during duck phase → HTTPException
- [ ] `test_place_duck_while_in_move_piece_phase` — POST `/api/place-duck` while phase is "move_piece" → HTTPException
- [ ] `test_move_piece_missing_pending_state` — If sess.pending is None but in duck phase somehow → handle gracefully (default (0,0))
- [ ] `test_double_move_piece_same_square` — Two consecutive move-piece calls without duck placement → error on second

### 5.3 Concurrent Access Edge Cases

**Complexity**: High  
**Priority**: Medium

#### Test Cases:
- [ ] `test_move_and_resign_race_condition` — Move and resign both in flight → one succeeds, other gets "Game over"
- [ ] `test_load_same_model_concurrent_new_games` — 3 parallel new-game calls with same model → load once, cache hit 2x
- [ ] `test_session_cleanup_after_resignation` — Resigned session can still be queried (remains in memory)

### 5.4 Board State Invariants

**Complexity**: Medium  
**Priority**: High

#### Test Cases:
- [ ] `test_board_always_16_pieces_total` — After any move, count pieces (should be ≤ 16 per side)
- [ ] `test_both_kings_present_until_capture` — If game not over, both sides have king
- [ ] `test_duck_at_most_one` — At most one duck on board (actually always exactly one after move 1)
- [ ] `test_no_pawns_on_end_ranks` — After move, no pawn on rank 8 or rank 1 (promotion enforced)

### 5.5 Special Moves

**Complexity**: High  
**Priority**: Medium

#### Test Cases:
- [ ] `test_en_passant_capture_in_web_api` — Pawn 1 square past on 5th rank, opponent pawn 2-square move → en passant legal
- [ ] `test_en_passant_removes_passing_pawn` — After en passant, pawn removed from correct square
- [ ] `test_castling_kingside_white` — e1g1 with unmoved king/rook → castling executed
- [ ] `test_castling_queenside_black` — e8c8 with unmoved king/rook → castling executed
- [ ] `test_castling_rights_lost_after_king_move` — King moves e1d1 → castling no longer available
- [ ] `test_castling_rights_lost_after_rook_move` — Rook moves a1a2 → queenside castling unavailable
- [ ] `test_pawn_promotion_automatic` — Pawn to 8th rank → auto-promotes to queen (or configurable)

---

## 6. Performance & Load Tests (`test_web_performance.py`)

### 6.1 Response Time Baselines

**Complexity**: Low  
**Priority**: Low

#### Test Cases:
- [ ] `test_list_models_latency_< 10ms` — Model listing cached, should be instant
- [ ] `test_move_piece_latency_< 50ms` — Move validation fast
- [ ] `test_place_duck_latency_< 500ms` — Duck validation + optional AI move (if AI is fast)
- [ ] `test_model_first_load_latency_< 2s` — First model load (cold cache) takes < 2 seconds
- [ ] `test_model_subsequent_load_latency_< 1ms` — Cached model retrieval near-instant

### 6.2 Memory & Resource Management

**Complexity**: Medium  
**Priority**: Low

#### Test Cases:
- [ ] `test_model_cache_max_size` — At most N models in memory (prevent unbounded growth)
- [ ] `test_session_cleanup_old_games` — Sessions older than X minutes can be purged (optional: implement)
- [ ] `test_large_game_history_serialization` — 100+ moves serializes without OOM
- [ ] `test_concurrent_games_no_memory_leak` — 50 simultaneous games don't leak memory

### 6.3 Board Snapshot Generation Stress

**Complexity**: Medium  
**Priority**: Low

#### Test Cases:
- [ ] `test_snapshot_generation_50_moves` — Generating 100 snapshots (50 turns) completes in < 1s
- [ ] `test_snapshot_reconstruction_accuracy_100_moves` — Replaying 100 moves produces identical final board

---

## 7. Infrastructure & Deployment Tests

### 7.1 Static File Serving

**Complexity**: Low  
**Priority**: Medium

#### Test Cases:
- [ ] GET `/` serves `index.html` (FastAPI `html=True` mode)
- [ ] GET `/duck.png` serves image asset
- [ ] GET `/api/*` routes take precedence over static (routing order correct)

### 7.2 CORS & Headers

**Complexity**: Low  
**Priority**: Low

#### Test Cases:
- [ ] POST requests from browser origin accepted (no CORS blocking)
- [ ] JSON response headers correct (`Content-Type: application/json`)
- [ ] 404 responses have proper status and body

---

## Test Implementation Strategy

### Tools & Frameworks

**Backend (Python)**:
- **pytest** — main test runner (already configured in `pytest.ini`)
- **pytest-asyncio** — for async FastAPI tests
- **fastapi.testclient** — HTTP client for API routes
- **unittest.mock** — mock `_HeadlessEngine`, `MaskablePPO` for isolation
- **tmp_path** (pytest fixture) — temporary directories for save/load tests

**Frontend (JavaScript, Optional)**:
- **Playwright** or **Cypress** — E2E browser automation
- **Jest** + jsdom — unit tests for pure JS functions (if refactored into modules)
- Manual testing with browser DevTools for first pass

### Execution Plan

**Phase 1 (Weeks 1-2): Backend Unit & Integration**
1. Set up `test_web_server.py` with fixtures for mock engine, game sessions
2. Test model management, session lifecycle, move validation
3. Add threading/concurrency tests

**Phase 2 (Weeks 2-3): Persistence & Edge Cases**
1. Implement `test_web_persistence.py` for save/load
2. Test snapshot generation and replay
3. Add malformed request and state desync tests

**Phase 3 (Week 3-4): Frontend E2E**
1. Set up Playwright environment
2. Write smoke tests for critical user flows (new game → move → save)
3. Add detailed interaction tests (click handling, board rendering)

**Phase 4 (Ongoing): Performance & Regression**
1. Baseline response times
2. Load test with concurrent sessions
3. CI integration (run tests on PR)

---

## Test Coverage Targets

| Component | Target Coverage | Priority |
|-----------|-----------------|----------|
| `server.py` — API endpoints | 85%+ | Critical |
| `server.py` — Game logic | 80%+ | Critical |
| `server.py` — Persistence | 90%+ | High |
| Frontend — Board interaction | Manual + E2E | High |
| Frontend — Replay | E2E only | Medium |
| Integration (API ↔ Engine) | 75%+ | Critical |

---

## Known Risks & Gaps

1. **Model Integration**: Tests mock or use lightweight models; full end-to-end with real stage-12 model deferred
2. **Browser Compatibility**: E2E tests should run on Chrome/Firefox/Safari; initially Chrome-only acceptable
3. **Save/Load Reliability**: File I/O assumes writable `saved_replays/` directory; test failure isolation needed
4. **Replay Accuracy**: Board snapshot replay depends on move parsing; hand-craft test cases with known move histories
5. **Concurrency Race Conditions**: Threading bugs may only surface under load; stress tests recommended

---

## Deliverables

1. **`test_web_server.py`** — 60+ test cases covering API, sessions, moves, AI
2. **`test_web_persistence.py`** — 20+ test cases covering save/load/replay
3. **`test_web_edge_cases.py`** — 15+ test cases covering error handling
4. **`test_web_frontend.html`** — Playwright/Cypress spec file (optional phase 3)
5. **`WEB_UI_TEST_PLAN.md`** (this document) — comprehensive reference

---

## Success Criteria

- All backend tests pass with pytest
- Coverage ≥ 80% on `server.py` (excluding static serving)
- Frontend smoke tests (new game → move → save) pass 5/5 times
- No model crashes on invalid input
- Save/load roundtrip produces byte-identical JSON (except timestamps)
- Concurrent 10-game stress test completes without errors
