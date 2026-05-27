import gymnasium as gym
import numpy as np
import os, time, uuid, pickle
from gymnasium import spaces
from DuckChess_Game.Logic.logic import GameLogicMixin
from DuckChess_Game.Logic.rules_checker import RulesChecker
from DuckChess_Game.Logic.constants import KING, PIECE_VALUES
from DuckChess_Game.playwright_game.peter_interface import PeterInterface

class HeadlessEngine(GameLogicMixin):
	"""A lightweight version of the game strictly for fast RL training."""
	def __init__(self):
		self.game_mode = 'rl_training'
		self.reset_game_state()

class DuckPeterEnv(gym.Env):
    """Stage 10 V3: Anti-Farming & Endgame Optimization."""
    def __init__(self, render_mode=None):
        super(DuckPeterEnv, self).__init__()
            
        self.peter_interface = PeterInterface(headless=False)
        
        self.action_space = spaces.Discrete(4096)
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(19, 8, 8), dtype=np.float32)
        self.render_mode = render_mode
        
        self.engine = HeadlessEngine()
        self.opponent_latest = None
        self.opponent_historical = None
        
        self.episode_counter = 0
        self.current_episode_actions = []
        
        # Will be dynamic upon resetting
        self.learning_color = 'b'
        self.opponent_color = 'w'
        
        # Strategic Scaling Factors
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
        if self.checker.is_in_check(color, self.engine.board, self.engine.duck_pos):
            return 1
        return 0

    def _find_king(self, color):
        board = self.engine.board
        for r in range(8):
            for c in range(8):
                p = board[r][c]
                if p and p.type == KING and p.color == color:
                    return (r, c)
        return None

    def _center_distance(self, pos):
        r, c = pos
        return max(abs(r - 3.5), abs(c - 3.5))

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.peter_interface.reset()
        
        checkbox = self.peter_interface.get_page().locator("input[type='checkbox']")
        if not checkbox.is_checked():
            checkbox.click()
            
        print("Waiting for engine to initialize (Nodes > 0)...")
        self.peter_interface.get_page().wait_for_function(
            """() => {
                const elements = Array.from(document.querySelectorAll('div'));
                const nodeDiv = elements.find(el => el.innerText.includes('Nodes:'));
                if (!nodeDiv) return false;
                const match = nodeDiv.innerText.match(/Nodes:\s*(\d+)/);
                return match && parseInt(match[1]) > 0;
            }""",
            timeout=300000
        )
        print("Engine Active!")

        self.engine.reset_game_state()
        self.current_episode_actions = []
        self.episode_counter += 1
        
        # Dynamic Assignment: "Sometimes white, sometimes black"
        if options and 'learning_color' in options:
            self.learning_color = options['learning_color']
        else:
            self.learning_color = np.random.choice(['w', 'b'])
            
        self.opponent_color = 'b' if self.learning_color == 'w' else 'w'
        
        print("\n" + "="*40)
        print(f" EPISODE #{self.episode_counter} CONFIGURATION")
        print(f" Model Side   : {'WHITE' if self.learning_color == 'w' else 'BLACK'}")
        print(f" Peter Side   : {'WHITE' if self.opponent_color == 'w' else 'BLACK'}")
        print("="*40 + "\n")

        self.board_map = self.peter_interface.map_board_squares(self.peter_interface.get_page())
        
        # If Peter is White, he takes the initiative first before returning observation
        if self.opponent_color == 'w':
            self._play_opponent_turn()
            
        self.inspect_bitboard_occupancy()
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

    def _get_smart_opponent_mask(self, original_mask):
        smart_mask = original_mask.copy()
        if getattr(self.engine, 'phase', '') != 'move_piece':
            return smart_mask

        board = self.engine.board
        in_check = self.checker.is_in_check(self.opponent_color, board, self.engine.duck_pos)
        
        for action in np.where(smart_mask)[0]:
            start, end = self.engine._decode_move(action)
            piece = board[start[0]][start[1]]
            
            if in_check or (piece and piece.type == KING):
                target_piece = board[end[0]][end[1]]
                board[end[0]][end[1]] = piece
                board[start[0]][start[1]] = None
                is_attacked = self.checker.is_in_check(self.opponent_color, board, self.engine.duck_pos)
                board[start[0]][start[1]] = piece
                board[end[0]][end[1]] = target_piece
                
                if in_check and is_attacked:
                    smart_mask[action] = False
                elif piece and piece.type == KING and is_attacked:
                    smart_mask[action] = False

        return smart_mask if np.any(smart_mask) else original_mask

    def step(self, action):
        try:
            self.engine.bb_mgr.print_current_state()
            # self.inspect_bitboard_occupancy()
            masks = self.action_masks()
            if not np.any(masks):
                return self.get_observation(), 0.0, True, False, {}
                
            threats_before = self._count_threats(self.learning_color)
            material_before_abs = self.engine.calculate_material_score(self.engine.board)
            
            mobility_before = 0
            opp_mob_before = 0
            opp_king_before = None
            
            if self.engine.phase == 'move_piece':
                mobility_before = self._calculate_mobility(self.learning_color)
                opp_king_before = self._find_king(self.opponent_color)
            elif self.engine.phase == 'move_duck':
                opp_mob_before = self._calculate_mobility(self.opponent_color)

            pos_bonus = 0
            if self.engine.phase == 'move_piece':
                start, end = self.engine._decode_move(action)
                p = self.engine.board[start[0]][start[1]]
                if p and p.type == KING and abs(start[1] - end[1]) == 2:
                    pos_bonus = self.castling_bonus
            
            # Delegate tracking and execution completely to Peter Interface
            self.peter_interface.model_move(action, self.board_map, self.engine)

            self._apply_action(action)
            self.current_episode_actions.append(int(action))

            rewards = {"material": 0, "pos": pos_bonus, "defense": 0, "blocking": 0, "mobility": 0, "endgame_push": 0}
            dynamic_step_penalty = self.step_penalty
            
            material_after_abs = self.engine.calculate_material_score(self.engine.board)
            my_adv = material_after_abs if self.learning_color == 'w' else -material_after_abs
            
            self.peter_interface.get_page().wait_for_timeout(2000)
            
            # Post-action evaluation updates
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
                
                if not self.engine.game_over:
                    self._play_opponent_turn()
                    
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
                if self.episode_counter % 10 == 0: self._save_replay("periodic")

            return self.get_observation(), total_reward, terminated, False, {}

        except Exception as e:
            self._save_replay(f"CRASH_{type(e).__name__}")
            raise e

    def _apply_action(self, action):
        start, end = self.engine._decode_move(action)
        if self.engine.phase == 'move_piece': 
            self.engine.execute_move(start, end, animated=False)
        else: 
            self.engine.place_duck(end, animated=False)

    def _play_opponent_turn(self):
        """Asynchronously plays out Peter's fully matched responses."""
        if self.engine.turn == self.opponent_color and not getattr(self.engine, 'game_over', False):
            
            # Scrape UI and translate matching coordinates
            p_src_alg, p_dst_alg, last_p_duck_alg, p_duck_alg = self.peter_interface.execute_peter_response(self.board_map)
            
            p_src = self.peter_interface.algebraic_to_coords(p_src_alg)
            p_dst = self.peter_interface.algebraic_to_coords(p_dst_alg)
            p_duck = self.peter_interface.algebraic_to_coords(p_duck_alg)
            
            # Execute matching shifts inside local model
            self.engine.execute_move(p_src, p_dst, animated=False)
            move_action = self.engine._encode_move(p_src, p_dst)
            self.current_episode_actions.append(int(move_action))

            if not getattr(self.engine, 'game_over', False):
                self.engine.place_duck(p_duck, animated=False)
                last_p_duck = self.peter_interface.algebraic_to_coords(last_p_duck_alg)
                duck_action = self.engine._encode_move(last_p_duck, p_duck)
                self.current_episode_actions.append(int(duck_action))

    def _save_replay(self, reason):
        save_dir = os.path.join("saved_replays", "stage_10")
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

    def inspect_bitboard_occupancy(self):
        print("\n" + "="*70)
        print("   CRITICAL DIAGNOSTIC: BITBOARD OCCUPANCY MATRIX (Rank 8 down to 1)")
        print("="*70)
        
        bb_mgr = self.engine.bb_mgr
        for r in range(7, -1, -1):
            row_display = []
            for c in range(8):
                i = r * 8 + c
                bit_mask = 1 << i
                
                is_white = bool(bb_mgr.white_occupancy & bit_mask)
                is_black = bool(bb_mgr.black_occupancy & bit_mask)
                
                if is_white and is_black: symbol = "INVALID_BOTH"
                elif is_white: symbol = "WHITE"
                elif is_black: symbol = "BLACK"
                else: symbol = "  .  "
                    
                if hasattr(self.engine, 'duck_pos') and self.engine.duck_pos == (r, c):
                    symbol = "[DUCK]"
                    
                square_name = self.peter_interface.coords_to_algebraic(r, c)
                row_display.append(f"[{r},{c}] Bit({i:02d}): {symbol:<5} ({square_name})")
                
            print(f"Row Matrix Index {r} | " + " | ".join(row_display))
        print("="*70 + "\n")