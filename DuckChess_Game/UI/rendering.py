from DuckChess_Game.UI.rendering_base import BaseRenderingMixin
from DuckChess_Game.UI.rendering_ui import UIRenderingMixin
from DuckChess_Game.UI.rendering_board import BoardRenderingMixin

class RenderingMixin(BaseRenderingMixin, UIRenderingMixin, BoardRenderingMixin):
	"""
	Aggregates all rendering mixins. 
	This keeps the code clean while maintaining compatibility with main.py.
	"""
	pass