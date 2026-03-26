from DuckChess_Game.UI.rendering_base import BaseRenderingMixin
from DuckChess_Game.UI.rendering_menu import MenuRenderingMixin
from DuckChess_Game.UI.rendering_hud import HUDRenderingMixin
from DuckChess_Game.UI.rendering_board_core import BoardCoreRenderingMixin
from DuckChess_Game.UI.rendering_editor import EditorRenderingMixin
from DuckChess_Game.UI.rendering_animation import AnimationRenderingMixin

class RenderingMixin(
	BaseRenderingMixin, 
	MenuRenderingMixin, 
	HUDRenderingMixin, 
	BoardCoreRenderingMixin, 
	EditorRenderingMixin, 
	AnimationRenderingMixin
):
	"""
	Aggregates all rendering modules into a single interface [cite: 117-119].
	Provides high cohesion by splitting responsibilities into files < 100 lines.
	"""
	pass