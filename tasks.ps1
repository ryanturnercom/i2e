#!/usr/bin/env pwsh
# Project task runner.
# Usage:  ./tasks.ps1 test
#         ./tasks.ps1 cov

param(
    [Parameter(Position = 0)]
    [ValidateSet("test", "cov", "install", "e2e", "all", "bundle")]
    [string]$Task = "test"
)

$python = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }

switch ($Task) {
    "install" {
        & $python -m pip install -e ".[dev]"
    }
    "test" {
        & $python -m pytest -q
    }
    "cov" {
        & $python -m pytest -q --cov=i2e_core --cov-report=term-missing
    }
    "e2e" {
        & $python -m pytest -m e2e -q
    }
    "all" {
        & $python -m pytest -m "e2e or not e2e" -q
    }
    "bundle" {
        & $python packaging/build_bundles.py
    }
}
