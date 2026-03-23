import pickle
import sys
import os


def read_binary_game(filepath):
    """
    Loads a .pkl replay file and prints the game details and move log.
    """
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' not found.")
        return

    with open(filepath, 'rb') as f:
        game_data = pickle.load(f)

    print("=" * 40)
    print(f"GAME REPLAY - Episode: {game_data.get('episode', 'Unknown')}")
    print(f"Winner: {game_data.get('winner', 'Unknown').upper()}")
    print("=" * 40)
    print("Move Log:")

    for move in game_data.get('move_log', []):
        print(move)

    print("=" * 40)


if __name__ == "__main__":
    # Change this filename to one of the files generated in the 'saved_replays' folder
    target_file = "saved_replays/game_500_20260311_201500.pkl"
    read_binary_game(target_file)