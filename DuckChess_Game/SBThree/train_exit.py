#!/usr/bin/env python
"""
train_exit.py — the Expert-Iteration training step (Step 7b).

finetune_value.py retrains ONLY the value head (policy frozen). That is not
Expert Iteration — it can make search's leaves usable but never improves the
move-selection policy, so it cannot move the depth-3 wall. This script trains
BOTH heads on MCTS targets from gen_mcts_data.py, the AlphaZero way:

  policy loss : cross-entropy of the policy head against the MCTS visit
                distribution π   (the search-improved policy — the "expert")
  value loss  : MSE of tanh(value head) against the game outcome z

Warm-starting from the current model and regressing toward the expert's choices
is exactly the policy-improvement half of Expert Iteration; iterating
gen→train→gen distils search back into the network. A small learning rate and
gradient clipping keep the already-strong warm-started policy from being wrecked.

What is trained:
  * mlp_extractor.policy_net + action_net  — TRAINED toward π
  * mlp_extractor.value_net  + value_net   — TRAINED toward z
  (features_extractor is a 0-param FlattenExtractor.)

Targets are stored as the top-K visited actions per position; the CE is taken
over the full 4096 logits with log_softmax (no mask) — illegal moves are masked
only at inference (mcts.py / eval), the standard AlphaZero arrangement.

Usage:
  python -m DuckChess_Game.SBThree.train_exit \
      --base models/duck_ppo/antiexploit_v2/ax_final.zip \
      --data data/exit_iter1.npz \
      --out  models/duck_ppo/exit/exit_v1.zip --epochs 10
  # replay window: train on several recent iterations at once
  python -m DuckChess_Game.SBThree.train_exit --base <ckpt> \
      --data data/exit_iter1.npz data/exit_iter2.npz --out <out>
"""
from __future__ import annotations

import argparse
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

torch.distributions.Distribution.set_default_validate_args(False)

from sb3_contrib import MaskablePPO

ACTION_DIM = 4096


def _load_data(paths):
    obs, pi_idx, pi_val, z = [], [], [], []
    for p in paths:
        d = np.load(p)
        obs.append(d["obs"].astype(np.float32))
        pi_idx.append(d["pi_idx"].astype(np.int64))
        pi_val.append(d["pi_val"].astype(np.float32))
        z.append(d["z"].astype(np.float32))
    return (np.concatenate(obs), np.concatenate(pi_idx),
            np.concatenate(pi_val), np.concatenate(z))


def _target_dist(idx_b, val_b, dev):
    """Scatter top-K (idx, prob) into a dense (B, 4096) target distribution."""
    B = idx_b.shape[0]
    target = torch.zeros(B, ACTION_DIM, device=dev)
    safe = idx_b.clamp(min=0)                     # padding (-1) → index 0, adds val 0
    target.scatter_add_(1, safe, val_b)
    return target


