import gymnasium as gym
import numpy as np
from gymnasium import spaces
import torch as th
import pickle
import time
import os
import uuid

from DuckChess_Game.Logic.logic import GameLogicMixin
from DuckChess_Game.Logic.rules_checker import RulesChecker
from DuckChess_Game.Logic.constants import KING, PIECE_VALUES
from DuckChess_Game.playwright_game.New.peter_interface import PeterSiteConnector

class HeadlessEngine(GameLogicMixin):
    """A lightweight version of the game strictly for fast RL training."""
    def __init__(self):
        self.game_mode = 'rl_training'
        self.reset_game_state()

class DuckPeterEnv(gym.Env):
    """
    Environment wrapper for live testing/training against Peter's Duck Chess website.
    Delegates all opponent interactions and physical executions to an external handler.
    """
    def __init__(self, render_mode=None):
        super(DuckPeterEnv, self).__init__()
        self.action_space = spaces.Discrete(4096)
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(19, 8, 8), dtype=np.float32)
        self.render_mode = render_mode
        
        # The external controller handling the physical interactions
        self.connector = PeterSiteConnector()
        
        self.engine = HeadlessEngine()
        self.episode_counter = 0
        self.current_episode_actions = []
        
        self.learning_color = 'w'
        self.opponent_color = 'b'
        
        # Strategic Scaling Factors (Mirrored from Stage 10)
        self.material_scale = 0.05
        self.loss_penalty_multiplier = 1.2
        self.castling_bonus = 0.15
        self.defense_bonus = 0.02
        self.duck_blocking_scale = 0.01
        self.step_penalty = -0.007
        self.mobility_scale = 0.003
        
        # Endgame specific parameters
        self.endgame_material_threshold = 5.0
        self.king_push_bonus = 0.05
        
        self.checker = RulesChecker()
        self.tactical_values = PIECE_VALUES.copy()
        self.tactical_values[KING] = 10000

    def _calculate_mobility(self, color):
        """Counts total reachable squares for all pieces of a color."""
        controlled_squares = 0
        board = self.engine.board
        for r in range(8):
            for c in range(8):
                p = board[r][c]
                if p and p.color == color:
                    moves = self.engine.get_piece_legal_moves(r, c)
                    controlled_squares += len(moves)
        return controlled_squares

    def _count_threats(self, color):
        """Checks if the King is in check."""
        if self.checker.is_in_check(color, self.engine.board, self.engine.duck_pos):
            return 1
        return 0

    def _find_king(self, color):
        """Locates the coordinates of the king for a specific color."""
        board = self.engine.board
        for r in range(8):
            for c in range(8):
                p = board[r][c]
                if p and p.type == KING and p.color == color:
                    return (r, c)
        return None

    def _center_distance(self, pos):
        """Calculates the Chebyshev distance from the center of the board."""
        r, c = pos
        return max(abs(r - 3.5), abs(c - 3.5))

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        # init_board() also detects the site's flip state and rebuilds the
        # square map, so all pixel<->square translation below is orientation-safe.
        self.connector.init_board()

        self.engine.reset_game_state()
        self.current_episode_actions = []
        self.episode_counter += 1

        # Color (FEN side-to-move) is independent of the board's visual flip:
        # White always moves first; flipping only changes which side is drawn at
        # the bottom. learning_color drives the FEN turn and the reward sign.
        if options and 'learning_color' in options:
            self.learning_color = options['learning_color']
        else:
            self.learning_color = np.random.choice(['w', 'b'])
        self.opponent_color = 'b' if self.learning_color == 'w' else 'w'

        print(f"[RESET] Model={'WHITE' if self.learning_color == 'w' else 'BLACK'} "
              f"| Peter={'WHITE' if self.opponent_color == 'w' else 'BLACK'} "
              f"| board_flipped={self.connector.flipped}")

        # If the model is Black, White (Peter) moves first on the website.
        if self.learning_color == 'b':
            self._play_external_opponent_turn()

        return self.get_observation(), {}

    def get_observation(self):
        return self.engine._get_obs()

    def action_masks(self):
        masks = self.engine.action_masks()
        if not np.any(masks):
            masks[0] = True
            return masks

        if getattr(self.engine, 'phase', '') == 'move_piece':
            forced_mask = np.zeros(4096, dtype=bool)
            found_king_capture = False
            board = self.engine.board
            
            for action in np.where(masks)[0]:
                _, end = self.engine._decode_move(action)
                target = board[end[0]][end[1]]
                if target and target.type == KING and target.color != self.engine.turn:
                    forced_mask[action] = True
                    found_king_capture = True
                    
            if found_king_capture:
                return forced_mask
        return masks

    def step(self, action):
        self.engine.bb_mgr.print_current_state()
        print(f"Phase before: {self.engine.phase}")
        try:
            if not np.any(self.action_masks()):
                return self.get_observation(), 0.0, True, False, {}
                
            threats_before = self._count_threats(self.learning_color)
            material_before_abs = self.engine.calculate_material_score(self.engine.board)
            
            mobility_before = 0
            opp_mob_before = 0
            opp_king_before = None
            
            # Cache phase state before execution
            current_phase = getattr(self.engine, 'phase', 'move_piece')
            
            if current_phase == 'move_piece':
                mobility_before = self._calculate_mobility(self.learning_color)
                opp_king_before = self._find_king(self.opponent_color)
            elif current_phase == 'move_duck':
                opp_mob_before = self._calculate_mobility(self.opponent_color)

            pos_bonus = 0
            if current_phase == 'move_piece':
                start, end = self.engine._decode_move(action)
                p = self.engine.board[start[0]][start[1]]
                if p and p.type == KING and abs(start[1] - end[1]) == 2:
                    pos_bonus = self.castling_bonus

            # 1. Apply action internally to update internal board map
            self._apply_action(action)
            self.current_episode_actions.append(int(action))

            # 2. Replicate the action physically on Peter's website
            if self.connector:
                self.connector.send_action_to_site(action, current_phase)

            rewards = {"material": 0, "pos": pos_bonus, "defense": 0, "blocking": 0, "mobility": 0, "endgame_push": 0}
            dynamic_step_penalty = self.step_penalty
            
            material_after_abs = self.engine.calculate_material_score(self.engine.board)
            my_adv = material_after_abs if self.learning_color == 'w' else -material_after_abs
            
            if self.engine.phase == 'move_piece':
                mobility_after = self._calculate_mobility(self.learning_color)
                rewards["mobility"] = (mobility_after - mobility_before) * self.mobility_scale
                
                threats_after = self._count_threats(self.learning_color)
                if threats_before > threats_after:
                    rewards["defense"] = (threats_before - threats_after) * self.defense_bonus
                    
                if my_adv >= self.endgame_material_threshold:
                    penalty_multiplier = 1.0 + (my_adv / 5.0)
                    dynamic_step_penalty = self.step_penalty * penalty_multiplier
                    
                    opp_king_after = self._find_king(self.opponent_color)
                    if opp_king_before and opp_king_after:
                        dist_before = self._center_distance(opp_king_before)
                        dist_after = self._center_distance(opp_king_after)
                        if dist_after > dist_before:
                            rewards["endgame_push"] = (dist_after - dist_before) * self.king_push_bonus
                
                # If game continues, fetch Peter's response moves from the website
                if not self.engine.game_over:
                    self._play_external_opponent_turn()
                    
            elif self.engine.phase == 'move_duck':
                opp_mob_after = self._calculate_mobility(self.opponent_color)
                if opp_mob_before > opp_mob_after:
                    rewards["blocking"] = (opp_mob_before - opp_mob_after) * self.duck_blocking_scale

            diff = (material_after_abs - material_before_abs) if self.learning_color == 'w' else (material_before_abs - material_after_abs)
            rewards["material"] = diff * self.material_scale * (self.loss_penalty_multiplier if diff < 0 else 1.0)

            total_reward = sum(rewards.values()) + dynamic_step_penalty
            terminated = getattr(self.engine, 'game_over', False)
            
            if terminated:
                total_reward += 1.0 if self.engine.winner == self.learning_color else (-1.0 if self.engine.winner == self.opponent_color else 0)
                if self.episode_counter % 10 == 0: self._save_replay("periodic_peter")

            return self.get_observation(), total_reward, terminated, False, {}

        except Exception as e:
            self._save_replay(f"PETER_CRASH_{type(e).__name__}")
            raise e

    def _apply_action(self, action):
        start, end = self.engine._decode_move(action)
        if self.engine.phase == 'move_piece': 
            self.engine.execute_move(start, end, animated=False)
        else: 
            self.engine.place_duck(end, animated=False)

    def _play_external_opponent_turn(self):
        """
        Intercepts internal opponent generation. Fetches external moves from 
        Peter's website using the connector, then updates the model's internal map.
        """
        if not self.connector:
            return

        # Fetch actions from external handler [piece_move, duck_placement]
        peter_actions = self.connector.receive_actions_from_site()
        
        for peter_action in peter_actions:
            if getattr(self.engine, 'game_over', False):
                break
            # Applies the movement to the model's matrix state map
            print(f"Pre: {self.engine.phase}")
            self._apply_action(peter_action)
            self.current_episode_actions.append(int(peter_action))
            print(f"Post: {self.engine.phase}")

    def _save_replay(self, reason):
        save_dir = os.path.join("saved_replays", "peter_match")
        os.makedirs(save_dir, exist_ok=True)
        safe_reason = "".join([c for c in reason if c.isalpha() or c.isdigit() or c=='_'])[:30]
        unique_id = uuid.uuid4().hex[:6]
        filename = os.path.join(save_dir, f"{safe_reason}_ep{self.episode_counter}_{int(time.time())}_{unique_id}.pkl")
        try:
            with open(filename, 'wb') as f:
                pickle.dump({
                    'action_history': self.current_episode_actions,
                    'learning_color': self.learning_color,
                    'opponent_color': self.opponent_color
                }, f)
        except: pass

    def render(self): pass
    def close(self): pass