"""PostToolUse: ruff format + autofix an edited Python file; report what is left."""

import json
import subprocess
import sys

data = json.load(sys.stdin)
path = str(data.get("tool_input", {}).get("file_path", ""))
norm = path.replace("\\", "/")

if not norm.endswith(".py") or "/generated/" in norm or "/.venv/" in norm:
    sys.exit(0)

subprocess.run(["uv", "run", "ruff", "format", path], capture_output=True, text=True)
check = subprocess.run(
    ["uv", "run", "ruff", "check", "--fix", path], capture_output=True, text=True
)
if check.returncode != 0:
    print(check.stdout + check.stderr, file=sys.stderr)
    sys.exit(2)
