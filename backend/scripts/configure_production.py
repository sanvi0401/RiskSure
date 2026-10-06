"""Transfer a local environment to existing Vercel projects through stdin."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess

from cryptography.fernet import Fernet
from dotenv import dotenv_values, set_key


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--backend-project", required=True)
    parser.add_argument("--frontend-project", required=True)
    parser.add_argument("--backend-url", required=True)
    parser.add_argument("--frontend-url", required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--model")
    parser.add_argument("--only", nargs="+")
    args = parser.parse_args()
    values = dotenv_values(args.env_file)
    defaults = {
        "TOTP_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "FRONTEND_ORIGIN": args.frontend_url.rstrip("/"),
        "RISKSURE_ENV": "production",
        "RATELIMIT_STORAGE_URI": "memory://",
        "BACKEND_API_URL": args.backend_url.rstrip("/"),
        "NEXT_PUBLIC_API_BASE_URL": "/api",
    }
    if args.model:
        set_key(args.env_file, "HUGGINGFACE_MODEL", args.model)
        values["HUGGINGFACE_MODEL"] = args.model
    for name, value in defaults.items():
        if not (values.get(name) or "").strip():
            set_key(args.env_file, name, value)
            values[name] = value
    npx = shutil.which("npx.cmd") or shutil.which("npx")
    if not npx:
        raise RuntimeError("npx is unavailable")
    frontend_keys = {"BACKEND_API_URL", "NEXT_PUBLIC_API_BASE_URL"}
    backend_keys = {line.split("=", 1)[0] for line in (
        Path(__file__).resolve().parents[2] / ".env.example").read_text().splitlines() if "=" in line}
    for name, value in values.items():
        if not value or not value.strip() or name not in backend_keys:
            continue
        if args.only and name not in args.only:
            continue
        project = args.frontend_project if name in frontend_keys else args.backend_project
        result = subprocess.run([
            npx, "--yes", "vercel", "env", "add", name, "production",
            "--project", project, "--scope", args.scope, "--force",
            "--no-sensitive" if name in frontend_keys else "--sensitive", "--yes",
        ], input=value, text=True, capture_output=True, env={**os.environ, "VERCEL_TELEMETRY_DISABLED": "1"})
        print(f"{name}: {'configured' if result.returncode == 0 else 'failed'}", flush=True)
        if result.returncode:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
