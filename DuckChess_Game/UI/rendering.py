from DuckChess_Game.UI.rendering_base import BaseRenderingMixin
from DuckChess_Game.UI.rendering_menu import MenuRenderingMixin
from DuckChess_Game.UI.rendering_rules import RulesRenderingMixin
from DuckChess_Game.UI.rendering_promotion import PromotionRenderingMixin
from DuckChess_Game.UI.rendering_hud import HUDRenderingMixin
from DuckChess_Game.UI.rendering_board_core import BoardCoreRenderingMixin
from DuckChess_Game.UI.rendering_editor import EditorRenderingMixin
from DuckChess_Game.UI.rendering_animation import AnimationRenderingMixin

class RenderingMixin(
	BaseRenderingMixin, 
	MenuRenderingMixin, 
	RulesRenderingMixin,
	PromotionRenderingMixin,
	HUDRenderingMixin, 
	BoardCoreRenderingMixin, 
	EditorRenderingMixin, 
	AnimationRenderingMixin
):
	"""
	Aggregates all rendering modules into a single interface.
	Provides high cohesion by splitting responsibilities into specific files.
	"""
	pass