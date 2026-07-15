$ErrorActionPreference = "Stop"
$Proje = Split-Path -Parent $MyInvocation.MyCommand.Path
$DurumDosyasi = Join-Path $Proje "servisler.json"

if (-not (Test-Path $DurumDosyasi)) {
    Write-Host "Calisan Kantin Radar servis kaydi bulunamadi."
    exit 0
}

$Servisler = Get-Content $DurumDosyasi -Raw | ConvertFrom-Json
@($Servisler.dashboard_pid, $Servisler.worker_pid) | ForEach-Object {
    $Islem = Get-Process -Id $_ -ErrorAction SilentlyContinue
    if ($Islem) {
        Stop-Process -Id $_
    }
}

Remove-Item -LiteralPath $DurumDosyasi
Write-Host "Kantin Radar durduruldu."
