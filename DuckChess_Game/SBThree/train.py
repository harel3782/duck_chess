import os
from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker
from duck_env import DuckChessEnv


def mask_fn(env: DuckChessEnv):
    return env.get_action_masks()


def main():
    env = DuckChessEnv()
    env = ActionMasker(env, mask_fn)

    models_dir = "models/duck_ppo"
    os.makedirs(models_dir, exist_ok=True)
    model_path = f"{models_dir}/duck_model_v1.zip"

    if os.path.exists(model_path):
        print(f"Loading existing model from {model_path}...")
        model = MaskablePPO.load(model_path, env=env)
    else:
        print("Starting fresh training with stability parameters...")
        # We add 'max_grad_norm' to prevent gradient explosions (NaNs)
        # and increase 'batch_size' for more stable updates.
        model = MaskablePPO(
            "MlpPolicy",
            env,
            verbose=1,
            batch_size=128,  # Increased from 64 for stability
            max_grad_norm=0.5,  # Strictly limits how much weights can jump
            learning_rate=0.0002  # Slightly slower learning for better convergence
        )

    print("Starting training! Press Ctrl+C to save and stop early.")
    try:
        # Training for 500,000 steps
        model.learn(total_timesteps=100_000, reset_num_timesteps=False)
    except KeyboardInterrupt:
        print("\nTraining interrupted. Saving progress...")

    model.save(f"{models_dir}/duck_model_v1")
    print(f"Model saved successfully to {models_dir}/duck_model_v1")


if __name__ == "__main__":
    main()