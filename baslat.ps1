$ErrorActionPreference = "Stop"
$Python = "C:\Users\alitu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Proje = Split-Path -Parent $MyInvocation.MyCommand.Path
$ServisDosyasi = Join-Path $Proje "servisler.json"

if (Test-Path $ServisDosyasi) {
    $Mevcut = Get-Content $ServisDosyasi -Raw | ConvertFrom-Json
    $DashboardHazir = Get-Process -Id $Mevcut.dashboard_pid -ErrorAction SilentlyContinue
    $WorkerHazir = Get-Process -Id $Mevcut.worker_pid -ErrorAction SilentlyContinue
    if ($DashboardHazir -and $WorkerHazir) {
        Write-Host "İhalex zaten çalışıyor: http://127.0.0.1:8501"
        exit 0
    }
}

$Dashboard = Start-Process -FilePath $Python `
    -ArgumentList "-m", "streamlit", "run", "site_web.py", "--server.port", "8501", "--server.address", "127.0.0.1", "--server.headless", "true" `
    -WorkingDirectory $Proje -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $Proje "streamlit.log") `
    -RedirectStandardError (Join-Path $Proje "streamlit-error.log")

$Worker = Start-Process -FilePath $Python `
    -ArgumentList "worker.py", "--parallel", "6" `
    -WorkingDirectory $Proje -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $Proje "worker-stdout.log") `
    -RedirectStandardError (Join-Path $Proje "worker-stderr.log")

@{
    dashboard_pid = $Dashboard.Id
    worker_pid = $Worker.Id
} | ConvertTo-Json | Set-Content -Path $ServisDosyasi -Encoding UTF8

Write-Host "İhalex başlatıldı: http://127.0.0.1:8501"
Write-Host "Tam tarama saatleri: 11:59 ve 23:59"
