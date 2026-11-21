# Optional per-user shortcut. Run with -Remove to disable start-at-sign-in.
[CmdletBinding()]
param([switch]$Remove, [string]$ShortcutDirectory)
$ErrorActionPreference = 'Stop'
$projectDirectory = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$startupDirectory = if ($ShortcutDirectory) { (Resolve-Path -LiteralPath $ShortcutDirectory).Path } else {
    [Environment]::GetFolderPath([Environment+SpecialFolder]::Startup)
}
if ([string]::IsNullOrWhiteSpace($startupDirectory)) { throw 'The Windows Startup folder is unavailable.' }
$shortcutPath = Join-Path $startupDirectory 'Leonida Loot Atlas.lnk'
$launcherScript = Join-Path $projectDirectory 'launch_atlas.py'
$shortcutFactory = New-Object -ComObject WScript.Shell
$shortcut = $shortcutFactory.CreateShortcut($shortcutPath)
if ((Test-Path -LiteralPath $shortcutPath) -and $shortcut.Description -ne 'Start the Leonida Loot Atlas local discovery server') {
    throw 'Another shortcut uses this name. Leaving it untouched.'
}
if ($Remove) {
    if (Test-Path -LiteralPath $shortcutPath) { Remove-Item -LiteralPath $shortcutPath }
    Write-Output 'Atlas startup disabled.'
    return
}
$pythonLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
$pythonWindowless = $null
if ($pythonLauncher) {
    $pythonWindowless = & $pythonLauncher.Source -3 -c "from pathlib import Path; import sys; print(Path(sys.executable).with_name('pythonw.exe'))" 2>$null
}
if (-not $pythonWindowless) {
    $pythonWindowless = & python.exe -c "from pathlib import Path; import sys; print(Path(sys.executable).with_name('pythonw.exe'))"
}
if (-not $pythonWindowless -or -not (Test-Path -LiteralPath $pythonWindowless -PathType Leaf)) { throw 'Install Python for Windows first.' }
$shortcut.TargetPath = $pythonWindowless
$shortcut.Arguments = '"' + $launcherScript + '" --no-open --bundled-only'
$shortcut.WorkingDirectory = $projectDirectory
$shortcut.Description = 'Start the Leonida Loot Atlas local discovery server'
$shortcut.Save()
Write-Output 'Atlas startup enabled for your next Windows sign-in.'

