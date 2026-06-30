import random

# Baseline alpha-beta/random AI opponent for the desktop game (no learned model).
class DuckAI:
    # Store search depth (currently unused; reserved for future minimax).
    def __init__(self, depth=2):
        self.depth = depth
        # TODO: Initialize Bitboards here for the CS Project optimization

    def get_piece_move(self, board, turn_color, legal_moves_generator):
        """
        Decides which piece to move.
        Input: 2D Array Board
        Output: Tuple ((start_r, start_c), (end_r, end_c))
        """
        all_moves = []

        # 1. Generate all possible moves for the AI
        # (Later, we will replace this loop with Bitboard generation)
        # Scan every square; collect (start, dest) for each of our pieces' legal moves.
        for r in range(8):
            for c in range(8):
                p = board[r][c]
                if p and p.color == turn_color:
                    valid_destinations = legal_moves_generator(r, c)
                    for dest in valid_destinations:
                        all_moves.append(((r, c), dest))

        # No legal piece moves -> caller handles (in Duck Chess, no moves = fowling win).
        if not all_moves:
            return None

        # --- AI DECISION LOGIC ---
        # Current: Random (Baseline)
        # TODO: Implement Minimax / Alpha-Beta Pruning here
        chosen_move = random.choice(all_moves)

        return chosen_move

    def get_duck_move(self, board, current_duck_pos, prev_duck_pos):
        """
        Decides where to place the duck.
        Output: Tuple (r, c)
        """
        # Collect every unoccupied square as a duck-placement candidate.
        empties = []
        for r in range(8):
            for c in range(8):
                if not board[r][c]:
                    empties.append((r, c))

        # Filter out the square the duck was just on (duck may not stay put).
        valid_squares = [pos for pos in empties if pos != prev_duck_pos]

        if not valid_squares:
            return None

        # Current: Random placement
        # TODO: Heuristic - Place duck to block enemy sliding pieces?
        return random.choice(valid_squares)