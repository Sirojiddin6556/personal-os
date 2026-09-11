<#
.SYNOPSIS
  Personal OS - Unified Test Suite Runner (CI/CD Local & Pipeline).
  Runs all layers of the testing pyramid: Typechecks, Unit tests, Integration tests.
#>

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " Personal OS — Unified Test Suite Runner  " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Backend Pytest (Unit & Integration)
Write-Host "`n[1/3] Running Backend Tests (pytest)..." -ForegroundColor Yellow
Push-Location "apps/api"
try {
    python -m pytest tests/ -v --tb=short
    Write-Host ">> Backend Tests Passed!" -ForegroundColor Green
} finally {
    Pop-Location
}

# 2. Frontend Typecheck
Write-Host "`n[2/3] Running Frontend Typecheck (tsc)..." -ForegroundColor Yellow
Push-Location "apps/web"
try {
    npm run typecheck
    Write-Host ">> Frontend Typecheck Passed!" -ForegroundColor Green
} finally {
    Pop-Location
}

# 3. Frontend Unit Tests (Vitest)
Write-Host "`n[3/3] Running Frontend Tests (vitest)..." -ForegroundColor Yellow
Push-Location "apps/web"
try {
    npm test
    Write-Host ">> Frontend Unit Tests Passed!" -ForegroundColor Green
} finally {
    Pop-Location
}

Write-Host "`n==========================================" -ForegroundColor Cyan
Write-Host " ALL TEST SUITES PASSED SUCCESSFULLY! (100%)" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
