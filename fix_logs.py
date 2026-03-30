import os
import tensorflow as tf
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

def merge_tensorboard_logs(input_dir, output_dir, prefix):
	"""
	Merges multiple TensorBoard event files that start with a specific prefix
	into a single, continuous event file in a new directory.
	"""
	print(f"Merging logs starting with '{prefix}' into '{output_dir}'...")
	os.makedirs(output_dir, exist_ok=True)
	
	# Create a new writer in the output directory
	writer = tf.summary.create_file_writer(output_dir)
	
	# Find all subdirectories that match the prefix and sort them
	dirs_to_merge = []
	for d in os.listdir(input_dir):
		if d.startswith(prefix):
			full_path = os.path.join(input_dir, d)
			if os.path.isdir(full_path):
				dirs_to_merge.append(full_path)
	
	# Try to sort intelligently (e.g., iter_0, iter_1, iter_10)
	try:
		dirs_to_merge.sort(key=lambda x: int(x.split('_iter_')[-1].split('_')[0]))
	except:
		dirs_to_merge.sort() # Fallback alphabetical

	if not dirs_to_merge:
		print(f"No directories found for prefix '{prefix}'")
		return

	# Load and write data
	with writer.as_default():
		for d in dirs_to_merge:
			print(f"  Reading {d}...")
			# Find the actual event file inside the directory
			event_files = [f for f in os.listdir(d) if "events.out.tfevents" in f]
			if not event_files: continue
			
			event_file_path = os.path.join(d, event_files[0])
			
			# Load the events
			ea = EventAccumulator(event_file_path)
			ea.Reload()
			
			# We'll merge the scalars (the line graphs)
			for tag in ea.Tags()['scalars']:
				events = ea.Scalars(tag)
				for event in events:
					tf.summary.scalar(tag, event.value, step=event.step)
					
	writer.close()
	print(f"Successfully created merged log at {output_dir}\n")

if __name__ == "__main__":
	base_logs = "tensorboard_logs"
	
	# Merge Stage 3
	merge_tensorboard_logs(base_logs, "tensorboard_logs/stage3_merged", "run_stage3_selfplay")
	
	# Merge Stage 4
	merge_tensorboard_logs(base_logs, "tensorboard_logs/stage4_merged", "run_stage4_dense")
	
	# Merge Stage 5 (Up to the point you stopped)
	merge_tensorboard_logs(base_logs, "tensorboard_logs/stage5_merged", "run_stage5_strategic")