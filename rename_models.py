import os
from pathlib import Path

def rename_model_files():
	"""Renames the model files to match the new, cleaner naming convention."""
	
	models_dir = Path("models/duck_ppo")
	
	# Mapping of old filenames to new filenames
	rename_map = {
		"duck_stage1_final.zip": "stage1_random.zip",
		"duck_stage2_greedy_final.zip": "stage2_greedy.zip",
		"duck_latest.zip": "stage3_selfplay_latest.zip"
	}
	
	# Add the v0-v9 dynamic mapping
	for i in range(10):
		rename_map[f"duck_v{i}.zip"] = f"stage3_selfplay_v{i}.zip"
		
	if not models_dir.exists():
		print("Directory not found.")
		return
		
	for old_name, new_name in rename_map.items():
		old_path = models_dir / old_name
		new_path = models_dir / new_name
		
		if old_path.exists():
			old_path.rename(new_path)
			print(f"Renamed: {old_name} -> {new_name}")

if __name__ == '__main__':
	rename_model_files()
	print("\n✅ All models successfully renamed!")