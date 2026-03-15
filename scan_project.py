import os
from pathlib import Path


def generate_tree(dir_path, ignore_dirs, prefix=""):
    # Generates a string representation of the directory tree
    tree_str = ""

    # Sort directories first, then files
    paths = sorted(dir_path.iterdir(), key=lambda p: (p.is_file(), p.name))
    paths = [p for p in paths if p.name not in ignore_dirs]

    for i, path in enumerate(paths):
        is_last = (i == len(paths) - 1)
        connector = "└── " if is_last else "├── "
        tree_str += f"{prefix}{connector}{path.name}\n"

        if path.is_dir():
            extension = "\t" if is_last else "│\t"
            tree_str += generate_tree(path, ignore_dirs, prefix + extension)

    return tree_str


def combine_codebase(source_dir, output_file):
    # Directories to skip to prevent massive unreadable files
    ignore_dirs = ['.git', '__pycache__', 'venv', 'env', '.idea']
    # Only read relevant source code files
    valid_extensions = ['.py', '.txt', '.md', '.json']

    source_path = Path(source_dir)

    with open(output_file, 'w', encoding='utf-8') as out_f:
        # Write the directory structure at the top of the file
        out_f.write("DIRECTORY STRUCTURE:\n")
        out_f.write(f"{source_path.name}/\n")
        out_f.write(generate_tree(source_path, ignore_dirs))
        out_f.write("\n" + "=" * 60 + "\n\n")

        for file_path in source_path.rglob('*'):
            # Verify it is a file and has an allowed extension
            if file_path.is_file() and file_path.suffix in valid_extensions:

                # Skip if the file is inside any of the ignored directories
                if any(ignored in file_path.parts for ignored in ignore_dirs):
                    continue

                # Create a clear visual separator for each file
                out_f.write(f"\n{'=' * 60}\n")
                out_f.write(f"FILE: {file_path.relative_to(source_path)}\n")
                out_f.write(f"{'=' * 60}\n\n")

                try:
                    # Append the file content to the output file
                    with open(file_path, 'r', encoding='utf-8') as in_f:
                        out_f.write(in_f.read())
                        out_f.write("\n")
                except Exception as e:
                    # Log any reading errors without crashing the script
                    out_f.write(f"ERROR reading file: {e}\n")


if __name__ == '__main__':
    # Set the target folder and the desired output filename
    folder_to_scan = 'DuckChess_Game'
    output_txt = 'duck_chess_full_code.txt'

    if os.path.exists(folder_to_scan):
        combine_codebase(folder_to_scan, output_txt)
        print(f"Success! The codebase was compiled into: {output_txt}")
    else:
        print(f"Error: Could not find the directory '{folder_to_scan}'.")