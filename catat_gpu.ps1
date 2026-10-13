# Catat pemakaian GPU tiap detik ke work\gpu_log.csv, untuk statistik_gpu.py.
# Jalankan di jendela PowerShell terpisah sebelum/selama proses, hentikan dengan Ctrl+C:
#   powershell -ExecutionPolicy Bypass -File catat_gpu.ps1
$log = Join-Path $PSScriptRoot "work\gpu_log.csv"
New-Item -ItemType Directory -Force (Split-Path $log) | Out-Null
Write-Host "Mencatat GPU ke $log (Ctrl+C untuk berhenti)"
while ($true) {
    $baris = nvidia-smi --query-gpu=timestamp,utilization.gpu,memory.used,memory.total,power.draw,temperature.gpu --format=csv,noheader,nounits
    Add-Content -Path $log -Value $baris -Encoding utf8
    Start-Sleep -Milliseconds 1000
}
