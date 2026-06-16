# run_resume_build.ps1 — resume the full build after the 2026-06-15 restart.
#
# Phase A resumes from ax_latest (5.0M-step checkpoint) for the remaining ~3M
# steps, continuing the entropy schedule (~0.035 -> 0.02) so it picks up where
# it left off. Then Phase C (ExIt) on the finished ax_final, as before.
#
# Detached/unattended. If the machine restarts again, ax_latest is the new
# resume point — just re-run this with --base ax_latest and adjusted --steps.

$ErrorActionPreference = "Continue"
$root = "C:\Users\afiks\Documents\Afik S\Afik\Afeka\duck_chess-master\duck_chess-master"
Set-Location $root
$py = Join-Path $root ".venv\Scripts\python.exe"
$master = Join-Path $root "logs\fullbuild_master.log"
$base = Join-Path $root "models\duck_ppo\antiexploit_v2\ax_latest.zip"

"=== RESUME build started $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') (base=ax_latest ~5.0M) ===" | Out-File -Append -Encoding utf8 $master

# ---- Phase A (resume): 3M more steps from the 5.0M checkpoint -------------- #
"[A-resume] start $(Get-Date -Format 'HH:mm:ss')" | Out-File -Append -Encoding utf8 $master
& $py -u -m DuckChess_Game.SBThree.train_antiexploit_v2 --base $base --steps 3000000 `
    --n-envs 8 --ckpt-every 250000 --ent-start 0.035 --ent-end 0.02 *>> (Join-Path $root "logs\fullbuild_train.log")
$rcA = $LASTEXITCODE
"[A-resume] done rc=$rcA $(Get-Date -Format 'HH:mm:ss')" | Out-File -Append -Encoding utf8 $master

# ---- Phase C: Expert Iteration on the finished base ----------------------- #
$final = Join-Path $root "models\duck_ppo\antiexploit_v2\ax_final.zip"
if (-not (Test-Path $final)) { $final = Join-Path $root "models\duck_ppo\antiexploit_v2\ax_latest.zip" }
if ((Test-Path $final) -and ($rcA -eq 0)) {
    "[C] ExIt start (base=$final) $(Get-Date -Format 'HH:mm:ss')" | Out-File -Append -Encoding utf8 $master
    & $py -u -m DuckChess_Game.SBThree.run_exit --base $final --out-dir (Join-Path $root "models\duck_ppo\exit") `
        --iters 5 --games 400 --sims 200 --workers 8 --peter-frac 0.30 `
        --eval-games 12 --eval-sims 200 *>> (Join-Path $root "logs\fullbuild_exit.log")
    "[C] ExIt done rc=$LASTEXITCODE $(Get-Date -Format 'HH:mm:ss')" | Out-File -Append -Encoding utf8 $master
} else {
    "[C] SKIPPED (final missing or Phase A failed rc=$rcA)" | Out-File -Append -Encoding utf8 $master
}

"=== RESUME build finished $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" | Out-File -Append -Encoding utf8 $master
