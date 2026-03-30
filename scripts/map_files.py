import os
from pathlib import Path

def generate_tree(dir_path: Path, prefix: str = '', exclude_dirs=None):
	"""Generates a directory tree, ignoring virtual environments, cache folders, and replays."""
	
	# Default directories to ignore to keep the tree clean
	if exclude_dirs is None:
		exclude_dirs = {
			'.git', 'node_modules', '__pycache__', 'dist', 'build', 
			'.vercel', '.venv', 'venv', 'env', '.idea', '.vscode',
			'saved_replays', 'wandb', '.qodana'
		}
		
	try:
		# Sort paths: directories first, then files
		paths = sorted(dir_path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
		
		# Filter out the excluded directories
		paths = [p for p in paths if not (p.is_dir() and p.name in exclude_dirs)]
		
		for index, path in enumerate(paths):
			is_last = index == (len(paths) - 1)
			connector = '└── ' if is_last else '├── '
			
			if path.is_dir():
				print(f"{prefix}{connector}📂 {path.name}/")
				# Recursive call into the directory
				extension = '    ' if is_last else '│   '
				generate_tree(path, prefix + extension, exclude_dirs)
			else:
				# Skip compiled python files to reduce noise
				if path.name.endswith('.pyc'):
					continue
				print(f"{prefix}{connector}📄 {path.name}")
				
	except PermissionError:
		print(f"{prefix}└── 🔒 [Access Denied]")

if __name__ == '__main__':
	# Run the script on the current working directory
	current_dir = Path.cwd()
	print(f"\n📦 {current_dir.name}/")
	generate_tree(current_dir)
	print("\n✅ Mapping complete!\n")