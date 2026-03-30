import json
import os
from datetime import datetime

class SaveManager:
	"""Handles saving played games to JSON files with replay support."""

	@staticmethod
	def save_game(move_history, replay_actions, game_mode, white_player, black_player, winner):
		"""
		Saves the game details, notation log, and raw machine actions for replays.
		"""
		folder_name = "saved_replays"
		
		if not os.path.exists(folder_name):
			os.makedirs(folder_name)
			
		timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
		file_name = f"{white_player}_vs_{black_player}_{timestamp}.json"
		file_path = os.path.join(folder_name, file_name)
		
		save_data = {
			"date_played": timestamp,
			"game_mode": game_mode,
			"players": {
				"white": white_player,
				"black": black_player
			},
			"result": winner,
			"moves": move_history,
			"replay_actions": replay_actions
		}
		
		with open(file_path, 'w', encoding='utf-8') as json_file:
			json.dump(save_data, json_file, indent='\t')
			
		print(f"Game saved successfully to: {file_path}")
		return file_path