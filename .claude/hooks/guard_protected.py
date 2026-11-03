"""PreToolUse: block hand edits to generated code and the uv lockfile (ADR-035)."""

import json
import sys
from pathlib import PurePosixPath

reason = None
data = json.load(sys.stdin)
path = str(data.get("tool_input", {}).get("file_path", "")).replace("\\", "/")
parts = PurePosixPath(path).parts

if "generated" in parts:
    reason = "generated code is a build output (ADR-035): change schemas/ and regenerate"
elif parts and parts[-1] == "uv.lock":
    reason = "uv.lock is managed by uv: use `uv lock` / `uv add` instead"

if reason:
    print(f"Blocked edit of {path}: {reason}.", file=sys.stderr)
    sys.exit(2)
