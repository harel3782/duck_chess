import gymnasium as gym
import numpy as np
from gymnasium import spaces
import sys
import os
import pickle
import time
import random

# Add the root directory to sys.path so we can import the game logic
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from DuckChess_Game.Logic.logic import GameLogicMixin


class DuckChessEnv(gym.Env, GameLogicMixin):
    """
    Headless RL Environment for Duck Chess compatible with Stable Baselines3.
    The RL Agent plays WHITE. The Environment simulates BLACK randomly.
    """

    def __init__(self):
        super().__init__()

        self.action_space = spaces.Discrete(4096)
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(19, 8, 8), dtype=np.float32)
        self.game_mode = 'rl_training'

        self.episode_counter = 0
        self.replays_dir = "saved_replays"
        os.makedirs(self.replays_dir, exist_ok=True)

        self.reset()

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)

        self.board = [[None] * 8 for _ in range(8)]
        self.duck_pos = (-1, -1)
        self.prev_duck_pos = (-1, -1)
        self.turn = 'w'
        self.phase = 'move_piece'
        self.game_over = False
        self.winner = None
        self.en_passant_target = None
        self.half_move_clock = 0
        self.rep_history = {}
        self.turn_number = 1

        self.move_log = []
        self.history = []
        self.view_index = -1
        self.last_move_arrow = None
        self.captured = {'w': [], 'b': []}
        self.promotion_pending = False
        self.current_move_str = ""

        self.action_history = []

        self.init_board()

        return self._get_obs(), {}

    def save_snapshot(self):
        pass

    def _save_binary_replay(self):
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(self.replays_dir, f"game_{self.episode_counter}_{timestamp}.pkl")

        game_data = {
            'episode': self.episode_counter,
            'winner': self.winner,
            'move_log': self.move_log,
            'action_history': self.action_history
        }

        with open(filename, 'wb') as f:
            pickle.dump(game_data, f)

    def _play_random_opponent_turn(self):
        """
        Simulates a complete turn (Piece Move + Duck Place) for the Black opponent.
        """
        if self.game_over or self.turn != 'b':
            return

        # 1. Opponent Piece Move
        valid_piece_moves = []
        for r in range(8):
            for c in range(8):
                p = self.board[r][c]
                if p and p.color == 'b':
                    moves = self.get_piece_legal_moves(r, c)
                    for dest in moves:
                        valid_piece_moves.append(((r, c), dest))

        if valid_piece_moves:
            chosen_move = random.choice(valid_piece_moves)
            # We must save the opponent's action to the history so the GUI replay viewer won't crash
            action_idx = self._encode_move(chosen_move[0], chosen_move[1])
            self.action_history.append(action_idx)

            self.execute_move(chosen_move[0], chosen_move[1], animated=False)
            self.check_game_end_conditions()

        if self.game_over: return

        # 2. Opponent Duck Placement
        valid_duck_moves = []
        for r in range(8):
            for c in range(8):
                if not self.board[r][c] and (r, c) != self.prev_duck_pos:
                    valid_duck_moves.append((r, c))

        if valid_duck_moves:
            chosen_duck = random.choice(valid_duck_moves)

            # Save opponent duck action
            action_idx = self._encode_move((0, 0), chosen_duck)
            self.action_history.append(action_idx)

            self.place_duck(chosen_duck, animated=False)
            self.check_game_end_conditions()

    def step(self, action):
        self.action_history.append(action)
        reward = -0.001  # Small step penalty to encourage fast wins
        terminated = False
        truncated = False
        info = {}

        # 1. AGENT'S TURN (WHITE)
        (sr, sc), (er, ec) = self._decode_move(action)

        if self.phase == 'move_piece':
            self.execute_move((sr, sc), (er, ec), animated=False)
        elif self.phase == 'move_duck':
            self.place_duck((er, ec), animated=False)

        self.check_game_end_conditions()

        # 2. OPPONENT'S TURN (BLACK) - Triggered only if the Agent just placed a duck
        if not self.game_over and self.turn == 'b':
            self._play_random_opponent_turn()

        # 3. EVALUATE REWARD
        if self.game_over:
            terminated = True
            self.episode_counter += 1

            if self.winner == 'w':  # Agent won!
                reward = 1.0
            elif self.winner == 'b':  # Agent lost to the random bot
                reward = -1.0
            else:  # Draw
                reward = -0.1

            if self.episode_counter % 5 == 0:
                self._save_binary_replay()

        return self._get_obs(), reward, terminated, truncated, info

    def get_action_masks(self):
        return self.action_masks()