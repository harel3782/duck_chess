from DuckChess_Game.Logic.move_generation import MoveGenerationMixin
from DuckChess_Game.Logic.state_manager import StateManagerMixin

class GameLogicMixin(MoveGenerationMixin, StateManagerMixin):
	"""
	Aggregates all game logic mixins.
	This keeps the code clean while maintaining compatibility with UI/main.py.
	"""
	pass