# Models, Evaluation, and Results

## The five ranked models — `models/duck_ppo/ranked/`

The UI (both desktop and web) automatically loads the highest-ranked model present. Ranking is by filename: `1_champion` beats `2_allrounder` beats `3_aggressive`, etc.

| Rank | File | vs Peter d1 | vs Peter d2 | How it was made |
|------|------|:-----------:|:-----------:|-----------------|
| 1 | `1_champion.zip` | **1.00** (20/0/0) | **1.00** (20/0/0) | ExIt iteration 1 from `strong_final` base |
| 2 | `2_allrounder.zip` | 0.80 (12W/3D/0L) | 0.67 (10W/5D/0L) | v2 PPO policy + distilled value head |
| 3 | `3_aggressive.zip` | 0.46 (glass cannon) | 1.00 (20/0/0) | `strong_final` — beats d2 perfectly, weak to king-rush |
| 4 | `4_classic.zip` | ~0.27 | ~0.55 | Original v2 PPO, no dedicated value head |
| 5 | `5_safe.zip` | weak | weak | antiexploit_v2 corrective run, exploits fixed but passive |

**d1 = Peter depth-1**: plays aggressive, king-rush style. Mirrors how typical human players attack.  
**d2 = Peter depth-2**: plays proper positional moves. A more strategic, well-rounded opponent.  
**d3 = Peter depth-3**: deep tactical play. Every model scores 0% here — the open research challenge.

---

## How strength is measured — `eval_vs_peter.py`

**Ground truth is always measured against Peter, never from self-play.**

Early in the project, self-play win rates were used to track progress. They consistently overstated real strength — a model could reach 80% self-play win rate and then score 20% against Peter. Self-play creates an echo chamber: if the model develops a weakness (e.g., poor king defense), it exploits that weakness against itself and reports high win rates, but Peter does not have the same weakness.

`eval_vs_peter.py` plays N games (typically 20 per color configuration) against Peter at a fixed depth, alternating colors, and reports W/L/D counts and a score:

```
score = (wins + 0.5 × draws) / total_games
```

A score of 1.00 means perfect — every game won. A score of 0.50 means equal (like Elo 0 difference). A score of 0.00 means every game lost.

### With MCTS — `eval_search.py`

The champion model is evaluated **with MCTS**, not just raw policy. This better reflects how the model actually plays in the UI. The eval command:

```bash
python -m DuckChess_Game.SBThree.eval_search --engine mcts --sims 200
```

The raw policy without search scores somewhat lower than the same model with MCTS, confirming that MCTS adds genuine strength beyond what the policy alone achieves.

---

## The depth-3 wall

Every model trained so far scores **0%** against Peter depth-3. This is the defining open challenge.

**Why is depth-3 so much harder?**

Peter at depth-3 searches the game tree to depth 3 (full turns, not half-moves). It can see captures, counter-captures, and king attacks three moves ahead. The tactics at depth-3 involve combinations that require planning more than 1-2 moves ahead.

The champion model with 300 MCTS simulations can effectively "see" a few moves ahead, but Peter d3's alpha-beta search at depth-3 is extremely efficient at finding tactical shots. The combination of a hand-crafted evaluation function (Peter's heuristic) with a guaranteed 3-move look-ahead is hard to beat without either (a) many more MCTS simulations or (b) a much better value head.

**Possible paths forward** (discussed in PLAN_V2.md):
1. More ExIt iterations with higher MCTS simulation counts (expensive, compute-bound)
2. A CNN-based network architecture instead of MLP (better spatial pattern recognition)
3. Training specifically against Peter d3 to generate targeted tactical data
4. A stronger value head trained on positions where the model currently blunders

---

## Model training lineage

```
Random play (Stage 1-3)
       ↓
League self-play (Stages 4-13) — each stage vs stronger opponents
       ↓
4_classic.zip  ← first usable model, sparse reward, no value head
       ↓
v2 training — opponent pool + random starts + sparse reward
       ↓
2_allrounder.zip  ← balanced model, has value head via distillation
       ↓
train_strong.py — 12h corrective vs Peter + strong self-play
       ↓
3_aggressive.zip = strong_final  ← perfect vs d2, weak to king-rush
       ↓
antiexploit_v2 corrective — fixes exploits but too passive
       ↓
5_safe.zip
       ↓
Expert Iteration (run_exit.py, 1 iteration, 500 games, sims=300)
starting from strong_final base
       ↓
1_champion.zip  ← 1.00 vs d1, 1.00 vs d2, 0.00 vs d3
```

---

## How models are loaded

### Desktop UI (`DuckChess_Game/UI/main.py`)

```python
model_path = "models/duck_ppo/ranked/1_champion.zip"
USE_MCTS   = True
DIFFICULTY = "hard"   # → sims = 300

self.rl_searcher = DuckMCTS(self.rl_model, sims=300, c_puct=1.5)
```

The model path is hardcoded to try `1_champion → 2_allrounder → 4_classic` in order (first one that exists is used). With `USE_MCTS=True`, the `ai_turn()` function calls `rl_searcher.choose_turn()` instead of the raw policy.

### Web UI (`web_ui/server.py`)

The web server auto-discovers all `.zip` files in `models/duck_ppo/**/*.zip` using `discover_models()`. Models are loaded lazily (on first request) and cached in a dictionary. Users can select any model from the web interface — the ranked models appear sorted by name (1_ first).

---

## Key measurements for the defense

| Claim | Evidence |
|-------|---------|
| Champion beats Peter d1 perfectly | `eval_vs_peter.py`: 20W / 0D / 0L |
| Champion beats Peter d2 perfectly | `eval_vs_peter.py`: 20W / 0D / 0L |
| MCTS improves over raw policy | `eval_search.py` with/without MCTS shows measurable gap |
| ExIt improved over PPO baseline | `2_allrounder` (pre-ExIt) scores 0.80/0.67; `1_champion` (post-ExIt) scores 1.00/1.00 |
| Self-play is not reliable | Historical data in `docs/training_log.md` shows self-play inflated scores vs Peter ground truth |
| d3 remains unsolved | All models: 0W / 0D / NL vs Peter depth-3 |

---

## The three behavioral exploits (antiexploit_v2)

Before ExIt, three specific exploits were identified by playing against the model:

1. **Opening repetition**: the model always played the same first 5-10 moves. A human who knew the pattern could prepare specific counter-play. Fixed by ExIt's Dirichlet noise and temperature sampling.

2. **Passive duck placement**: the model placed the duck in the same few default positions regardless of the position. A good player could predict where the duck would go. Fixed by ExIt's explicit duck-node training targets.

3. **Endgame collapse**: when the model had a winning material advantage, it would sometimes shuffle pieces aimlessly instead of converting. The 50-move draw cap and Peter d1 training data (which forces king-attack situations) helped here.

`5_safe.zip` (antiexploit_v2) fixed all three exploits but became too passive — it avoided material losses at the cost of never winning. The lesson: exploit-fixing via conservative training can overcorrect. ExIt, by training on MCTS games against real opponents, fixed the exploits while maintaining aggressive strength.
