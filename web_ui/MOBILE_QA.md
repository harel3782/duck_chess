# Mobile QA Checklist — `web_ui/index.html`

Manual mobile pass for the Duck Chess web UI. Every item is specific to this
single-file app (FastAPI server + one `index.html`). Work top to bottom on a
real phone where possible; DevTools device emulation is fine for layout but
**cannot** catch the iOS Safari toolbar / `100dvh` and sticky-hover issues —
do those on a real device.

## Test setup

- [ ] Server restarted **after** the `/assets` mount was added (`uvicorn.run` does
      not hot-reload): `python web_ui/server.py` → expect `[Duck Chess] python: …\.venv\…`.
- [ ] Opened over LAN on a real phone (`http://<dev-machine-ip>:7890`), not just localhost.
- [ ] **Network reachable** — the 12 piece sprites load from external Wikimedia URLs
      (`IMG` map, lines ~743–756). Offline / blocked CDN ⇒ pieces vanish even though
      the board works. Only the **duck** is local (`/assets/pieces/duck.png`).
- [ ] Hard-refresh (`Ctrl/Cmd+Shift+R`) after each redeploy — the old page cached a
      404 for the duck image.
- [ ] Test at **390px** (iPhone 14) **and 320px** (iPhone SE) widths. Expected board
      square `--sq`: ≈43.7px @390 (board ≈357px), ≈35.8px @320 (board ≈287px).
- [ ] Breakpoints in play: **≤860px** (sidebars stack under board) and **≤480px**
      (model select stacks, `.pname`/`.gn-model` hidden, board `--sq` shrinks).

---

## SCREENS

### 1. Splash / loading (`#splash`)
- [ ] Duck image loads (`/assets/pieces/duck.png`, line ~446) — not a broken-image icon.
- [ ] `#splash-text` "DuckChess" readable, centered, not clipped.
- [ ] `fade-out 2s` animation completes and splash is removed (does not block taps —
      `pointer-events:none`, `animationend` + 2200ms fallback).
- [ ] No horizontal scroll during the fade.
- [ ] Splash fully covers the viewport top-to-bottom (no auth screen peeking under it on tall phones).

### 2. Auth screen (`#screen-auth`)
- [ ] `.auth-logo` duck image loads (line ~453).
- [ ] Login / Sign-up `.auth-tab` toggle works on tap; active tab highlighted (gold).
- [ ] `.auth-card` (max-width 380px) centered, fits within 320px with side padding.
- [ ] Username/password `.field input` tappable; mobile keyboard does not cover the submit button (scroll up if needed — `#screen-auth` has `overflow-y:auto; max-height:100dvh`).
- [ ] No content clipped under the iOS top bar / notch.
- [ ] No horizontal scroll.
- [ ] `.auth-error` line displays without shifting layout.

### 3. Menu screen (`#screen-menu`)
- [ ] Top-bar `.logo` duck image loads (line ~483).
- [ ] Profile chip shows; at ≤480px `.pname` is hidden (only avatar + buttons remain) — verify it doesn't overflow the top bar.
- [ ] **Model select** (`#menu-model`) populated from `/api/models` (shows the configured default, not "Loading models…").
- [ ] **`.select-wrap` stacks full-width below its label at ≤480px** (`.model-pick` becomes a column); dropdown arrow `::after` stays aligned.
- [ ] No horizontal scroll at 390px **or 320px** (this was the main pre-fix break: `min-width:200px`).
- [ ] Color/mode chosen via the three `.menu-card`s: **Play as White**, **Play as Black**, **2 Players** — each tappable, full card is the tap target.
- [ ] Menu cards reflow to one column when narrow (`auto-fill, minmax(250px,1fr)`).
- [ ] `.menu-body` scrolls if content exceeds viewport; `#screen-menu` has `overflow-y:auto; max-height:100dvh` (no clip under bottom bar).
- [ ] "Saved Games" heading + list visible below the cards (see screen 6).
- [ ] Text readable without pinch-zoom (titles, `.mc-sub` descriptions).

### 4. Game screen (`#screen-game`)
- [ ] `.game-nav` logo duck image loads (line ~535, inline `font-size:1rem`).
- [ ] **Board renders** with all pieces (external sprites) **and the duck** (`.duck-svg`, `/assets/pieces/duck.png`, line ~952) once the duck is on the board.
- [ ] Board fits horizontally at 390px and 320px (no clipping of files a/h, no horizontal scroll).
- [ ] Coordinate labels (`.coord-file`/`.coord-rank`) legible at small `--sq`.
- [ ] At ≤860px: board moves to top (`order:-1`), then **left sidebar** (players + eval), then **right sidebar** (history + nav + undo) stack vertically; `.main` scrolls (`overflow-y:auto`).
- [ ] Player cards (`.player-card`) show names; **timers** (`.p-time`) tick and are readable; active card has gold border, opponent card dims/pulses (`.thinking`) during model move.
- [ ] `.turn-bar` + `.phase-pill` ("Move piece" / "Place duck") visible and update each phase.
- [ ] At ≤860px the "Opponent: <model>" `.gn-model` is hidden — verify nothing looks cut off mid-word.
- [ ] No content clipped under the iOS bottom toolbar (bottom sidebar / undo button reachable by scrolling).

