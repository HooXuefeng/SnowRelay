$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)

$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $projectRoot
$buildEnv = Join-Path $projectRoot '.build-env'

function Get-PythonBase([string]$pythonExe) {
    if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) { return $null }
    try {
        $base = (& $pythonExe -c "import sys; print(sys.base_prefix)" 2>$null | Select-Object -Last 1).Trim()
        if ($LASTEXITCODE -eq 0 -and $base) { return $base }
    } catch { }
    return $null
}

function Has-TkFiles([string]$pythonExe) {
    $base = Get-PythonBase $pythonExe
    if (-not $base) { return $false }
    $required = @(
        (Join-Path $base 'tcl\tcl8.6\init.tcl'),
        (Join-Path $base 'tcl\tk8.6\tk.tcl'),
        (Join-Path $base 'DLLs\_tkinter.pyd'),
        (Join-Path $base 'DLLs\tcl86t.dll'),
        (Join-Path $base 'DLLs\tk86t.dll')
    )
    return -not ($required | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) })
}

function Find-BasePython {
    $bundled = Join-Path $projectRoot '.build-python\runtime\python.exe'
    if (Has-TkFiles $bundled) { return $bundled }

    foreach ($version in @('3.13', '3.12', '3.11', '3.10')) {
        try {
            $candidate = (& py "-$version" -c "import sys; print(sys.executable)" 2>$null | Select-Object -Last 1).Trim()
            if ($LASTEXITCODE -eq 0 -and (Has-TkFiles $candidate)) { return $candidate }
        } catch { }
    }

    try {
        $candidate = (& python -c "import sys; print(sys.executable)" 2>$null | Select-Object -Last 1).Trim()
        if ($LASTEXITCODE -eq 0 -and (Has-TkFiles $candidate)) { return $candidate }
    } catch { }
    return $null
}

$bundledPython = Join-Path $projectRoot '.build-python\runtime\python.exe'
if (Has-TkFiles $bundledPython) {
    # This runtime exists only for SnowRelay builds, so installing build
    # dependencies into it never changes the user's system Python.
    $python = $bundledPython
    Write-Host "Using SnowRelay build runtime: $python"
} else {
    $existingBuildPython = Join-Path $buildEnv 'Scripts\python.exe'
    if (-not (Has-TkFiles $existingBuildPython)) {
        if (Test-Path -LiteralPath $buildEnv) {
            $resolvedBuildEnv = [IO.Path]::GetFullPath($buildEnv)
            $resolvedRoot = [IO.Path]::GetFullPath($projectRoot) + [IO.Path]::DirectorySeparatorChar
            if (-not $resolvedBuildEnv.StartsWith($resolvedRoot, [StringComparison]::OrdinalIgnoreCase)) {
                throw 'Build environment escaped the SnowRelay project directory.'
            }
            Remove-Item -LiteralPath $resolvedBuildEnv -Recurse -Force
        }
        $basePython = Find-BasePython
        if (-not $basePython) {
            throw 'Python 3.10-3.13 with Tcl/Tk was not found. Install 64-bit Python with tcl/tk and IDLE enabled.'
        }
        Write-Host "Using Python: $basePython"
        & $basePython -m venv $buildEnv
        if ($LASTEXITCODE -ne 0) { throw 'Unable to create the isolated build environment.' }
    }
    $python = $existingBuildPython
}

& $python -c "import pandas, openpyxl, xlrd, PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Installing missing build dependencies...'
    & $python -m pip install --disable-pip-version-check -r requirements.txt -r requirements-build.txt
    if ($LASTEXITCODE -ne 0) { throw 'Build dependency installation failed. Check the network and Python configuration.' }
} else {
    Write-Host 'Build dependencies are ready.'
}

Write-Host 'Building the Windows application...'
& $python -m PyInstaller --noconfirm --clean SnowRelay.spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }

$output = Join-Path $projectRoot 'dist\SnowRelay-v0.5.0\SnowRelay.exe'
if (-not (Test-Path -LiteralPath $output -PathType Leaf)) {
    throw 'The build command completed without creating SnowRelay.exe.'
}
$item = Get-Item -LiteralPath $output
Write-Host 'Verifying packaged application startup...'
$smoke = Start-Process -FilePath $output -ArgumentList '--smoke' -WindowStyle Hidden -PassThru
if (-not $smoke.WaitForExit(15000)) {
    Stop-Process -Id $smoke.Id -Force -ErrorAction SilentlyContinue
    throw 'SnowRelay.exe did not complete its startup check within 15 seconds.'
}
if ($smoke.ExitCode -ne 0) {
    throw "SnowRelay.exe startup check failed with exit code $($smoke.ExitCode)."
}
Write-Host 'Verifying packaged customer-table conversion...'
$sample = Join-Path $projectRoot 'samples\sample_vulns.csv'
$conversionOutput = Join-Path ([IO.Path]::GetTempPath()) ("snowrelay-conversion-{0}.xlsx" -f [Guid]::NewGuid().ToString('N'))
$conversionArgs = '"{0}" --output "{1}" --quiet' -f $sample, $conversionOutput
$conversion = Start-Process -FilePath $output -ArgumentList $conversionArgs -WindowStyle Hidden -PassThru
if (-not $conversion.WaitForExit(30000)) {
    Stop-Process -Id $conversion.Id -Force -ErrorAction SilentlyContinue
    throw 'SnowRelay.exe did not complete its conversion check within 30 seconds.'
}
if ($conversion.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $conversionOutput -PathType Leaf)) {
    throw 'SnowRelay.exe packaged conversion check failed.'
}
Remove-Item -LiteralPath $conversionOutput -Force
$intermediate = Join-Path $projectRoot 'build'
if (Test-Path -LiteralPath $intermediate) {
    $resolvedIntermediate = [IO.Path]::GetFullPath($intermediate)
    $resolvedRoot = [IO.Path]::GetFullPath($projectRoot) + [IO.Path]::DirectorySeparatorChar
    if (-not $resolvedIntermediate.StartsWith($resolvedRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Build cleanup path escaped the SnowRelay project directory.'
    }
    Remove-Item -LiteralPath $resolvedIntermediate -Recurse -Force
}
Write-Host ("Completed: {0} ({1:N2} MB)" -f $item.FullName, ($item.Length / 1MB))
