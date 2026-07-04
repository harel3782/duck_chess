# Duck Chess AI — תיעוד מקיף ללמידת מכונה

> **לקראת הגנה על הפרויקט** | פיתוח סוכן AI ל-Duck Chess באמצעות Reinforcement Learning, MCTS, ו-Expert Iteration

---

## תוכן עניינים

1. [מה זה Duck Chess?](#1-מה-זה-duck-chess)
2. [הגדרת הבעיה כ-RL](#2-הגדרת-הבעיה-כ-rl)
3. [ייצוג המצב — Observation Space](#3-ייצוג-המצב--observation-space)
4. [מרחב הפעולות — Action Space](#4-מרחב-הפעולות--action-space)
5. [מסכת פעולות — Action Masking](#5-מסכת-פעולות--action-masking)
6. [ארכיטקטורת הרשת — MaskablePPO](#6-ארכיטקטורת-הרשת--maskableppo)
7. [פונקציית הגמול — Reward Function](#7-פונקציית-הגמול--reward-function)
8. [קוריקולום האימון — Training Curriculum](#8-קוריקולום-האימון--training-curriculum)
9. [בעיות שנתגלו בדרך](#9-בעיות-שנתגלו-בדרך)
10. [חיפוש בזמן ריצה — Inference-Time Search](#10-חיפוש-בזמן-ריצה--inference-time-search)
11. [MCTS — AlphaZero Style](#11-mcts--alphazero-style)
12. [Value Distillation — זיקוק ראש הערך](#12-value-distillation--זיקוק-ראש-הערך)
13. [Expert Iteration (ExIt) — הלולאה של AlphaZero](#13-expert-iteration-exit--הלולאה-של-alphazero)
14. [תוצאות ודירוג המודלים](#14-תוצאות-ודירוג-המודלים)
15. [שיעורים מרכזיים שנלמדו](#15-שיעורים-מרכזיים-שנלמדו)
16. [בעיות פתוחות](#16-בעיות-פתוחות)

---

## 1. מה זה Duck Chess?

Duck Chess הוא וריאנט שחמט עם 3 חוקים מיוחדים שמשנים את המשחק באופן קיצוני:

### החוקים המיוחדים

| חוק | הסבר | השפעה על ה-AI |
|-----|-------|---------------|
| **ה-Duck (ברווז)** | אחרי כל מהלך רגיל, השחקן חייב להזיז ברווז נייטרלי לכיכר ריקה אחרת | כל תור = **2 שלבים**: הזזת כלי + הזזת ברווז |
| **ניצחון בלכידת מלך** | אין שח/שח-מט; מנצחים על-ידי **לכידת המלך** הפיזית | אסטרטגיה שונה לחלוטין מהשחמט הרגיל |
| **Fowling** | שחקן שאין לו מהלכים חוקיים — **מנצח** (הפוך מ-stalemate!) | חוקי סיום מהופכים — אינטואיציה של שחמט רגיל תוביל לטעויות |

### למה Duck Chess מאתגר ל-AI?

```
תור רגיל בשחמט:    64 × 64 = 4,096 אפשרויות
תור ב-Duck Chess:   4,096 × ~55 (מיקומי ברווז) ≈ 225,000 אפשרויות
```

- מרחב הפעולות כפול (כלי + ברווז)
- הברווז יכול לחסום מהלכים, להגן על כלים, או לפתוח נתיבי תקיפה
- אין check/checkmate — הלוגיקה האסטרטגית שונה לחלוטין

---

## 2. הגדרת הבעיה כ-RL

### Markov Decision Process (MDP)

הגדרנו את המשחק כ-MDP:

```
State (s):      מיקום כל הכלים + ברווז + זכויות הצרחה + en passant + turn
Action (a):     מהלך (from, to) — אותו פורמט לכלי ולברווז
Reward (r):     +1 ניצחון / -1 הפסד / 0 תיקו (גמול ספרסי)
Transition:     חוקי המשחק (דטרמיניסטי)
Episode:        משחק שלם (עד לכידת מלך / 50 מהלכים)
```

### הסוכן: MaskablePPO

הסוכן שלנו מבוסס על **Proximal Policy Optimization (PPO)** עם הרחבת **Action Masking**:

- **Actor (Policy)**: בוחר מהלכים על-פי התפלגות הסתברותית
- **Critic (Value Head)**: מעריך את הציון הצפוי מכל מצב
- **Masking**: מבטל פעולות לא-חוקיות לחלוטין (ראה סעיף 5)

---

## 3. ייצוג המצב — Observation Space

### Tensor של 19 ערוצים: `19 × 8 × 8`

הלוח מיוצג כ-tensor תלת-ממדי דומה ל-AlphaZero:

```
Shape: (19, 8, 8)  →  19 "תמונות" של לוח 8×8
```

| ערוצים | תוכן | ערכים |
|--------|------|-------|
| **0–5** | כלים לבנים (פרש, רץ, צריח, מלכה, מלך, רגלי) | 0.0 / 1.0 |
| **6–11** | כלים שחורים (אותו סדר) | 0.0 / 1.0 |
| **12** | מיקום הברווז | 0.0 / 1.0 |
| **13** | En Passant target | 0.0 / 1.0 |
| **14** | צבע התור הנוכחי | 1.0 = לבן, 0.0 = שחור |
| **15–18** | זכויות הצרחה (KS/QS לשני הצבעים) | 0.0 / 1.0 |

### קוד הייצוג (מ-`observation_encoder.py`):

```python
obs = np.zeros((19, 8, 8), dtype=np.float32)

# Channels 0-11: מיקום כלים ישירות מ-Bitboards
piece_to_channel = {
    ('w', PAWN): 0, ('w', KNIGHT): 1, ..., ('w', KING): 5,
    ('b', PAWN): 6, ...,                   ('b', KING): 11
}

# Channel 12: מיקום הברווז
# Channel 14: תור — 1.0 ללבן, 0.0 לשחור (כל ה-8×8 מלאים)
# Channels 15-18: זכויות הצרחה (כל ה-8×8 מלאים)
```

### למה ייצוג כזה?

- **ביטבורד (Bitboard)**: כל כלי מיוצג כמספר 64-ביט — חישוב מהלכים חוקיים במהירות O(1)
- **Tensor כמו תמונה**: מאפשר לרשת לזהות דפוסים מרחביים (CNN-style)
- **ריבוי ערוצים**: כל סוג כלי בערוץ נפרד — הרשת לומדת את החשיבות של כל סוג

---

## 4. מרחב הפעולות — Action Space

### 4096 פעולות דיסקרטיות

```
מרחב: 64 × 64 = 4,096
קידוד: action_idx = (from_row * 8 + from_col) * 64 + (to_row * 8 + to_col)
```

**גאונות העיצוב**: אותו מרחב פעולות משמש גם להזזת כלי וגם להזזת ברווז!
- **שלב כלי**: `from` = מיקום הכלי, `to` = יעד
- **שלב ברווז**: `from` = (0,0) כ-dummy, `to` = כיכר יעד הברווז

זה מאפשר לאותה רשת לשחק שני שלבים ללא ארכיטקטורה נפרדת.

---

## 5. מסכת פעולות — Action Masking

### הבעיה

PPO סטנדרטי יכול לבחור פעולות לא-חוקיות (הזזת כלי שלא ניתן להזיז). ב-Duck Chess זה קטסטרופלי — יש מיליוני מצבים שרוב הפעולות בהם לא-חוקיות.

### הפתרון: MaskablePPO

```python
masks = np.zeros(4096, dtype=bool)  # כל פעולות חסומות כברירת מחדל

# שלב הזזת כלי — מסמן רק יעדים חוקיים
if phase == 'move_piece':
    for each piece position:
        for each legal destination:
            masks[encode(from, to)] = True

# שלב הזזת ברווז — כל כיכר ריקה (חוץ מהמיקום הקודם)
elif phase == 'move_duck':
    valid_squares = ~all_occupancy & 0xFFFFFFFFFFFFFFFF
    valid_squares &= ~previous_duck_position
```

### ForcedKingCaptureMask

**חוק קריטי**: אם יש לכידת מלך זמינה — **חובה לבצע אותה**.

```python
# מסנן את המסכה לפעולות לכידת מלך בלבד, אם קיימות
for action in legal_actions:
    if board[action.to] == KING and board[action.to].color != my_color:
        force_this_action()  # חסם את כל השאר
```

**למה זה קריטי ל-RL?**
- הרשת נותנת prior נמוך מאוד ללכידת מלך (רשעה נדירה בנתוני אימון)
- בלי כלל זה, הסוכן לא לוכד מלך גם כשהדרך פתוחה — טעות קטלנית

---

## 6. ארכיטקטורת הרשת — MaskablePPO

### Proximal Policy Optimization (PPO)

PPO הוא אלגוריתם RL מהסוג Policy Gradient עם מספר יתרונות:

```
מטרת ה-Actor:   max  E[min(r_t * A_t, clip(r_t, 1-ε, 1+ε) * A_t)]
מטרת ה-Critic:  min  E[(V(s) - V_target)²]
```

כאשר:
- `r_t = π_new(a|s) / π_old(a|s)` — יחס ההסתברויות
- `A_t` — פונקציית ה-Advantage (כמה המהלך היה טוב יחסית לציפייה)
- `ε = 0.2` — מגביל את הצעד (Clipping) למניעת עדכונים גדולים מדי

### מבנה הרשת

```
Input: (19, 8, 8) observation tensor
         ↓
   Shared Backbone (CNN / MLP)
    /              \
Actor Head         Critic Head
(Policy π)         (Value V)
    ↓                   ↓
4096 logits        1 scalar
    ↓                   
 + Masking        
    ↓               
Softmax → action
```

### Stable-Baselines3 + sb3-contrib

```python
from sb3_contrib import MaskablePPO

model = MaskablePPO(
    "MlpPolicy",          # ניתן גם CnnPolicy
    env,
    n_steps=2048,
    batch_size=64,
    n_epochs=10,
    learning_rate=3e-4,
    ent_coef=0.05,        # Entropy coefficient — מעודד חקר
    vf_coef=0.5,          # Value function coefficient
    verbose=1
)
```

---

## 7. פונקציית הגמול — Reward Function

### גמול ספרסי (Sparse / Terminal Reward)

```python
class TerminalReward:
    win  = +1.0   # ניצחון
    loss = -1.0   # הפסד
    draw =  0.0   # תיקו (50 מהלכים)
    
    # כל שאר הצעדים: 0.0
```

**יתרונות**: הסוכן לומד לנצח — לא לאסוף נקודות ביניים. ראש הערך (Critic) מייצג **הסתברות ניצחון**, לא תגמול מצטבר.

**חסרונות**: קשה ללמוד מגמול שטוח (flat -1 כנגד יריב חזק).

---

### גמול מעוצב (Dense / Shaped Reward)

שימש בשלבי האימון הראשונים כדי לתת אות לימוד:

```python
class ShapedReward:
    # רכיבים שניתן להפעיל/לכבות:
    material_weight    = 0.05   # פרש=3, רץ=3, צריח=5, מלכה=9
    development_bonus  = 0.1    # אנקאות יצאו מהשורה הביתית
    castling_bonus     = 0.3    # הצרחה
    duck_placement_bonus = 0.05 # הברווז חוסם מהלכי יריב
    mobility_scale     = 0.01   # מספר המהלכים החוקיים שלי
    king_push_bonus    = 0.1    # דחיפת מלך יריב לפינה
    step_penalty       = 0.001  # עונש לכל צעד — מעודד משחק מהיר
```

**הבעיה שגילינו**: גמול מעוצב **הרס את ראש הערך**:
- הסוכן לומד לאסוף גמול מעוצב, לא לנצח
- ראש הערך מייצג "תגמול צפוי", לא "סיכויי ניצחון"
- ערך התחלתי: `V = +3.9` (saturated tanh) — חסר כל משמעות לחיפוש

---

## 8. קוריקולום האימון — Training Curriculum

### שיטת הקוריקולום

הסוכן לא אומן ישירות נגד אויב חזק — זה יביא ל-flat reward ואין למידה. במקום זה בנינו **קוריקולום הדרגתי**:

```
Stage 1 → Stage 2 → ... → Stage 13 → v2 → antiexploit_v2 → ExIt
  מחזירים → גרדי → ליגה עצמית → Peter d1 → Peter d2 → ...
```

---

### Stage 1 — "גן ילדים" (2026-03-15)
- **יריב**: Random bot (מהלך אקראי)
- **גמול**: Dense
- **מטרה**: ללמוד מהלכים חוקיים ולכידת מלך בסיסית
- **שלבים**: 100,000
- **תוצאה**: `ep_rew_mean ≈ 0.9` ✅

### Stage 2 — "בית ספר יסודי" (2026-03-27)
- **יריב**: Greedy bot (תמיד לוכד אם יכול)
- **מטרה**: ללמוד הגנה בסיסית על כלים
- **שלבים**: 500,000

### Stages 3–8 — "חטיבת הביניים" (2026-04-01 → 04-14)
- מעבר לארכיטקטורת Bitboard
- אופטימיזציה של מסכת המהלכים החוקיים
- ייצוב self-play ראשוני
- **שלבים כולל**: ~5,000,000

### Stage 9 — Self-Play League (2026-04-15 → 04-19)
- **יריב**: קלונים של עצמו (מתעדכן בזמן אמת)
- **שלבים**: 3,000,000
- **ממצא**: מצוין נגד עצמו, מאוד חלש נגד מנוע אמיתי

### Stage 10 — League Play (2026-04-20 → 04-26)
- **יריב**: ליגה דינמית (גרסאות היסטוריות + עצמו)
- **ארכיטקטורה**: `SubprocVecEnv` — מקבילות אמיתית
- **שלבים**: 4,000,000

### Stage 11 — Alpha-Beta Punisher (2026-04-27 → 04-29)
- **יריב**: 30% Alpha-Beta depth-1 + 70% ליגה
- **גמול**: Sparse terminal
- **ממצא**: הסוכן מתחיל לנצל את depth-1 (exploit!)

### Peter Local — "עיגון טקטי" (2026-05)
- **יריב**: Peter — מנוע שחמט Alpha-Beta מקומי
- **תוצאה הטובה**: `peter_local_v20` מנצח Peter d2 100% (20/0/0)
- **גילוי קריטי**: מודל ה-League שאימנו ידפוק Peter d2 **אפס פעמים** — self-play לא = חוזק אמיתי

```
Self-play strength ≠ Real strength
```

### "Strong" — 12 שעות (2026-06-03)

| הגדרה | פרטים |
|--------|--------|
| **חימום** | `peter_local_v20` |
| **סביבות** | 8 — 3× Peter d2 + 5× strong self-play |
| **גמול** | Sparse terminal |
| **שלבים** | 6,356,992 (~11.5 שעות) |

**תוצאות**:
- vs Peter d2: **24/0/0** (מושלם) ✅
- vs Peter d3: **0/16** (קיר!) ❌

**בעיה שנחשפה**: הסוכן מנצח **רק** דרך ה-"king-rush exploit" — 4 מהלכים לכידת מלך. נגד Peter d3 שמגן על מלכו, האסטרטגיה כושלת לחלוטין.

---

### v2 — מודל כללי (לא-exploit)

#### האבחנה של הבעיה

גילינו 3 גורמים שגרמו ל-PPO ללמוד exploit במקום משחק אמיתי:

| גורם | ההשפעה | הפתרון ב-v2 |
|------|---------|-------------|
| **Opponent monoculture** | PPO לומד לנצל את *אותו* יריב קבוע | Pool של יריבים שונים |
| **Fixed start position** | אפשר לשנן פתיחה קבועה | 40% מהאפיזודות מתחילות אחרי k מהלכים אקראיים |
| **Dense reward** | הסוכן אוסף נקודות, לא מנצח | Sparse terminal בלבד |

#### Pool Environment (`duck_env_v2.py`)

```python
DEFAULT_POOL_WEIGHTS = {
    'peter_d1':    0.20,   # King-rush defense
    'peter_d2':    0.25,   # General play
    'peter_d3':    0.05,   # Wall (rare but present)
    'sp_latest':   0.25,   # Self-play vs latest
    'sp_hist':     0.15,   # Historical checkpoints
    'random':      0.10,   # Basic coverage
}

# 40% אפיזודות מתחילות אחרי k מהלכים אקראיים (k=4..16)
if random() < 0.4:
    for _ in range(randint(4, 16)):
        make_random_legal_move()
```

#### תוצאות v2

| מדד | v2_final |
|-----|---------|
| vs Peter d2 | **19/1/0 = 95%** ✅ |
| vs Peter d3 | 0/20/0 = 0% ❌ |
| Anchor Elo | ~1025 |
| Entropy collapse? | לא! (glided down → 0.71 explained variance) |
| King-rush exploit? | לא! (מהלכים מגוונים מהתחלות אקראיות) |

**Blind spot שנגלה**: הסוכן מפסיד נגד Greedy bot (~3/9) למרות שמנצח Peter d2. Greedy לא היה ב-pool! — לא-טרנסיטיביות קלאסית ב-RL.

---

### antiexploit_v2 (Branch: `antiexploit_v2`)

שלב תיקון שמתמקד ב-3 exploit ספציפיים:

| Exploit | הבעיה | הפתרון |
|---------|--------|--------|
| **Repetitive opening** | אותה פתיחה בכל משחק | Entropy schedule 0.06→0.02 + opening randomization |
| **Weak duck placement** | הברווז מונח אקראית | `duck_placement_bonus` בגמול |
| **Endgame collapse** | קריסה בסוף משחק | `max_episode_plies=300` + step penalty |

**מדידה**: `eval_antiexploit.py` — מודד את 3 ה-exploits ספציפית, לא רק W/L/D.

---

## 9. בעיות שנתגלו בדרך

### בעיה 1: King-Rush Exploit

**מה קרה**: הסוכן למד לסיים משחקים ב-4 מהלכים — הגנה על מלך לא מצויינת Peter d1/d2.

```
מהלך 1: Knight f3    (מאיים על מלך e8)
מהלך 2: Duck to f6  (חוסם מילוט)
מהלך 3: Knight xe8  (לכידת מלך → ניצחון!)
```

**למה PPO למד את זה**: קיצור דרך מדהים — ניצחון קבוע ב-4 מהלכים נגד Peter d1/d2.
**הבעיה**: Peter d3 מגן על המלך בצעד שלישי. בלי ה-exploit, הסוכן לא יודע לשחק.

### בעיה 2: Self-Play Overfit

**מה קרה**: מודלים שאומנו רק נגד עצמם ניצחו 100% בפנים, הפסידו 100% נגד Peter.

```
Stage 9/10 vs self-play:   WIN RATE = 99%
Stage 9/10 vs Peter d2:    WIN RATE = 0%
```

**לקח**: Self-play מנורמל לאיזון פנימי אבל לא בונה חוזק אמיתי נגד יריב חיצוני.

### בעיה 3: Value Head Saturation

**מה קרה**: עם Dense Reward, ראש הערך היה: `V(initial) = +3.9` → `tanh(3.9) ≈ 0.999`.

**המשמעות**: ראש הערך פרש לגמרי — הוא מייצג "כמה reward מצטבר אצבר" לא "מה סיכויי הניצחון שלי".

**ההשפעה על החיפוש**: ניסינו Alpha-Beta עם ראש הערך להערכת עלים → **תוצאה: 0% vs d2** (היה 95% בלי חיפוש).

---

## 10. חיפוש בזמן ריצה — Inference-Time Search

### `search.py` — Alpha-Beta Tree Search

כתבנו Alpha-Beta search שמכסה את שני השלבים (כלי + ברווז):

```
Tree structure:
  piece-move node
      └── duck-move node
              └── opponent piece-move node
                      └── opponent duck-move node
```

**גיזום (Branching control)**: כדי שה-Duck Chess לא יפוצץ את העץ:
- Top-K מהלכי כלי לפי policy prior
- Top-K מיקומי ברווז = policy prior + heuristics (חסימת מהלך הטוב ביותר של היריב)

### תוצאות `search.py`

| הגדרה | vs Peter d2 | vs Peter d3 |
|--------|------------|------------|
| Raw policy | **19/1 = 95%** | 0/20 = 0% |
| + search mode=best (value-argmax) | **0/20 = 0%** ❌❌ | 0/20 = 0% |
| + search sample-veto margin=5 | ~95% | 0% |

**גילוי מדהים**:

```
mode=best (תמיד לפי ראש הערך) → 0% vs d2   ← מחוסל לגמרי!
mode=veto margin=5 (defer to policy) → 100% vs d2
```

**המסקנה הפרויקטלית**:
> ראש הערך מיועד **להעריך** — לא **לבחור**.
> Value-greedy זורק את כל כישורי הבחירה של ה-Policy.

**הסיבה הטכנית**: ב-quiet positions, כל המהלכים מקבלים `V ≈ +0.6..+0.73` — פס צר שראש הערך לא יכול לדרג. ה-noise שלו גורם ל-override של מהלכים מנצחים.

---

## 11. MCTS — AlphaZero Style

### מה זה MCTS?

**Monte Carlo Tree Search** — חיפוש עץ שמשלב:
- **Exploration**: ניסוי מהלכים לא-מוכרים
- **Exploitation**: מיקוד במהלכים שהוכיחו ערך גבוה
- **Policy Prior**: הרשת מנחה את החקירה
- **Value Leaf**: הרשת מעריכה עלים (לא random rollout)

### PUCT Selection Formula

```
PUCT(a) = Q(a) + c_puct × P(a) × √N_total / (1 + N(a))

כאשר:
  Q(a) = W(a) / N(a)     — ממוצע ערך (exploitation)
  P(a)                   — prior מה-policy (כיוון חקירה)
  N(a)                   — ביקורים בפעולה a
  c_puct = 1.5           — איזון exploration/exploitation
```

### Duck Chess Factoring (החידוש שלנו)

הבעיה: ב-Duck Chess כל "תור" הוא **שני שלבים** (כלי + ברווז). MCTS סטנדרטי לא יודע לטפל בזה.

**הפתרון**: Node = (מצב, שלב) — כל node הוא **חצי-תור**:

```
Root (move_piece phase)
    ├── Piece move A → Node_A (move_duck phase)
    │       ├── Duck to x1 → Node_A1 (move_piece, opponent)
    │       └── Duck to x2 → Node_A2 (move_piece, opponent)
    └── Piece move B → Node_B (move_duck phase)
            └── ...
```

**תוצאה**: branching נשאר ~25 (piece) ו-~55 (duck) במקום 225,000 combined.

### קוד PUCT הליבה (`mcts.py`):

```python
def _simulate(self, node):
    """PUCT simulation — returns value from node.to_move perspective."""
    total_N = max(1.0, node.N.sum())
    
    # Q + U: ניצול + חקירה
    Q = np.where(node.N > 0, node.W / node.N, 0.0)
    U = self.c_puct * node.P * sqrt(total_N) / (1 + node.N)
    
    best_action = node.actions[argmax(Q + U)]
    child = self._apply(node.engine, best_action)
    child_val = self._simulate(child)
    
    # הפוך סימן רק כשהצד משתנה (piece→duck = אותו צד!)
    v = child_val if child.to_move == node.to_move else -child_val
    
    node.N[best_idx] += 1
    node.W[best_idx] += v
    return v
```

### King Capture Prior Floor

```python
# הרשת נותנת prior ≈ 0 ללכידת מלך (נדיר בנתוני אימון)
# PUCT לעולם לא יחקור אותה → תת-אופטימלי קריטי!
for i, action in enumerate(kept_actions):
    if captures_king(action):
        priors[i] = max(priors[i], 1.0)  # floor אגרסיבי
```

**בלי זה**: MCTS יתעלם מלכידת מלך זמינה כי ה-prior = 0.

### תוצאות MCTS

| הגדרה | vs Peter d2 | vs Peter d3 |
|--------|------------|------------|
| Raw policy | ~90% (19/1) | 0% (0/20) |
| Alpha-Beta mode=best | **0%** ❌ | 0% |
| **MCTS sims=200** | **100% (12/0)** ✅✅ | 0% (0/12) |
| MCTS sims=1200 | 100% | 0% (0/16) |
| מהירות | ~0.9s/turn | — |

**הלקח**: PUCT MCTS — policy מנחה את *מה* לחקור, value מעריך *עלים*, ממוצע על סימולציות. זו הדרך היחידה שעבדה.

---

## 12. Value Distillation — זיקוק ראש הערך

### הבעיה

MCTS עם ראש הערך של PPO (Dense reward) **לא עבד** — sign accuracy = **0.65** (כמעט כמטבע).

PPO critic לומד: "כמה reward אצבור מכאן?" — לא "מה סיכויי הניצחון שלי?"

### הפתרון: Supervised Regression על ראש הערך

**שלב 1: `gen_value_data.py`** — יצירת דאטאסט

```
שחק N משחקים עם המדיניות הנוכחית
עבור כל מצב ב-piece-phase:
    שמור (observation, תוצאת_משחק)  # +1 / -1 / 0
```

**שלב 2: `finetune_value.py`** — אימון ראש הערך בלבד

```python
# ה-policy קפוא לחלוטין (byte-for-byte identical אחרי)
# רק ראש הערך מתעדכן:
loss = MSE(predicted_value, actual_outcome)
```

**תוצאות**:

| מדד | לפני | אחרי |
|-----|------|------|
| Value Sign Accuracy | 0.65 | **0.98** |
| V(initial position) | +3.9 (saturated) | +0.34 (calibrated) |
| MCTS vs Peter d2 | ~0% | **100%** |

> **ראש ערך מכוייל** = ראש ערך שמייצג הסתברות ניצחון אמיתית.

**Dataset**: 12,093 מיקומים מ-N משחקים נגד Peter d2/d3.

---

## 13. Expert Iteration (ExIt) — הלולאה של AlphaZero

### הרקע

AlphaZero (Google DeepMind, 2017) למד שחמט ממאפס בלי ידע אנושי:
1. **Self-play עם MCTS** → נתוני אימון
2. **Train** policy + value על הנתונים
3. **רשת חזקה יותר** → MCTS טוב יותר → **לולאה**

אנחנו מימשנו את הלולאה הזו עבור Duck Chess.

### הלולאה של ExIt (Expert Iteration)

```
Iteration N:
  ┌─────────────────────────────────────────────────────┐
  │  1. GENERATE:                                        │
  │     שחק X משחקי self-play + Y משחקים vs Peter       │
  │     בכל מהלך: הרץ MCTS(sims=300)                    │
  │     שמור: (obs, π_mcts, z_outcome) לכל מיקום        │
  │                                                      │
  │  2. TRAIN:                                           │
  │     Loss = CE(policy, π_mcts) + MSE(value, z)       │
  │     (Sliding window — 4 iterations אחרונות)         │
  │                                                      │
  │  3. EVALUATE with MCTS:                              │
  │     vs Peter d1 (rush) + d2 (tactical) + d3 (wall) │
  │                                                      │
  │  4. ADVANCE:                                         │
  │     current ← new model (always-accept)              │
  │     best ← update if d1_score + d2_score improved   │
  └─────────────────────────────────────────────────────┘
```

### MCTS Visit Counts כ-Policy Target

**רגיל**: הרשת לומדת מ-argmax(MCTS) — רק המהלך הטוב ביותר.

**AlphaZero style**: לומדת מ-**visit distribution** — כמה פעמים MCTS ביקר בכל מהלך:

```python
# π = normalized visit counts מה-root של MCTS
π = node.N / node.N.sum()

# Loss ל-policy head:
policy_loss = CrossEntropy(policy_probs, π)

# הרשת לומדת את הביטחון של MCTS, לא רק את ה-argmax!
```

זה חלק קריטי: המידע ב-visit distribution עשיר יותר מ-argmax בלבד.

### Duck Placement Target

**חידוש חשוב**: אנחנו לומדים גם את **distribution של מיקום הברווז**:

```python
# choose_turn_with_targets() מחזיר:
targets = [
    (piece_obs, piece_actions, piece_visit_probs, side),  # piece node
    (duck_obs,  duck_actions,  duck_visit_probs,  side),  # duck node
]
```

זה מה שמתקן את ה-"Weak Duck Placement" exploit — הרשת לומדת **באיזה מיקום** להניח את הברווז.

### Temperature Sampling

```python
# במהלך generation — sampling עם temperature>0
# מונע קריסה לאותה פתיחה בכל משחק:
π_temp = π ** (1/temperature)
π_temp /= π_temp.sum()
action = sample(π_temp)

# בזמן evaluation — argmax (temperature=0)
```

### Sliding Replay Window

```python
# שמירת נתונים מ-4 iterations אחרונות
data_window.extend(files_this_iteration)
data_window = data_window[-4:]  # sliding window
```

מונע catastrophic forgetting — הרשת לומדת מניסיון עדכני בלי לשכוח לחלוטין.

### קוד הלולאה (`run_exit.py`):

```python
for it in range(iters):
    # 1. Generate
    self_data = generate(current_model, self_games, sims=300, opponent="self")
    peter_data = generate(current_model, peter_games, sims=300, opponent="peter")
    
    # 2. Train
    train_exit(current_model, data_window, output_path, epochs=10)
    
    # 3. Evaluate
    r1 = evaluate(new_model, games=16, peter_depth=1, engine="mcts")
    r2 = evaluate(new_model, games=16, peter_depth=2, engine="mcts")
    r3 = evaluate(new_model, games=16, peter_depth=3, engine="mcts")
    
    # 4. Advance (always-accept) + guard best
    current = new_model
    if r1.score + r2.score > best_score:  # human-strength first
        save_as_best()
```

**למה always-accept?** (בניגוד ל-AlphaZero שמחליף רק אם חזק יותר)
- עם מעט נתונים, הערכה רועשת — להחמיר מתי מחליפים = bottleneck
- Sliding window מגן מרגרסיה גדולה

---

## 14. תוצאות ודירוג המודלים

### טבלת המודלים הסופית

| מודל | vs Peter d1 | vs Peter d2 | הערות |
|------|:-----------:|:-----------:|-------|
| `ranked/1_champion.zip` | **1.00** (20/0/0) | **1.00** (20/0/0) | ExIt iter1 מבסיס חזק — **הטוב ביותר** |
| `ranked/2_allrounder.zip` | 0.80 (12/3/0) | 0.67 (10/5/0) | v2 policy + value head — מאוזן |
| `ranked/3_aggressive.zip` | 0.46 | 1.00 (20/0/0) | strong_final — מושלם vs d2, חלש vs d1 |
| `ranked/4_classic.zip` | ~0.27 | ~0.55 | v2 policy מקורי, בלי value head |
| `ranked/5_safe.zip` | חלש | חלש | antiexploit_v2 — ללא exploit אבל פסיבי |

**d1** = Peter depth-1 (king-rush, כמו בני אדם תוקפניים)
**d2** = Peter depth-2 (משחק פוזיציונלי)
**d3** = **0 ניצחונות** בכל המודלים — הקיר הפתוח

### ציר הזמן של שיפור (vs Peter d2)

```
Stage 1:          ~0%
Stage 9/10:       ~0%   ← self-play fallacy!
peter_local_v20:  100% (with king-rush exploit)
strong_final:     100% (with exploit)
v2_final (raw):   95%  (NO exploit, general play)
v2_value + MCTS:  100% (general play + search) ← CURRENT BEST
```

---

## 15. שיעורים מרכזיים שנלמדו

### לקח 1: Self-play ≠ חוזק אמיתי

```
Self-play models vs Peter d2: 0/20
Peter-trained models vs Peter d2: 20/20
```
מדד הכוח האמיתי: **eval_vs_peter.py** — לא self-play win rate.

---

### לקח 2: Dense Reward הורס את ראש הערך

```
Dense reward V head sign-accuracy: 0.65 (= random!)
Sparse reward V head sign-accuracy: 0.71+
After distillation sign-accuracy:  0.98
```
בלי sparse reward, MCTS לא עובד — ה-value head פשוט לא יכול לדרג מצבים.

---

### לקח 3: Policy בוחרת, Value מעריכה

```
Value-argmax (mode=best):     95% → 0%  ← catastrophic!
PUCT MCTS (policy priors):    95% → 100% ← improvement!
```
**Value-greedy זורק את כל כישורי ה-Policy**. רק MCTS שמשתמש ב-policy כ-prior ובvalue להערכת עלים עובד.

---

### לקח 4: Opponent Pool מנצח Opponent Monoculture

```
Training vs single fixed Peter d2 → learns to exploit it
Training vs pool {d1, d2, d3, self, hist, random} → general play
```
מגוון יריבים = מדיניות כללית. יריב יחיד = shortcut exploit.

---

### לקח 5: Action Masking הוא Correctness Invariant

```
Without masking: agent can select illegal moves
With masking:    only legal moves possible — always
```
זה לא אופטימיזציה — זה נכונות. בלי masking, הסוכן יכול "לנצח" על-ידי מהלכים לא-חוקיים.

---

### לקח 6: הברווז הוא נשק, לא הפרעה

```
Duck placement after piece move:
  Bad duck:  blocks own piece's retreat
  Good duck: blocks opponent's best response
  Great duck: closes off king escape routes
```
ExIt לימד את הרשת להניח ברווז לאסטרטגית על-ידי רישום MCTS duck visit distribution.

---

## 16. בעיות פתוחות

### קיר Peter Depth-3

```
כל מודל vs Peter d3: 0 ניצחונות
MCTS sims=200:  0/12 vs d3
MCTS sims=1200: 0/16 vs d3  (6x יותר סימולציות — אותה תוצאה)
```

**מה Peter d3 עושה שונה**: מגן על המלך בצעד 3 כנגד ה-king-rush. זה מספיק לשבור כל אסטרטגיה שנלמדה עד כה.

**הדרך הריאליסטית**: ExIt iterations נוספות עם:
- יותר נתוני self-play עם MCTS
- Peter d3 ב-generation pool
- ייתכן שנחוץ ארכיטקטורת רשת גדולה יותר

### Greedy Bot Blind Spot

```
v2_final vs greedy bot: 33% (3/9)
למרות:
v2_final vs Peter d2:   95%
```

לא-טרנסיטיביות קלאסית ב-RL. הפתרון: הוסף GreedyOpponent ל-training pool.

---

## נספח: מבנה הקוד

### קבצים מרכזיים

```
DuckChess_Game/Logic/
├── logic.py              # GameLogicMixin — Hub class
├── observation_encoder.py # Board → 19×8×8 tensor
├── action_masker.py       # 4096 action space + masking
├── turn_manager.py        # King capture win detection
├── endgame_checker.py     # Fowling + 50-move draw
└── bitboard_manager.py    # Fast 64-bit board representation

DuckChess_Game/SBThree/
├── mcts.py               # DuckMCTS — AlphaZero PUCT
├── search.py             # Alpha-Beta (failed approach)
├── gen_mcts_data.py      # ExIt data generation
├── train_exit.py         # ExIt supervised training
├── run_exit.py           # ExIt loop controller
├── gen_value_data.py     # Value distillation data
├── finetune_value.py     # Value head regression
├── eval_vs_peter.py      # Ground-truth evaluation
└── base/
    ├── env_base.py        # Base Gymnasium environment
    ├── reward_calculator.py # TerminalReward / ShapedReward
    └── opponent_strategy.py # Pool sampling logic
```

### Gymnasium Environment Interface

```python
class BaseDuckChessEnv(gym.Env):
    observation_space = spaces.Box(0, 1, shape=(19, 8, 8))
    action_space = spaces.Discrete(4096)
    
    def step(self, action):
        # Apply action to engine
        # Get opponent's response
        # Return (obs, reward, terminated, truncated, info)
    
    def action_masks(self):
        # Return boolean array of 4096 legal actions
```

---

*תיעוד זה נכתב לקראת הגנת הפרויקט. כל המספרים מאומתים מול הקוד ומקבצי הלוג.*

*פרויקט Duck Chess AI — Afek | Afeka College of Engineering | 2026*