### 5. Rules modal (`.modal-backdrop` / `.modal`)
- [ ] Opens from the `?` button (top bar) and from rules links.
- [ ] `.modal-head h2` duck icon loads (line ~635).
- [ ] Modal (max-width 540px, `max-height:86vh; overflow-y:auto`) scrolls internally on a short screen; the three rule rows all reachable.
- [ ] Sticky header stays pinned while scrolling rules.
- [ ] Closes via the `×` (`.modal-close`), backdrop tap, and `Esc`.
- [ ] No horizontal scroll inside the modal at 320px.

### 6. Saved games list (`#saved-list`)
- [ ] Empty state renders with duck placeholder image (line ~1409) + "No saved games yet" text.
- [ ] After saving a game, `.saved-game-card`s appear (newest first), each showing label, timestamp — result, and model label.
- [ ] Cards fit full-width with no horizontal overflow at 320px.
- [ ] "↻ Load & Review" and "🗑" (`.del-btn`) buttons reachable by thumb and not overlapping.

### 7. Game-over card (`.over-card`)
- [ ] `.over-icon` duck image loads (line ~645).
- [ ] Card (max-width 380px) centered, fits 320px.
- [ ] `.over-title` reflects outcome class (win = gold / lose = red / draw = blue) and the reason text matches (king capture / fowling / resign / 50-move draw / 2-player "White/Black wins").
- [ ] `.over-actions` buttons (rematch / menu) are full-width-ish and tappable; not clipped under bottom chrome.
- [ ] No horizontal scroll.

### 8. Replay mode
- [ ] Entered via "Load & Review" on a saved game.
- [ ] Replay control bar visible: ⏮ Prev / ▶ Play / Next ⏭ / Exit ✕ (`replayPrev`/`replayPlayPause`/`replayNext`/`exitReplay`).
- [ ] `#replay-move-num` updates as you scrub; board + **duck position** update per half-move snapshot.
- [ ] Control bar reachable by thumb (bottom of board area) and buttons don't wrap awkwardly at 320px.
- [ ] "Exit ✕" returns cleanly to the prior screen.

---

## INTERACTIONS

- [ ] **Tap to select piece → tap to move**: first tap highlights legal targets (`.vm`/`.vc` dots), second tap moves. No drag needed (handlers are `click` only).
- [ ] **No hover ghost**: after lifting your finger, the tapped square shows **no lingering brightness** (`.sq:hover` is gated behind `@media (hover:hover)`).
- [ ] **Duck placement tap**: in the duck phase, duckable squares (`.duckable` gold rings) are tappable; tapping an illegal square is rejected (stays in duck phase).
- [ ] **Dropdown closes on outside tap**: open `#menu-model`, tap elsewhere → native select closes; the custom outside-tap handler (`document` click, line ~1503) doesn't trap taps.
- [ ] **Resign** reachable (button in `.gn-actions` and/or `R` key — phone has no key, so the button must be tappable).
- [ ] **Undo** (`#btn-undo`) reachable — it sits below the history box in the right sidebar, which is at the **bottom** of the stacked mobile layout; verify you can scroll to it.
- [ ] **Save** button reachable and writes a game (then appears in the menu's saved list).
- [ ] **Replay scrubber usable with a thumb** — Prev/Next/Play buttons large enough and spaced so adjacent taps don't misfire.
- [ ] **Saved game load** opens replay; **delete** (`armDelete` → confirm → `/api/delete-game`) removes the card; the arm/confirm two-tap flow works on touch.
- [ ] History move list (`.history-box`) scrolls independently; tapping the "⏮ ⬅ ➡ ⏭" nav jumps moves and the board updates.

---

## KNOWN RISKS TO VERIFY

- [ ] **`100dvh` not clipped under iOS Safari toolbar** — `.screen` uses `height:100vh; height:100dvh`. On iOS Safari with the address bar showing, confirm the bottom of the **menu** and **game** screens (undo button, bottom sidebar) is reachable, not hidden behind the toolbar.
- [ ] **`#screen-auth` centering + overflow** — the auth card is vertically centered with `overflow-y:auto`. On a short landscape phone, confirm the top of a tall card isn't cut off and unreachable (flexbox-centering + overflow edge case).
- [ ] **`.select-wrap` stacks vertically at ≤480px** — model label on its own line, select full-width below it; re-confirm at exactly 480px, 390px, 320px.
- [ ] **Duck piece renders on board** — was broken (pointed at bare `duck.png` → 404); now `/assets/pieces/duck.png` via the `/assets` mount. Verify the live board shows the duck, not a broken-image glyph (requires a **server restart** to pick up the mount).
- [ ] **Favicon loads in the browser tab** — `<link rel="icon" href="../assets/pieces/duck.png">` (line 7) resolves to `/assets/pieces/duck.png`; check the tab/bookmark icon, not just the page.
- [ ] **No sticky hover highlight after tap on squares** — re-tap several squares quickly; none should retain the brightness filter once released (the whole point of the `@media (hover:hover)` wrap).
- [ ] **Tap targets ≥44px tall** — likely **below** 44px and worth flagging on touch:
  - `.btn` (~36px: `padding:9px` + 0.8125rem text),
  - history nav `.btn-ghost ⏮⬅➡⏭` (~28px: inline `padding:6px`),
  - `.logout-btn` (~26px: `padding:4px 8px`),
  - `select` (~36px), `.modal-close` `×`.
  Verify each is still reliably tappable; note any misfires.
- [ ] **External piece sprites** — confirm all 12 Wikimedia SVGs load over mobile data (not just wifi); a blocked CDN leaves the board pieceless while the duck (local) still shows.
