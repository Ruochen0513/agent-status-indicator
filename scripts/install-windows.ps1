$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$InstallRoot = Join-Path $env:LOCALAPPDATA "AgentStatusIndicator"
$Bin = Join-Path $InstallRoot "bin"
$Desktop = Join-Path $InstallRoot "desktop"
New-Item -ItemType Directory -Force -Path $Bin | Out-Null
New-Item -ItemType Directory -Force -Path $Desktop | Out-Null

Copy-Item (Join-Path $Root "bin\agent-status") $Bin -Force
Copy-Item (Join-Path $Root "bin\agent-status-hook") $Bin -Force
Copy-Item (Join-Path $Root "bin\agent-status-desktop") $Bin -Force
Copy-Item (Join-Path $Root "bin\codex-status-exec") $Bin -Force
Copy-Item (Join-Path $Root "bin\agent-status.cmd") $Bin -Force
Copy-Item (Join-Path $Root "bin\agent-status-hook.cmd") $Bin -Force
Copy-Item (Join-Path $Root "bin\agent-status-desktop.cmd") $Bin -Force
Copy-Item (Join-Path $Root "bin\codex-status-exec.cmd") $Bin -Force
Copy-Item (Join-Path $Root "desktop\agent_status_desktop.py") $Desktop -Force

$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$PathEntries = @($UserPath -split ";" | Where-Object { $_ })
if ($PathEntries -notcontains $Bin) {
    [Environment]::SetEnvironmentVariable("Path", (($PathEntries + $Bin) -join ";"), "User")
}

Write-Host "Installed Agent Status Indicator to $InstallRoot"
Write-Host "Open a new terminal, then run: agent-status-desktop"
