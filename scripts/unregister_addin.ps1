<#
.SYNOPSIS
    Unregisters the sw-mcp SOLIDWORKS Add-In from HKCU.
    Implements ADR-038.

.PARAMETER UnloadImmediately
    If specified and SOLIDWORKS is running, attempts to unload the add-in via UnloadAddIn.
#>
[CmdletBinding()]
param(
    [switch]$UnloadImmediately
)

$ErrorActionPreference = "Continue"

$guid = "4A137B34-3A9B-4A73-BE94-0E37C0F4A0A1"

Write-Host "Unregistering sw-mcp Add-In from Current User..." -ForegroundColor Cyan

# 1. Unload if active
if ($UnloadImmediately) {
    try {
        $swApp = [System.Runtime.InteropServices.Marshal]::GetActiveObject("SldWorks.Application")
        if ($swApp -ne $null) {
            $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
            $repoRoot = Split-Path -Parent $scriptDir
            $dllPath = Join-Path $repoRoot "apps\execution-server\ExecutionServer.AddIn\bin\x64\Debug\net48\sw-mcp.AddIn.dll"
            if (Test-Path $dllPath) {
                $ret = $swApp.UnloadAddIn((Resolve-Path $dllPath).Path)
                Write-Host "UnloadAddIn returned code: $ret" -ForegroundColor Green
            }
        }
    } catch {
        Write-Warning "Could not unload add-in via COM: $_"
    }
}

# 2. Remove SOLIDWORKS keys
Remove-Item -Path "HKCU:\Software\SolidWorks\Addins\{$guid}" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path "HKCU:\Software\SolidWorks\AddInsStartup\{$guid}" -Recurse -Force -ErrorAction SilentlyContinue

# 3. Remove COM keys
Remove-Item -Path "HKCU:\Software\Classes\CLSID\{$guid}" -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "Unregistration completed." -ForegroundColor Green
