import os
import wandb
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
from collections import defaultdict

def upload_tensorboard_data():
	base_path = "tensorboard_logs"
	if not os.path.exists(base_path):
		print(f"❌ ERROR: Cannot find folder '{base_path}'")
		return

	stages = {
		"Stage1_Combined": "Stage-1-Random",
		"Stage2_Combined": "Stage-2-Greedy",
		"Stage3_Combined": "Stage-3-Selfplay",
		"Stage4_Combined": "Stage-4-Dense",
		"Stage5_Combined": "Stage-5-Strategic"
	}

	for folder_name, project_group in stages.items():
		stage_path = os.path.join(base_path, folder_name)
		if not os.path.exists(stage_path):
			continue

		print(f"\n🚀 Processing {folder_name}...")
		subdirs = sorted(os.listdir(stage_path))
		
		for sub in subdirs:
			iter_path = os.path.join(stage_path, sub)
			
			event_files = [f for f in os.listdir(iter_path) if f.startswith("events.out.tfevents")]
			if not os.path.isdir(iter_path) or not event_files:
				continue

			event_file_path = os.path.join(iter_path, event_files[0])
			print(f"  ⬆️ Uploading: {sub}")

			run = wandb.init(
				project="duck-chess-training",
				group=project_group,
				name=sub,
				job_type="historical_import"
			)

			ea = EventAccumulator(event_file_path)
			ea.Reload()

			# Dictionary to group metrics by step: {step: {tag1: val1, tag2: val2}}
			step_data = defaultdict(dict)

			# Gather all data and group it by step
			for tag in ea.Tags()['scalars']:
				events = ea.Scalars(tag)
				for event in events:
					step_data[event.step][tag] = event.value
					# We also save the step explicitly as a metric so it plots nicely
					step_data[event.step]["global_step"] = event.step

			# Now, send the data to W&B in strict step order!
			sorted_steps = sorted(step_data.keys())
			for step in sorted_steps:
				wandb.log(step_data[step], step=step)

			run.finish()

if __name__ == "__main__":
	upload_tensorboard_data()
	print("\n✅ All metrics merged by step and uploaded successfully!")