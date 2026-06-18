# run_48h.ps1 — autonomous 48-hour ExIt builder.
#
# Survives crashes (loops + resumes) and reboots (re-launched by the Startup hook
# on logon). Each iteration resumes from the latest exit_v* checkpoint, so an
# interruption costs at most ONE iteration. Needs no runtime permissions.
#
# Window is 48h of WALL-CLOCK from first launch (downtime counts against it).
# Stop early: delete logs\run48_deadline.txt and create logs\run48.done, then
# Stop-Process -Name python -Force.

$ErrorActionPreference = "Continue"
$root = "C:\Users\afiks\Documents\Afik S\Afik\Afeka\duck_chess-master\duck_chess-master"
Set-Location $root
$py        = Join-Path $root ".venv\Scripts\python.exe"
$deadlineF = Join-Path $root "logs\run48_deadline.txt"
$lockF     = Join-Path $root "logs\run48.lock"
$doneF     = Join-Path $root "logs\run48.done"
$trainLog  = Join-Path $root "logs\run48_train.log"
$masterLog = Join-Path $root "logs\run48_master.log"
New-Item -ItemType Directory -Force -Path (Join-Path $root "logs") | Out-Null

# Finished the 48h window already? (Startup hook becomes a no-op afterwards.)
if (Test-Path $doneF) { exit }

# Single instance: if a previous wrapper is still alive, do nothing.
if (Test-Path $lockF) {
    $old = Get-Content $lockF -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($old -and (Get-Process -Id ([int]$old) -ErrorAction SilentlyContinue)) { exit }
}
$PID | Out-File -Encoding ascii $lockF

# Set the 48h deadline once; reboots keep the same window.
if (-not (Test-Path $deadlineF)) {
    (Get-Date).AddHours(48).ToString('o') | Out-File -Encoding ascii $deadlineF
}
$deadline = [datetime]::Parse((Get-Content $deadlineF | Select-Object -First 1))
"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] wrapper start (pid $PID); deadline $deadline" |
    Out-File -Append -Encoding utf8 $masterLog

while ((Get-Date) -lt $deadline) {
    "[$(Get-Date -Format 'HH:mm:ss')] launch ExIt iteration (resume)" | Out-File -Append -Encoding utf8 $masterLog
    & $py -u -m DuckChess_Game.SBThree.run_exit --resume `
        --base "models/duck_ppo/strong/strong_final.zip" `
        --out-dir "models/duck_ppo/exit2" `
        --iters 1 --games 150 --sims 200 --workers 8 `
        --peter-frac 0.40 --peter-depths 1 2 --eval-games 12 --eval-sims 200 *>> $trainLog
    "[$(Get-Date -Format 'HH:mm:ss')] iteration returned rc=$LASTEXITCODE" | Out-File -Append -Encoding utf8 $masterLog
    Start-Sleep -Seconds 10   # avoid a tight crash loop
}

"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] 48h reached -- DONE" | Out-File -Append -Encoding utf8 $masterLog
"done $(Get-Date -Format o)" | Out-File -Encoding ascii $doneF
Remove-Item $lockF -ErrorAction SilentlyContinue
