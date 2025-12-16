# ============================================
# AIWolf Docker Compose Startup Script
# Automatically saves logs to docker-logs/
# ============================================

param(
    [switch]$Multi,  # Use --profile multi
    [switch]$Build,  # Rebuild images
    [string]$Config1 = "./config/config_opr.yml",
    [string]$Config2 = "./config/config_opr_2.yml"
)

# Create timestamp for log file
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = "./docker-logs/${timestamp}.log"

# Set environment variables
$env:CONFIG_FILE = $Config1
$env:CONFIG_FILE2 = $Config2

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "AIWolf Docker Startup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Config1: $Config1"
Write-Host "Config2: $Config2"
Write-Host "Log file: $logFile"
Write-Host "Multi mode: $Multi"
Write-Host "========================================" -ForegroundColor Cyan

# Build command
$buildFlag = if ($Build) { " --build" } else { "" }
if ($Multi) {
    $cmd = "docker-compose --env-file ./config/.env --profile multi up$buildFlag"
} else {
    $cmd = "docker-compose --env-file ./config/.env up$buildFlag"
}

Write-Host "Running: $cmd" -ForegroundColor Yellow
Write-Host ""

# Run and save logs (suppress PowerShell stderr warnings)
$ErrorActionPreference = "SilentlyContinue"
Invoke-Expression "$cmd 2>&1" | Tee-Object -FilePath $logFile
$ErrorActionPreference = "Continue"