def train_exit(base, data_paths, out, *, epochs=10, batch=512, lr=1e-4,
               vf_coef=1.0, max_grad_norm=0.5, val_frac=0.1, seed=0, quiet=False):
    """Run one ExIt training step; returns the output checkpoint path."""
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)

    obs, pi_idx, pi_val, z = _load_data(data_paths)
    n = len(z)
    perm = rng.permutation(n)
    obs, pi_idx, pi_val, z = obs[perm], pi_idx[perm], pi_val[perm], z[perm]
    n_val = int(n * val_frac)

    model = MaskablePPO.load(base, device="cpu")
    policy = model.policy
    dev = policy.device

    for prm in policy.parameters():               # train the whole net
        prm.requires_grad_(True)
    opt = torch.optim.Adam((p for p in policy.parameters() if p.requires_grad), lr=lr)

    def heads(obs_t):
        """Return (policy_logits, tanh_value) for a batch of observations."""
        feats = policy.extract_features(obs_t)
        latent_pi = policy.mlp_extractor.forward_actor(feats)
        latent_vf = policy.mlp_extractor.forward_critic(feats)
        logits = policy.action_net(latent_pi)
        value = torch.tanh(policy.value_net(latent_vf).squeeze(-1))
        return logits, value

    obs_t = torch.as_tensor(obs, device=dev)
    idx_t = torch.as_tensor(pi_idx, device=dev)
    val_t = torch.as_tensor(pi_val, device=dev)
    z_t = torch.as_tensor(z, device=dev)
    tr = slice(n_val, n)
    va = slice(0, n_val)

    def evaluate(sl):
        policy.eval()
        with torch.no_grad():
            ce_tot = vmse_tot = sign_ok = sign_n = cnt = 0.0
            for s in range(sl.start, sl.stop, 4096):
                e = min(s + 4096, sl.stop)
                logits, value = heads(obs_t[s:e])
                tgt = _target_dist(idx_t[s:e], val_t[s:e], dev)
                logp = F.log_softmax(logits, dim=1)
                ce_tot += float(-(tgt * logp).sum(1).sum())
                zb = z_t[s:e]
                vmse_tot += float(F.mse_loss(value, zb, reduction="sum"))
                nz = zb != 0
                sign_ok += float(((value[nz] > 0) == (zb[nz] > 0)).float().sum())
                sign_n += float(nz.sum())
                cnt += (e - s)
        ce = ce_tot / max(1, cnt)
        vmse = vmse_tot / max(1, cnt)
        sign = sign_ok / max(1.0, sign_n)
        return ce, vmse, sign

    if n_val > 0:
        ce0, vmse0, sign0 = evaluate(va)
        if not quiet:
            print(f"[train_exit] init    val: policy_ce={ce0:.4f} "
                  f"value_mse={vmse0:.4f} value_sign_acc={sign0:.3f}", flush=True)

    n_tr = n - n_val
    for ep in range(1, epochs + 1):
        policy.train()
        order = torch.randperm(n_tr, device=dev) + n_val
        ptot = vtot = 0.0
        for s in range(0, n_tr, batch):
            b = order[s:s + batch]
            logits, value = heads(obs_t[b])
            tgt = _target_dist(idx_t[b], val_t[b], dev)
            logp = F.log_softmax(logits, dim=1)
            ploss = -(tgt * logp).sum(1).mean()
            vloss = F.mse_loss(value, z_t[b])
            loss = ploss + vf_coef * vloss
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(policy.parameters(), max_grad_norm)
            opt.step()
            ptot += float(ploss) * len(b)
            vtot += float(vloss) * len(b)
        if not quiet and (ep % max(1, epochs // 5) == 0 or ep == epochs):
            msg = (f"[train_exit] epoch {ep:>2}  train: policy_ce={ptot / n_tr:.4f} "
                   f"value_mse={vtot / n_tr:.4f}")
            if n_val > 0:
                ce, vmse, sign = evaluate(va)
                msg += f"  | val: policy_ce={ce:.4f} value_mse={vmse:.4f} sign_acc={sign:.3f}"
            print(msg, flush=True)

    model.save(out)
    if not quiet:
        print(f"[train_exit] saved -> {out}  (policy + value both updated)", flush=True)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True, help="checkpoint to warm-start from")
    p.add_argument("--data", required=True, nargs="+", help="one or more .npz files")
    p.add_argument("--out", required=True)
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--batch", type=int, default=512)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--vf-coef", type=float, default=1.0)
    p.add_argument("--max-grad-norm", type=float, default=0.5)
    p.add_argument("--val-frac", type=float, default=0.1)
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()
    train_exit(args.base, args.data, args.out, epochs=args.epochs, batch=args.batch,
               lr=args.lr, vf_coef=args.vf_coef, max_grad_norm=args.max_grad_norm,
               val_frac=args.val_frac, seed=args.seed)


if __name__ == "__main__":
    main()
