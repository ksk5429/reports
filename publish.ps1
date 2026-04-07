# Publish Quarto report to GitHub Pages with UTF-8 forced
# Usage: .\publish.ps1 [report.qmd]
param(
    [string]$Report = "report.qmd"
)

$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

Write-Host "Publishing $Report to GitHub Pages..." -ForegroundColor Cyan
quarto publish gh-pages $Report --no-prompt --no-browser

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nSUCCESS - https://ksk5429.github.io/reports/" -ForegroundColor Green
} else {
    Write-Host "`nFAILED" -ForegroundColor Red
    exit $LASTEXITCODE
}
