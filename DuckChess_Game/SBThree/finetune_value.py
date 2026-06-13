#!/usr/bin/env python
"""
finetune_value.py — retrain ONLY the value head of a v2 checkpoint on real
game outcomes, so search.py has a usable leaf evaluator.

Why: the v2 policy is strong but its PPO value head is a poor positional
evaluator (see PLAN_V2.md Step 6: search with leaf='value' cratered d2 95%->0%
because value-driven move overrides are noise). This script does supervised
regression of the value head onto Monte-Carlo game outcomes from
gen_value_data.py, while FREEZING the policy so raw play is byte-for-byte
unchanged (95% vs Peter d2).

What is trained / frozen:
  * features_extractor — FlattenExtractor, 0 params (shared but nothing to train)
  * mlp_extractor.policy_net + action_net — FROZEN (policy untouched)
  * mlp_extractor.value_net + value_net  — TRAINED (regress to outcome z)

The value head outputs a raw scalar; targets are z in [-1,1]; we train with MSE
on tanh(value) so the scale matches how search interprets it (search applies
tanh to the value-head output).

Output: a new checkpoint with the same policy and a retrained value head.

Usage:
  python -m DuckChess_Game.SBThree.finetune_value \
      --model models/duck_ppo/v2/v2_final.zip \
      --data  data/value_v2.npz \
      --out   models/duck_ppo/v2/v2_value.zip \
      --epochs 30
"""
from __future__ import annotations

import argparse
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import torch
import torch.nn as nn

torch.distributions.Distribution.set_default_validate_args(False)

from sb3_contrib import MaskablePPO


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="models/duck_ppo/v2/v2_final.zip")
    p.add_argument("--data", default="data/value_v2.npz")
    p.add_argument("--out", default="models/duck_ppo/v2/v2_value.zip")
    p.add_argument("--epochs", type=int, default=30)
    p.add_argument("--batch", type=int, default=512)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--val-frac", type=float, default=0.1)
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()

    torch.manual_seed(args.seed)
    rng = np.random.default_rng(args.seed)

    d = np.load(args.data)
    obs, z = d["obs"].astype(np.float32), d["z"].astype(np.float32)
    n = len(z)
    print(f"dataset: {n} samples | z win/loss/draw = "
          f"{np.mean(z>0):.1%}/{np.mean(z<0):.1%}/{np.mean(z==0):.1%}")

    perm = rng.permutation(n)
    obs, z = obs[perm], z[perm]
    n_val = int(n * args.val_frac)
    tr_obs, tr_z = obs[n_val:], z[n_val:]
    va_obs, va_z = obs[:n_val], z[:n_val]

    model = MaskablePPO.load(args.model, device="cpu")
    policy = model.policy
    dev = policy.device

    # Freeze everything, then unfreeze only the value path.
    for prm in policy.parameters():
        prm.requires_grad_(False)
    value_params = (list(policy.mlp_extractor.value_net.parameters())
                    + list(policy.value_net.parameters()))
    for prm in value_params:
        prm.requires_grad_(True)
    opt = torch.optim.Adam(value_params, lr=args.lr)

    def predict_tanh_value(obs_batch_t):
        """tanh(value head) for a batch of obs tensors, value path only."""
        features = policy.extract_features(obs_batch_t)
        if policy.share_features_extractor:
            latent_vf = policy.mlp_extractor.forward_critic(features)
        else:
            latent_vf = policy.mlp_extractor.forward_critic(features)
        return torch.tanh(policy.value_net(latent_vf).squeeze(-1))

    va_obs_t = torch.as_tensor(va_obs, device=dev)
    va_z_t = torch.as_tensor(va_z, device=dev)

    def val_loss():
        policy.eval()
        with torch.no_grad():
            preds = []
            for i in range(0, len(va_z), 4096):
                preds.append(predict_tanh_value(va_obs_t[i:i + 4096]))
            pred = torch.cat(preds) if preds else torch.zeros(0)
            mse = nn.functional.mse_loss(pred, va_z_t).item()
            # sign agreement vs non-draw targets = "does it call the winner?"
            mask = va_z_t != 0
            acc = ((pred[mask] > 0) == (va_z_t[mask] > 0)).float().mean().item() \
                if mask.any() else float("nan")
        return mse, acc

    mse0, acc0 = val_loss()
    print(f"epoch  0 (init)   val_mse={mse0:.4f}  sign_acc={acc0:.3f}")

    n_tr = len(tr_z)
    tr_obs_t = torch.as_tensor(tr_obs, device=dev)
    tr_z_t = torch.as_tensor(tr_z, device=dev)
    for ep in range(1, args.epochs + 1):
        policy.train()
        idx = torch.randperm(n_tr, device=dev)
        tot = 0.0
        for s in range(0, n_tr, args.batch):
            b = idx[s:s + args.batch]
            pred = predict_tanh_value(tr_obs_t[b])
            loss = nn.functional.mse_loss(pred, tr_z_t[b])
            opt.zero_grad()
            loss.backward()
            opt.step()
            tot += loss.item() * len(b)
        if ep % 5 == 0 or ep == args.epochs:
            mse, acc = val_loss()
            print(f"epoch {ep:>2}  train_mse={tot / n_tr:.4f}  "
                  f"val_mse={mse:.4f}  sign_acc={acc:.3f}")

    model.save(args.out)
    print(f"\nsaved -> {args.out}  (policy unchanged; value head retrained)")
    print("next: python -m DuckChess_Game.SBThree.eval_search --model "
          f"{args.out} --leaf-eval value --mode best --games 12 --peter-depth 2 --depth 2")


if __name__ == "__main__":
    main()
