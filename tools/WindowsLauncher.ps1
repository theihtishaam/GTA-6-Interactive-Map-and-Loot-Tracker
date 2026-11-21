[CmdletBinding()]
param(
    [ValidateSet('Start', 'Stop', 'Status')][string]$Action = 'Start',
    [switch]$NoOpen, [switch]$BundledOnly,
    [ValidateRange(0, 65535)][int]$Port
)
$ErrorActionPreference = 'Stop'
$project = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$dataDirectory = if ($env:GTA6_LOOT_MAP_DATA) { [IO.Path]::GetFullPath($env:GTA6_LOOT_MAP_DATA) } else { Join-Path $project '.atlas' }
$runtimeRoot = Join-Path $dataDirectory 'runtime'
$version = '3.14.10'
# Python Software Foundation release manifest: https://www.python.org/downloads/release/python-31410/
$checksums = @{
    amd64 = '90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159'
    win32 = '11a28e8c00a6d8f56b0a6164d52546133a9ed015a5b33e04536917e4fd6e306c'
    arm64 = 'bbe116bb1248820359cbf25127ac5c7794ea161869d83686cfbc9a45203ff836'
}

function Find-InstalledPython {
    $probe = 'import sys, sqlite3, ssl; print(sys.executable) if sys.version_info >= (3,10) else sys.exit(1)'
    foreach ($name in @('py.exe', 'python.exe', 'python3.exe')) {
        $commands = @(Get-Command $name -CommandType Application -All -ErrorAction SilentlyContinue)
        foreach ($command in $commands) {
            $exe = $command.Source
            $candidates = @($exe)
            $useLegacyLauncher = $name -eq 'py.exe'
            if ($exe -like '*\Microsoft\WindowsApps\*') {
                # A bare python.exe alias can open the Store. Ask the install
                # manager for existing interpreter paths without installing one.
                if ($name -ne 'py.exe') { continue }
                try { $candidates = @(& $exe list --format=exe 2>$null) }
                catch { continue }
                if ($LASTEXITCODE -ne 0) { continue }
                $useLegacyLauncher = $false
            }
            foreach ($candidate in $candidates) {
                if (!$candidate -or !(Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
                $parameters = @('-I', '-c', $probe)
                if ($useLegacyLauncher) { $parameters = @('-3') + $parameters }
                try {
                    $found = & $candidate @parameters 2>$null
                    if ($LASTEXITCODE -eq 0 -and $found -and (Test-Path -LiteralPath $found -PathType Leaf)) {
                        return [string]$found
                    }
                } catch { continue }
            }
        }
    }
}

function Get-AppPython {
    $arch = if ($env:PROCESSOR_ARCHITEW6432) { $env:PROCESSOR_ARCHITEW6432 } else { $env:PROCESSOR_ARCHITECTURE }
    $platform = switch ($arch) { 'AMD64' {'amd64'} 'ARM64' {'arm64'} 'x86' {'win32'} default { throw "Unsupported Windows architecture: $arch" } }
    $target = Join-Path $runtimeRoot "python-$version-$platform"
    $executable = Join-Path $target 'python.exe'
    if (Test-Path -LiteralPath $executable -PathType Leaf) { return $executable }
    [IO.Directory]::CreateDirectory($runtimeRoot) | Out-Null
    $deadline = [datetime]::UtcNow.AddMinutes(3)
    do {
        try {
            $lock = [IO.File]::Open((Join-Path $runtimeRoot 'setup.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
        } catch [IO.IOException] {
            if ([datetime]::UtcNow -ge $deadline) { throw 'Another setup is taking longer than expected. Try Start Atlas again.' }
            Start-Sleep -Milliseconds 250
        }
    } until ($lock)
    try {
        if (Test-Path -LiteralPath $executable -PathType Leaf) { return $executable }
        Write-Host "Setting up Python $version in the map folder. The first download is about 12 MB."
        $stage = Join-Path $runtimeRoot ('setup-' + [guid]::NewGuid().ToString('N'))
        $archive = $stage + '.zip'
        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            $url = "https://www.python.org/ftp/python/$version/python-$version-embed-$platform.zip"
            Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $archive -TimeoutSec 90
            $algorithm = [Security.Cryptography.SHA256]::Create()
            $source = [IO.File]::OpenRead($archive)
            try {
                $digest = [BitConverter]::ToString($algorithm.ComputeHash($source)).Replace('-', '')
            } finally { $source.Dispose(); $algorithm.Dispose() }
            if ($digest -ne $checksums[$platform]) {
                throw 'The Python download did not match its published checksum. Try Start Atlas again.'
            }
            Add-Type -AssemblyName System.IO.Compression.FileSystem
            [IO.Compression.ZipFile]::ExtractToDirectory($archive, $stage)
            & (Join-Path $stage 'python.exe') -c 'import sqlite3, ssl'
            if ($LASTEXITCODE -ne 0) { throw 'The downloaded runtime could not start the map.' }
            if ([IO.Path]::GetDirectoryName($target) -ne $runtimeRoot -or [IO.Path]::GetDirectoryName($stage) -ne $runtimeRoot) {
                throw 'Invalid local runtime directory.'
            }
            [IO.Directory]::Move($stage, $target)
            return $executable
        } finally {
            if (Test-Path -LiteralPath $archive -PathType Leaf) { Remove-Item -LiteralPath $archive -Force }
            if ((Test-Path -LiteralPath $stage -PathType Container) -and
                [IO.Path]::GetDirectoryName((Resolve-Path -LiteralPath $stage).Path) -eq $runtimeRoot -and
                [IO.Path]::GetFileName($stage) -match '^setup-[a-f0-9]{32}$') {
                Remove-Item -LiteralPath $stage -Recurse -Force
            }
        }
    } finally { $lock.Dispose() }
}

try {
    if ($Action -ne 'Start' -and !(Test-Path -LiteralPath (Join-Path $dataDirectory 'launcher.lock'))) {
        Write-Host 'GTA 6 Loot Map is already stopped.'
        exit 0
    }
    $interpreter = Find-InstalledPython
    if (!$interpreter) { $interpreter = Get-AppPython }
    $launchArgs = @((Join-Path $project 'app.py'))
    if ($Action -eq 'Stop') { $launchArgs += '--stop' }
    if ($Action -eq 'Status') { $launchArgs += '--status' }
    if ($NoOpen) { $launchArgs += '--no-open' }
    if ($BundledOnly) { $launchArgs += '--bundled-only' }
    if ($PSBoundParameters.ContainsKey('Port')) { $launchArgs += @('--port', $Port) }
    & $interpreter @launchArgs
    exit $LASTEXITCODE
} catch {
    Write-Host "Atlas setup: $($_.Exception.Message)"
    Write-Host 'Try Start Atlas.cmd again. For offline setup, install Python 3.10 or newer from https://www.python.org/downloads/windows/ and reopen the map.'
    exit 1
}
