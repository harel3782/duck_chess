import random
from settings import *


class DuckAI:
    def __init__(self, depth=1):
        self.depth = depth  # Use this later for Minimax depth

    def get_piece_move(self, board, turn_color, legal_moves_generator):
        """
        Decides which piece to move.
        :param board: The current 8x8 board array
        :param turn_color: 'w' or 'b'
        :param legal_moves_generator: A function (r, c) -> list of moves
        :return: Tuple ((start_r, start_c), (end_r, end_c)) or None
        """
        all_moves = []

        # 1. Find all possible moves
        for r in range(8):
            for c in range(8):
                p = board[r][c]
                if p and p.color == turn_color:
                    valid_destinations = legal_moves_generator(r, c)
                    for dest in valid_destinations:
                        all_moves.append(((r, c), dest))

        if not all_moves:
            return None

        # --- REPLACE THIS BLOCK WITH YOUR SMART AI LOGIC LATER ---
        # Currently: Random Choice
        chosen_move = random.choice(all_moves)
        return chosen_move
        # ---------------------------------------------------------

    def get_duck_move(self, board, current_duck_pos, prev_duck_pos):
        """
        Decides where to place the duck.
        :param board: The current 8x8 board array
        :param current_duck_pos: (r, c) tuple
        :param prev_duck_pos: (r, c) tuple (cannot place here)
        :return: (r, c) tuple
        """
        empties = [(r, c) for r in range(8) for c in range(8) if not board[r][c]]

        # Filter out the square the duck was just on (illegal in Duck Chess)
        valid_squares = [pos for pos in empties if pos != prev_duck_pos]

        if not valid_squares:
            # Fallback if board is full (rare)
            return random.choice(empties) if empties else None

        # --- REPLACE THIS BLOCK WITH YOUR SMART AI LOGIC LATER ---
        # Currently: Random Choice
        return random.choice(valid_squares)
        # ---------------------------------------------------------