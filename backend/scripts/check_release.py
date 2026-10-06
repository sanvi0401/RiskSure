"""Check release files against local secrets without displaying their values."""
import argparse
from pathlib import Path
import subprocess

from dotenv import dotenv_values


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    values = dotenv_values(args.env_file)
    sensitive_values = {name: value.encode() for name, value in values.items()
                        if value and len(value) >= 12 and any(word in name for word in (
                            "PASSWORD", "TOKEN", "SECRET", "ENCRYPTION_KEY", "DATABASE_URL"))}
    paths = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                                    cwd=root, text=True).splitlines()
    failures = []
    for name in paths:
        path = Path(name)
        if any(part in {"node_modules", ".next", "__pycache__", ".venv", "artifacts", ".vercel"}
               for part in path.parts) or (path.name.startswith(".env") and path.name != ".env.example"):
            failures.append(f"Excluded artifact is tracked: {name}")
            continue
        if not (root / path).is_file():
            continue
        data = (root / path).read_bytes()
        for key, value in sensitive_values.items():
            if value in data:
                failures.append(f"Configured secret {key} occurs in {name}")
    for failure in failures:
        print(failure)
    print(f"Release file scan: {'FAIL' if failures else 'PASS'} ({len(paths)} files checked)")
    raise SystemExit(bool(failures))
