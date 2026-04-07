#!/usr/bin/env bash
# Publish Quarto report to GitHub Pages with UTF-8 forced
# Usage: ./publish.sh [report.qmd]
set -e
REPORT="${1:-report.qmd}"

export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1

echo "Publishing $REPORT to GitHub Pages..."
quarto publish gh-pages "$REPORT" --no-prompt --no-browser

echo ""
echo "SUCCESS - https://ksk5429.github.io/reports/"
