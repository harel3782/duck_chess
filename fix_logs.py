import os
from pathlib import Path

def fix_tensorboard_files():
	"""Forces any file inside the log folders to be named correctly for TensorBoard."""
	logs_dir = Path("tensorboard_logs")
	
	if not logs_dir.exists():
		print("Directory not found.")
		return
		
	for folder in logs_dir.iterdir():
		if folder.is_dir():
			for file_path in folder.iterdir():
				if file_path.is_file():
					# Forcefully rename the file to the exact required TensorBoard format
					if not file_path.name.startswith("events.out.tfevents"):
						new_path = folder / "events.out.tfevents.1"
						file_path.rename(new_path)
						print(f"Fixed in {folder.name}: {file_path.name} -> events.out.tfevents.1")

if __name__ == '__main__':
	fix_tensorboard_files()
	print("\n✅ All files fixed. You can run TensorBoard now!")