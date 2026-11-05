# Local Development and SOLIDWORKS Setup

This guide covers building and registering the in-process SOLIDWORKS C# add-in, configuring the per-user `sw-mcp` settings file, and wiring the MCP front-end into Claude Desktop or Claude Code.

---

## 1. Prerequisites

- **OS:** Windows 10 or Windows 11 x64 (an interactive desktop session is required when driving SOLIDWORKS).
- **SOLIDWORKS:** SOLIDWORKS 2025 or newer installed locally.
- **.NET SDK:** .NET 8.0 SDK (`net8.0-windows`).
- **Python Toolchain:** Python 3.13 and [`uv`](https://docs.astral.sh/uv/).

Synchronize the workspace and install the `sw-mcp-core` and `sw-mcp-mcp` console scripts into `.venv`:

```powershell
uv sync
```

---

## 2. Build and Register the SOLIDWORKS Add-In

The execution server runs in-process inside `SLDWORKS.exe` as a COM add-in (`ExecutionServer.AddIn`).

### 2.1 Build the Solution

From the repository root, build `ExecutionServer.sln` (pass `SolidWorksInstallDir` if SOLIDWORKS is not installed in the default `C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS` path):

```powershell
dotnet build apps/execution-server/ExecutionServer.sln -c Release `
  -p:SolidWorksInstallDir="C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS"
```

### 2.2 Register the COM Add-In

From an elevated PowerShell prompt (or using `/codebase` registration for the built assembly), register `ExecutionServer.AddIn.dll` with `regasm.exe` and add the SOLIDWORKS add-in registry keys:

```powershell
$AddInDll = (Resolve-Path "apps\execution-server\ExecutionServer.AddIn\bin\Release\net8.0-windows\ExecutionServer.AddIn.dll").Path
$RegAsm = "$env:windir\Microsoft.NET\Framework64\v4.0.30319\RegAsm.exe"

# Register COM types (for .NET 8 comhost, register ExecutionServer.AddIn.comhost.dll with regsvr32 if enabled)
& $RegAsm /codebase /tlb $AddInDll
```

Verify in SOLIDWORKS under **Tools > Add-Ins** that **sw-mcp Execution Server** is listed and checked for both **Active Add-ins** and **Start Up**. When SOLIDWORKS starts with the add-in loaded, it writes its session discovery file to `%LOCALAPPDATA%\sw-mcp\sessions\sw-<pid>.json`.

---

## 3. User Configuration (`%APPDATA%\sw-mcp\config.toml`)

Security-sensitive settings (`access.allowed_roots`, `access.pdm_vault_roots`, `part.template`, `drawing.standard_dir`, and `solidworks.session`) are read **only** from the per-user configuration file at:

```text
%APPDATA%\sw-mcp\config.toml
```

Create `%APPDATA%\sw-mcp\config.toml` before calling file-reading or part-building tools:

```toml
config_version = "1.0"

[access]
# Every CAD path passed to a tool must reside under one of these directories.
allowed_roots = [
  "D:\\CAD\\Projects",
]

[part]
# Absolute path to your SOLIDWORKS part template (.prtdot) used when creating new parts.
template = "C:\\ProgramData\\SolidWorks\\SOLIDWORKS 2025\\templates\\Part.prtdot"

[mcp]
# Enabled toolsets ("core" by default; add "drawing" or "full" when needed).
toolsets = ["core"]
```

Notes:
- If `access.allowed_roots` is empty or omitted, any file path argument is rejected with `AUTH_PATH_DENIED`.
- `part.template` must be an absolute Windows path ending in `.prtdot`. If `part.template` is empty or points to a missing file when `apply_part_graph` creates a new part, the tool returns `CONFIG_INVALID`.

---

## 4. Configure Claude (`mcpServers`)

`sw-mcp-mcp` is a stateless UTF-8 stdio MCP front-end. When launched by an MCP client, it connects to the per-user `sw-mcp-core` service over its user-only named pipe (starting `sw-mcp-core` automatically if it is not already running).

Add the following `mcpServers` entry to your Claude Desktop configuration (`%APPDATA%\Claude\claude_desktop_config.json`) or project `.mcp.json`:

```json
{
  "mcpServers": {
    "sw-mcp": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "D:\\01_Data\\code\\sw-mcp",
        "sw-mcp-mcp"
      ]
    }
  }
}
```

Alternatively, you can invoke the `.venv` script directly:

```json
{
  "mcpServers": {
    "sw-mcp": {
      "command": "D:\\01_Data\\code\\sw-mcp\\.venv\\Scripts\\sw-mcp-mcp.exe",
      "args": []
    }
  }
}
```

### Managing the Core Service Manually

You can start or stop the background per-user core service directly from the command line:

```powershell
# Start in the foreground
uv run sw-mcp-core

# Stop a running per-user core service instance
uv run sw-mcp-core stop
```
