# Patrol Service Run Script for Windows
Write-Host "🚀 Starting Patrol Service..." -ForegroundColor Cyan

# Create virtual environment if it doesn't exist
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -q -r requirements.txt

# Start service
Write-Host "Starting python script..." -ForegroundColor Green
python patrol_service.py
