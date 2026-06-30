from DuckChess_Game.Logic.constants import *

class EndgameCheckerMixin:
	"""Evaluates material and checks for terminal game states according to Duck Chess rules."""

	def calculate_material_score(self, board_state):
		"""Returns white material minus black material (positive = white ahead)."""
		score = 0
		for r in range(8):
			for c in range(8):
				p = board_state[r][c]
				if p:
					val = PIECE_VALUES.get(p.type, 0)
					score += val if p.color == 'w' else -val
		return score

	def check_game_end_conditions(self):
		"""Validates terminal states: 50-move rule and Fowling (Stalemate win)."""
		if getattr(self, 'game_over', False): return
		
		# Each pawn push or capture resets the clock; all other plies increment it.
		# 100 half-moves = 50 full moves per the FIDE definition.
		if hasattr(self, 'half_move_clock') and self.half_move_clock >= 100:
			self.game_over, self.winner = True, 'draw'
			return

		# Short-circuit scan: stop as soon as any legal move is found.
		has_moves = False
		for r in range(8):
			for c in range(8):
				p = self.board[r][c]
				if p and p.color == self.turn:
					if self.get_piece_legal_moves(r, c):
						has_moves = True
						break
			if has_moves: break
		
		# FOWLING RULE: In Duck Chess, if a player has no legal moves, they WIN.
		if not has_moves:
			self.game_over = True
			self.winner = self.turn  # The stalemated player wins
			if hasattr(self, 'play_sound'): self.play_sound('game_over')