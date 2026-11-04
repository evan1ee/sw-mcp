<#
.SYNOPSIS
    Registers the sw-mcp SOLIDWORKS Add-In in HKCU (per-user, no admin privileges required).
    Implements ADR-038 and Milestone 6 owner gate.

.PARAMETER Configuration
    Build configuration to register ('Debug' or 'Release'). Defaults to 'Debug'.

.PARAMETER LoadImmediately
    If specified and SOLIDWORKS is currently running, attempts to load the add-in dynamically via LoadAddIn.
#>
[CmdletBinding()]
param(
    [string]$Configuration = "Debug",
    [switch]$LoadImmediately
)

$ErrorActionPreference = "Stop"

$guid = "4A137B34-3A9B-4A73-BE94-0E37C0F4A0A1"
$title = "sw-mcp Add-In"
$description = "sw-mcp execution server add-in for SOLIDWORKS"
$className = "ExecutionServer.AddIn.SwAddin"

# Resolve DLL path
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$dllPath = Join-Path $repoRoot "apps\execution-server\ExecutionServer.AddIn\bin\x64\$Configuration\net48\sw-mcp.AddIn.dll"

if (-not (Test-Path $dllPath)) {
    # Fallback without x64 subfolder
    $dllPathAlt = Join-Path $repoRoot "apps\execution-server\ExecutionServer.AddIn\bin\$Configuration\net48\sw-mcp.AddIn.dll"
    if (Test-Path $dllPathAlt) {
        $dllPath = $dllPathAlt
    } else {
        throw "Could not find built add-in at '$dllPath' or '$dllPathAlt'. Build solution first: dotnet build apps\execution-server\ExecutionServer.sln"
    }
}

$resolvedDllPath = (Resolve-Path $dllPath).Path
$codeBaseUri = [System.Uri]::new($resolvedDllPath).AbsoluteUri
$assemblyName = [System.Reflection.AssemblyName]::GetAssemblyName($resolvedDllPath).FullName

Write-Host "Registering sw-mcp Add-In for Current User..." -ForegroundColor Cyan
Write-Host "  DLL Path: $resolvedDllPath"
Write-Host "  Assembly: $assemblyName"
Write-Host "  CLSID:    {$guid}"

# 1. COM Class Registration in HKCU\Software\Classes\CLSID\{GUID}
$clsidPath = "HKCU:\Software\Classes\CLSID\{$guid}"
New-Item -Path $clsidPath -Force | Out-Null
Set-ItemProperty -Path $clsidPath -Name "(Default)" -Value $className

$inprocPath = Join-Path $clsidPath "InprocServer32"
New-Item -Path $inprocPath -Force | Out-Null
Set-ItemProperty -Path $inprocPath -Name "(Default)" -Value "mscoree.dll"
Set-ItemProperty -Path $inprocPath -Name "ThreadingModel" -Value "Both"
Set-ItemProperty -Path $inprocPath -Name "Class" -Value $className
Set-ItemProperty -Path $inprocPath -Name "Assembly" -Value $assemblyName
Set-ItemProperty -Path $inprocPath -Name "RuntimeVersion" -Value "v4.0.30319"
Set-ItemProperty -Path $inprocPath -Name "CodeBase" -Value $codeBaseUri

$progIdPath = Join-Path $clsidPath "ProgId"
New-Item -Path $progIdPath -Force | Out-Null
Set-ItemProperty -Path $progIdPath -Name "(Default)" -Value $className

$catPath = Join-Path $clsidPath "Implemented Categories\{62C8FE65-4EBB-45e7-B440-6E39B2CDBF29}"
New-Item -Path $catPath -Force | Out-Null

# 2. SOLIDWORKS Add-In Registration in HKCU\Software\SolidWorks\Addins\{GUID}
$swAddinPath = "HKCU:\Software\SolidWorks\Addins\{$guid}"
New-Item -Path $swAddinPath -Force | Out-Null
Set-ItemProperty -Path $swAddinPath -Name "(Default)" -Value 1 -Type DWord
Set-ItemProperty -Path $swAddinPath -Name "Title" -Value $title -Type String
Set-ItemProperty -Path $swAddinPath -Name "Description" -Value $description -Type String

# 3. SOLIDWORKS Add-In Startup Registration in HKCU\Software\SolidWorks\AddInsStartup\{GUID}
$swStartupPath = "HKCU:\Software\SolidWorks\AddInsStartup\{$guid}"
New-Item -Path $swStartupPath -Force | Out-Null
Set-ItemProperty -Path $swStartupPath -Name "(Default)" -Value 1 -Type DWord

Write-Host "COM and SOLIDWORKS registration completed in HKCU." -ForegroundColor Green

# 4. If requested, attempt to load into running SOLIDWORKS instance
if ($LoadImmediately) {
    try {
        Write-Host "Attempting dynamic load into active SOLIDWORKS session..." -ForegroundColor Cyan
        $swApp = [System.Runtime.InteropServices.Marshal]::GetActiveObject("SldWorks.Application")
        if ($swApp -ne $null) {
            $ret = $swApp.LoadAddIn($resolvedDllPath)
            Write-Host "LoadAddIn returned code: $ret" -ForegroundColor Green
        }
    } catch {
        Write-Warning "Could not dynamically load into active SOLIDWORKS: $_. Restart SOLIDWORKS or enable via Tools > Add-Ins."
    }
}
