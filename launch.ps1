Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  A.G.E.N.T.S. SYSTEM LAUNCHER (v2.0.0)" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptRoot

$serverPort = 8000
$webUrl = "http://localhost:8000/static/index.html"
$statusUrl = "http://localhost:8000/status"
$telemetryUrl = "http://localhost:8000/telemetry"

function Stop-ProcessesOnPort {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port
    )

    $pattern = "^\s*TCP\s+\S+:$Port\s+\S+\s+LISTENING\s+(\d+)\s*$"
    $pids = netstat -ano |
        Select-String ":$Port" |
        ForEach-Object {
            if ($_.Line -match $pattern) {
                [int]$matches[1]
            }
        } |
        Sort-Object -Unique

    if (-not $pids) {
        Write-Host "      No listeners found on port $Port." -ForegroundColor DarkGray
        return
    }

    foreach ($listenerPid in $pids) {
        if ($listenerPid -and $listenerPid -ne $PID) {
            try {
                $proc = Get-Process -Id $listenerPid -ErrorAction Stop
                Write-Host "      Stopping $($proc.ProcessName) (PID $listenerPid) on port $Port..." -ForegroundColor Yellow
                Stop-Process -Id $listenerPid -Force -ErrorAction Stop
            } catch {
                Write-Host "      Failed to stop PID $listenerPid on port ${Port}: $($_.Exception.Message)" -ForegroundColor Yellow
            }
        }
    }
}

Write-Host "[0/5] Checking environment file..." -NoNewline
if (Test-Path ".env") {
    Write-Host " [FOUND]" -ForegroundColor Green
} elseif (Test-Path ".env.example") {
    Copy-Item ".env.example" ".env"
    Write-Host " [CREATED FROM TEMPLATE]" -ForegroundColor Yellow
    Write-Host "      Please review .env before production usage." -ForegroundColor Yellow
} else {
    Write-Host " [MISSING]" -ForegroundColor Red
    Write-Host "      No .env or .env.example found." -ForegroundColor Yellow
}

Write-Host "[1/5] Checking Ollama Local Server..." -NoNewline
$ollamaOnline = $false
try {
    $null = Invoke-WebRequest -Uri "http://localhost:11434" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
    $ollamaOnline = $true
    Write-Host " [ONLINE]" -ForegroundColor Green
} catch {
    Write-Host " [OFFLINE]" -ForegroundColor Red
    Write-Host "      Attempting to launch Ollama Background Service..." -ForegroundColor Yellow
    try {
        Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden -ErrorAction Stop
        for ($i = 0; $i -lt 12; $i++) {
            Start-Sleep -Seconds 1
            try {
                $null = Invoke-WebRequest -Uri "http://localhost:11434" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
                $ollamaOnline = $true
                break
            } catch {}
        }
        if ($ollamaOnline) {
            Write-Host "      Ollama initialized." -ForegroundColor Green
        } else {
            Write-Host "      Ollama did not come online. Continuing anyway..." -ForegroundColor Yellow
        }
    } catch {
        Write-Host "      Failed to start Ollama automatically. Continuing anyway..." -ForegroundColor Yellow
    }
}

Write-Host "[2/5] Activating Environment (.venv)..." -NoNewline
if (Test-Path ".venv\Scripts\Activate.ps1") {
    . .venv\Scripts\Activate.ps1
    Write-Host " [ACTIVE]" -ForegroundColor Green
} else {
    Write-Host " [NOT FOUND]" -ForegroundColor Red
    Write-Host "      Falling back to system Python (recommend creating a .venv)." -ForegroundColor Yellow
}

Write-Host "[3/5] Verifying runtime packages..." -NoNewline
python -c "import fastapi, uvicorn, pydantic" *> $null
if ($LASTEXITCODE -eq 0) {
    Write-Host " [OK]" -ForegroundColor Green
} else {
    Write-Host " [MISSING]" -ForegroundColor Yellow
    Write-Host "      Run: pip install -r requirements.txt" -ForegroundColor Yellow
}

Write-Host "[4/5] Live WebApp access" -ForegroundColor Cyan
Write-Host "      WebApp:    $webUrl" -ForegroundColor White
Write-Host "      Status:    $statusUrl" -ForegroundColor White
Write-Host "      Telemetry: $telemetryUrl" -ForegroundColor White
Write-Host "      For scenario-loop progress, send prompts starting with: Variation:, RFI:, or Delay:" -ForegroundColor White
Write-Host "      For phone/remote viewing, run remote_access_v2.bat in another terminal." -ForegroundColor White
Write-Host ""

Write-Host "[5/6] Clearing stale server processes..." -NoNewline
Stop-ProcessesOnPort -Port $serverPort
Write-Host " [DONE]" -ForegroundColor Green

Write-Host "[6/6] Launching A.G.E.N.T.S. Management Suite..." -ForegroundColor Cyan
Write-Host "--------------------------------------------------" -ForegroundColor Cyan
python main.py

Write-Host ""
Write-Host "System process terminated."
Pause
