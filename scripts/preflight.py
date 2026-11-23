"""Check BrightSpeak source syntax and API imports before starting Uvicorn.

Launched as a file (NOT python -c) to avoid Windows PowerShell 5.1
quotation removal in arguments passed to native executables.
"""

from __future__ import annotations

import argparse
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK_DIRS = ("app", "scripts", "ml", "tests")

def check_source_syntax(root: Path) -> int:
    examined = 0
    for dirname in CHECK_DIRS:
        folder = root / dirname
        if not folder.exists():
            continue
        for path in sorted(folder.rglob("*.py")):
            if any(part in {"__pycache__", ".venv", ".git"} for part in path.parts):
                continue
            with tokenize.open(path) as f:
                source = f.read()
            compile(source, str(path), "exec")
            examined += 1
    print(f"Python syntax OK: {examined} source files.", flush=True)
    return examined

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan-root", type=Path, default=ROOT, help="Source root (for diagnostics)")
    parser.add_argument("--syntax-only", action="store_true", help="Only verify .py compilation")
    args = parser.parse_args()
    try:
        count = check_source_syntax(args.scan_root.resolve())
        if count == 0:
            print("ERROR: no Python source files found.", file=sys.stderr, flush=True)
            return 2
        if args.syntax_only:
            return 0
        if args.scan_root.resolve() != ROOT:
            print("ERROR: importing app from another scan root is unsupported.", file=sys.stderr)
            return 2
        sys.path.insert(0, str(ROOT))
        from app.daily import local_day
        from app.main import app
        print(f"Python preflight OK. Local date: {local_day()}; app version: {app.version}", flush=True)
        return 0
    except Exception:
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
