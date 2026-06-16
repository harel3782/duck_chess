# run_full_build.ps1 — unattended "build the best model" pipeline.
#
# Phase A: antiexploit_v2 corrective train, 8M steps (~20-24h on this CPU).
#          This is the long (>=8h) training run. Produces ax_final.zip.
# Phase C: Expert Iteration loop (run_exit) on ax_final — generate MCTS games,
#          retrain policy+value, eval vs Peter d2/d3, iterate. Produces
#          models/duck_ppo/exit/exit_best.zip (the strongest model).
#
# Fully unattended: launched detached via Start-Process, needs no further
# permissions. Resumable — both phases checkpoint to disk continuously.
# To stop after Phase A only: kill the python.exe processes (see fullbuild_master.log
# for the "[A] train done" line first), or Stop-Process -Name python -Force.

$ErrorActionPreference = "Continue"
$root = "C:\Users\afiks\Documents\Afik S\Afik\Afeka\duck_chess-master\duck_chess-master"
Set-Location $root
$py = Join-Path $root ".venv\Scripts\python.exe"
$master = Join-Path $root "logs\fullbuild_master.log"

"=== full build started $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" | Out-File -Append -Encoding utf8 $master

# ---- Phase A: long corrective training ------------------------------------ #
"[A] antiexploit_v2 8M train start $(Get-Date -Format 'HH:mm:ss')" | Out-File -Append -Encoding utf8 $master
& $py -u -m DuckChess_Game.SBThree.train_antiexploit_v2 --steps 8000000 --n-envs 8 --ckpt-every 500000 *>> (Join-Path $root "logs\fullbuild_train.log")
$rcA = $LASTEXITCODE
"[A] train done rc=$rcA $(Get-Date -Format 'HH:mm:ss')" | Out-File -Append -Encoding utf8 $master

# ---- Phase C: Expert Iteration on the trained base ------------------------ #
$base = Join-Path $root "models\duck_ppo\antiexploit_v2\ax_final.zip"
if (-not (Test-Path $base)) {
    $base = Join-Path $root "models\duck_ppo\antiexploit_v2\ax_latest.zip"  # fallback if final missing
}
if ((Test-Path $base) -and ($rcA -eq 0)) {
    "[C] ExIt start (base=$base) $(Get-Date -Format 'HH:mm:ss')" | Out-File -Append -Encoding utf8 $master
    & $py -u -m DuckChess_Game.SBThree.run_exit --base $base --out-dir (Join-Path $root "models\duck_ppo\exit") `
        --iters 5 --games 400 --sims 200 --workers 8 --peter-frac 0.30 `
        --eval-games 12 --eval-sims 200 *>> (Join-Path $root "logs\fullbuild_exit.log")
    "[C] ExIt done rc=$LASTEXITCODE $(Get-Date -Format 'HH:mm:ss')" | Out-File -Append -Encoding utf8 $master
} else {
    "[C] SKIPPED (base missing or Phase A failed, rc=$rcA)" | Out-File -Append -Encoding utf8 $master
}

"=== full build finished $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" | Out-File -Append -Encoding utf8 $master
