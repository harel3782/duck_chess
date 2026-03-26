from DuckChess_Game.Logic.move_generation import MoveGenerationMixin
from DuckChess_Game.Logic.state_manager import StateManagerMixin

class GameLogicMixin(MoveGenerationMixin, StateManagerMixin):
	"""Aggregates all game logic mixins."""
	pass