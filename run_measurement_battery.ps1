# Phase 5.2 Measurement Battery
# This script runs a series of realistic scenarios through log_issue.py
# and non-interactively approves them to generate cache and usage data.

$ErrorActionPreference = "Stop"

function Run-Scenario {
    param(
        [string]$Issue,
        [string]$Cost,
        [string]$Days
    )
    
    $args = @("log_issue.py", "`"$Issue`"", $Cost, $Days)
    Write-Host "---"
    Write-Host "▶️ EXECUTING: python.exe $args"
    Write-Host "---"
    
    try {
        # Pipe 'y' to the approval prompt and capture output
        $output = "y" | python.exe $args
        Write-Host $output
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "❌ SCENARIO FAILED: $Issue" -ForegroundColor Red
        } else {
            Write-Host "✅ SCENARIO COMPLETE: $Issue" -ForegroundColor Green
        }
    } catch {
        Write-Host "❌ SCRIPT CRASHED on scenario: $Issue" -ForegroundColor DarkRed
        Write-Host $_.Exception.Message
    }
    
    # Skip usage feedback prompts
    Start-Sleep -Seconds 3
}

# --- TEST BATTERY ---

# Variations
Run-Scenario "Unexpected rock found during excavation" "15000" "3"
Run-Scenario "Client requested higher-grade windows" "8000" "0"
Run-Scenario "Theft of copper wiring from site" "4000" "1"
Run-Scenario "Unforeseen bedrock discovered at site 2" "25000" "5"
Run-Scenario "HVAC unit upgrade required by client" "12000" "1"

# Wording Variations (to test cache normalization)
Run-Scenario "Rain delay pushed back concrete pour" "0" "2"
Run-Scenario "Rain delay impacts slab pour schedule" "0" "2"
Run-Scenario "Unexpected bedrock at site two" "25000" "5"
Run-Scenario "Client wants better windows installed" "8000" "0"

# RFIs
Run-Scenario "RFI from electrical on conduit routing" "500" "1"
Run-Scenario "Structural engineer needs to clarify beam spec" "500" "1"
Run-Scenario "Architectural clarification on finish details" "250" "0"

# Delays
Run-Scenario "Permit approval from council is delayed" "0" "5"
Run-Scenario "Subcontractor staffing issue" "2500" "2"
Run-Scenario "Material delivery holdup for structural steel" "0" "4"
Run-Scenario "COVID-19 site shutdown protocol activated" "0" "14"

# --- Edge Cases ---
Run-Scenario "Minor adjustment to interior paint color" "500" "0"
Run-Scenario "Catastrophic failure of primary crane" "500000" "30" # High risk, should trigger bypass
Run-Scenario "Request for information regarding fire exit signage" "100" "0"
Run-Scenario "Client wants to add a water feature to the lobby" "35000" "10"


Write-Host "---"
Write-Host "✅ MEASUREMENT BATTERY COMPLETE"
Write-Host "---"
