import pickle
import os

def analyze_replay(filepath):
	# Verify that the file exists before attempting to load
	if not os.path.exists(filepath):
		print(f"File not found: {filepath}")
		return

	# Load the binary pickle file safely
	with open(filepath, 'rb') as f:
		data = pickle.load(f)
	
	actions = data.get('action_history', [])
	print(f"--- Analyzing: {filepath} ---")
	print(f"Learning Color: {data.get('learning_color')}")
	
	# Iterate over actions to decode them back to board coordinates
	for i, action in enumerate(actions):
		# Decode the 0-4095 action index to start and end squares
		start_sq = action // 64
		end_sq = action % 64
		
		sr, sc = start_sq // 8, start_sq % 8
		er, ec = end_sq // 8, end_sq % 8
		
		# Convert numeric indices to standard chess notation (e.g., e2)
		start_str = f"{'abcdefgh'[sc]}{'87654321'[sr]}"
		end_str = f"{'abcdefgh'[ec]}{'87654321'[er]}"
		
		# Even indices are piece moves, odd indices are duck placements
		if i % 2 == 0:
			print(f"Turn {i//2 + 1}: Piece {start_str} -> {end_str}")
		else:
			print(f"         Duck -> {end_str}")
			
	print("-" * 40 + "\n")

# Process the three latest replay files
analyze_replay("periodic_ep4000_1775424129_9f8795.pkl")
