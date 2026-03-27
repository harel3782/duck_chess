# --- RL ENVIRONMENT HELPERS ---
def _get_obs(self):
    """
    Converts the current board state into an 19x8x8 Observation Tensor for the RL Model.
    Channels 0-5: White pieces (P, N, B, R, Q, K)
    Channels 6-11: Black pieces
    Channel 12: Duck position
    Channel 13: En Passant target
    Channel 14: Turn (1.0 for White, 0.0 for Black)
    Channels 15-18: Castling rights (White King, White Queen, Black King, Black Queen)
    """
    obs = np.zeros((19, 8, 8), dtype=np.float32)

    piece_to_channel = {
        'w': {PAWN: 0, KNIGHT: 1, BISHOP: 2, ROOK: 3, QUEEN: 4, KING: 5},
        'b': {PAWN: 6, KNIGHT: 7, BISHOP: 8, ROOK: 9, QUEEN: 10, KING: 11}
    }

    wk_pos = None
    bk_pos = None

    # 1. Fill piece layers
    for r in range(8):
        for c in range(8):
            p = self.board[r][c]
            if p:
                channel = piece_to_channel[p.color][p.type]
                obs[channel][r][c] = 1.0

                if p.type == KING:
                    if p.color == 'w':
                        wk_pos = (r, c)
                    else:
                        bk_pos = (r, c)

    # 2. Duck position
    if self.duck_pos != (-1, -1):
        dr, dc = self.duck_pos
        obs[12][dr][dc] = 1.0

    # 3. En Passant target
    if self.en_passant_target:
        er, ec = self.en_passant_target
        obs[13][er][ec] = 1.0

    # 4. Turn
    if self.turn == 'w':
        obs[14].fill(1.0)

    # 5. Castling rights
    if wk_pos and not self.board[wk_pos[0]][wk_pos[1]].has_moved:
        if self.can_castle(wk_pos[0], wk_pos[1], True):
            obs[15].fill(1.0)
        if self.can_castle(wk_pos[0], wk_pos[1], False):
            obs[16].fill(1.0)

    if bk_pos and not self.board[bk_pos[0]][bk_pos[1]].has_moved:
        if self.can_castle(bk_pos[0], bk_pos[1], True):
            obs[17].fill(1.0)
        if self.can_castle(bk_pos[0], bk_pos[1], False):
            obs[18].fill(1.0)

    return obs
# --- RL ACTION SPACE HELPERS ---


def _encode_move(self, start, end):
    """Converts a move from coordinates to a flat index (0-4095)"""
    start_idx = start[0] * 8 + start[1]
    end_idx = end[0] * 8 + end[1]
    return start_idx * 64 + end_idx


def _decode_move(self, action):
    """Converts a flat index back to coordinates ((sr, sc), (er, ec))"""
    start_idx = action // 64
    end_idx = action % 64
    sr, sc = start_idx // 8, start_idx % 8
    er, ec = end_idx // 8, end_idx % 8
    return (sr, sc), (er, ec)


def action_masks(self):
    """
    Returns a boolean mask of size 4096.
    True means the action is legal in the current phase.
    """
    masks = np.zeros(4096, dtype=bool)

    if self.phase == 'move_piece':
        # Phase 1: Moving a piece
        for r in range(8):
            for c in range(8):
                p = self.board[r][c]
                if p and p.color == self.turn:
                    valid_moves = self.get_piece_legal_moves(r, c)
                    for end_pos in valid_moves:
                        action_idx = self._encode_move((r, c), end_pos)
                        masks[action_idx] = True

    elif self.phase == 'move_duck':
        # Phase 2: Placing the duck
        # We arbitrarily use start=(0,0) to keep the action within the 4096 range
        for r in range(8):
            for c in range(8):
                if not self.board[r][c] and (r, c) != self.prev_duck_pos:
                    action_idx = self._encode_move((0, 0), (r, c))
                    masks[action_idx] = True
    return masks


def debug_print_observation(self):
    """
    Helper function to print the 19x8x8 observation tensor in a human-readable format.
    It scans the tensor and prints only the active bits (1.0).
    """
    obs = self._get_obs()

    # Map channel indices to readable names
    channel_names = {
        0: "White Pawns", 1: "White Knights", 2: "White Bishops",
        3: "White Rooks", 4: "White Queens", 5: "White King",
        6: "Black Pawns", 7: "Black Knights", 8: "Black Bishops",
        9: "Black Rooks", 10: "Black Queens", 11: "Black King",
        12: "Duck Position", 13: "En Passant Target"
    }

    print("\n" + "=" * 40)
    print("OBSERVATION TENSOR STATE")
    print("=" * 40)

    # 1. Print piece positions and board targets (Channels 0-13)
    for channel in range(14):
        active_squares = []
        for r in range(8):
            for c in range(8):
                if obs[channel][r][c] == 1.0:
                    # Convert (r, c) to chess notation like 'e2'
                    coords = self.get_notation_coords(r, c)
                    active_squares.append(coords)

        # Only print channels that actually have active bits
        if active_squares:
            print(f"[{channel}] {channel_names[channel]:<18}: {', '.join(active_squares)}")

    # 2. Print global state variables (Channels 14-18)
    print("-" * 40)
    # Turn plane is entirely 1.0 if white, 0.0 if black
    current_turn = "White" if obs[14][0][0] == 1.0 else "Black"
    print(f"[14] Turn               : {current_turn}")

    # Castling planes
    print(f"[15] White Castling KS  : {'Yes' if obs[15][0][0] == 1.0 else 'No'}")
    print(f"[16] White Castling QS  : {'Yes' if obs[16][0][0] == 1.0 else 'No'}")
    print(f"[17] Black Castling KS  : {'Yes' if obs[17][0][0] == 1.0 else 'No'}")
    print(f"[18] Black Castling QS  : {'Yes' if obs[18][0][0] == 1.0 else 'No'}")
    print("=" * 40 + "\n")