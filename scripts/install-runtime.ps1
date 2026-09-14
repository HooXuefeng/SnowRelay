$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)

$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $projectRoot
$venv = Join-Path $projectRoot '.venv'
$venvPython = Join-Path $venv 'Scripts\python.exe'

function Test-GuiPython([string]$pythonExe) {
    if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) { return $false }
    try {
        & $pythonExe -c "import main; main.prepare_tk_runtime(); import tkinter as tk; root=tk.Tcl(); assert root.eval('info patchlevel')" 2>$null
        return $LASTEXITCODE -eq 0
    } catch { return $false }
}

function Find-GuiPython {
    foreach ($version in @('3.13', '3.12', '3.11', '3.10')) {
        try {
            $candidate = (& py "-$version" -c "import sys; print(sys.executable)" 2>$null | Select-Object -Last 1).Trim()
            if ($LASTEXITCODE -eq 0 -and (Test-GuiPython $candidate)) { return $candidate }
        } catch { }
    }
    try {
        $candidate = (& python -c "import sys; print(sys.executable)" 2>$null | Select-Object -Last 1).Trim()
        if ($LASTEXITCODE -eq 0 -and (Test-GuiPython $candidate)) { return $candidate }
    } catch { }
    return $null
}

if (-not (Test-GuiPython $venvPython)) {
    if (Test-Path -LiteralPath $venv) {
        $resolvedVenv = [IO.Path]::GetFullPath($venv)
        $resolvedRoot = [IO.Path]::GetFullPath($projectRoot) + [IO.Path]::DirectorySeparatorChar
        if (-not $resolvedVenv.StartsWith($resolvedRoot, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Runtime environment escaped the SnowRelay project directory.'
        }
        Remove-Item -LiteralPath $resolvedVenv -Recurse -Force
    }
    $basePython = Find-GuiPython
    if (-not $basePython) {
        throw 'Python 3.10-3.13 with working Tkinter was not found. Use start.bat with the packaged EXE, or install 64-bit Python with tcl/tk and IDLE enabled.'
    }
    Write-Host "Using Python: $basePython"
    & $basePython -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw 'Unable to create the source runtime.' }
}

& $venvPython -c "import pandas, openpyxl, xlrd" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Installing missing application dependencies...'
    & $venvPython -m pip install --disable-pip-version-check -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Application dependency installation failed. Check the network connection.' }
} else {
    Write-Host 'Application dependencies are ready.'
}
