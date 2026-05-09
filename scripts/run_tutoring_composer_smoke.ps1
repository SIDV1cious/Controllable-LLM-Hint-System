param(
    [string]$AppUrl = $(if ($env:E2E_APP_URL) { $env:E2E_APP_URL } else { "https://controllable-llm-hint-system-zzt.streamlit.app/" }),
    [string]$StudentUsername = $env:E2E_STUDENT_USERNAME,
    [string]$StudentPassword = $env:E2E_STUDENT_PASSWORD,
    [string]$ScenarioFilter = $(if ($env:E2E_SCENARIO_FILTER) { $env:E2E_SCENARIO_FILTER } else { "input_smoke" }),
    [switch]$RealSend,
    [string]$BrowserChannel = $(if ($env:E2E_BROWSER_CHANNEL) { $env:E2E_BROWSER_CHANNEL } else { "chrome" }),
    [string]$ReportPath = $(if ($env:E2E_REPORT_PATH) { $env:E2E_REPORT_PATH } else { Join-Path $env:TEMP "tutoring_composer_smoke_report.json" }),
    [string]$ScreenshotPath = $(if ($env:E2E_SCREENSHOT_PATH) { $env:E2E_SCREENSHOT_PATH } else { Join-Path $env:TEMP "tutoring_composer_smoke.png" })
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$scriptPath = Join-Path $repoRoot "scripts\e2e_tutoring_composer.js"

if (-not (Test-Path $scriptPath)) {
    throw "Cannot find E2E script: $scriptPath"
}

if (-not $StudentUsername -or -not $StudentPassword) {
    throw "Please set E2E_STUDENT_USERNAME and E2E_STUDENT_PASSWORD, or pass -StudentUsername / -StudentPassword."
}

$tempPlaywrightModules = Join-Path $env:TEMP "playwright_tmp\node_modules"
if (-not $env:NODE_PATH -and (Test-Path $tempPlaywrightModules)) {
    $env:NODE_PATH = $tempPlaywrightModules
}

node -e "require('playwright')" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Playwright is not available to Node. Run `npm install --no-save playwright` first, or set NODE_PATH to an existing Playwright node_modules directory."
}

$env:E2E_APP_URL = $AppUrl
$env:E2E_STUDENT_USERNAME = $StudentUsername
$env:E2E_STUDENT_PASSWORD = $StudentPassword
$env:E2E_SCENARIO_FILTER = $ScenarioFilter
$env:E2E_RUN_REAL_SEND = $(if ($RealSend) { "1" } else { "0" })
$env:E2E_BROWSER_CHANNEL = $BrowserChannel
$env:E2E_REPORT_PATH = $ReportPath
$env:E2E_SCREENSHOT_PATH = $ScreenshotPath

Write-Host "Running tutoring composer smoke test..."
Write-Host "  App URL: $AppUrl"
Write-Host "  Scenario filter: $ScenarioFilter"
Write-Host "  Real send: $($env:E2E_RUN_REAL_SEND)"
Write-Host "  Report: $ReportPath"
Write-Host "  Screenshot: $ScreenshotPath"

node $scriptPath
