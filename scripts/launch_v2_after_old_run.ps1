# launch_v2_after_old_run.ps1 — waits for the old train_real run to finish,
# then cleans smoke-test artifacts and launches the v2 training run (PLAN_V2.md Step 3).
# Launched detached so it survives the Claude Code session.
param(
    [int]$WaitPid = 11984,
    [double]$Hours = 12.0
)

$repo = "C:\Users\afiks\Documents\Afik\Afeka\duck_chess-master\duck_chess-master"
Set-Location $repo
$log = Join-Path $repo "logs\v2_launcher.log"
New-Item -ItemType Directory -Force (Join-Path $repo "logs") | Out-Null

function Log($msg) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $msg" | Out-File -Append -Encoding utf8 $log }

Log "Launcher started. Waiting for old training run (PID $WaitPid) to exit."
$proc = Get-Process -Id $WaitPid -ErrorAction SilentlyContinue
if ($proc) {
    Wait-Process -Id $WaitPid -ErrorAction SilentlyContinue
    Log "Old run exited."
    Start-Sleep -Seconds 60   # let its final eval/file writes settle
} else {
    Log "PID $WaitPid not running - launching immediately."
}

# Clean smoke-test artifacts so the real run starts with clean version numbering
Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $repo "models\duck_ppo\v2\*.zip")
Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $repo "logs\v2_progress.csv")
Log "Smoke artifacts cleaned. Launching v2 training for $Hours hours."

$py = Join-Path $repo ".venv\Scripts\python.exe"
Start-Process -FilePath $py `
    -ArgumentList "-m", "DuckChess_Game.SBThree.train_peter_v2", "--hours", "$Hours", "--n-envs", "8" `
    -WorkingDirectory $repo `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $repo "logs\v2_train.log") `
    -RedirectStandardError  (Join-Path $repo "logs\v2_train_err.log")
Log "v2 training launched (logs/v2_train.log, logs/v2_progress.csv)."
