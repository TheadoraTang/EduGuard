"""Start EduGuard PostgreSQL, backend, and frontend from one terminal."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"


def read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    env_path = ROOT / ".env"
    if not env_path.exists():
        raise RuntimeError("Missing .env. Copy .env.example to .env and configure it first.")
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def command_path(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"Command not found: {name}")
    return path


def terminate(process: subprocess.Popen | None) -> None:
    if not process or process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        process.terminate()


def main() -> int:
    if not VENV_PYTHON.exists():
        raise RuntimeError("Missing .venv\\Scripts\\python.exe. Create the virtual environment first.")
    if not (FRONTEND / "node_modules").exists():
        raise RuntimeError("Frontend dependencies are missing. Run npm install in frontend first.")

    config = read_env()
    required = ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_PORT")
    missing = [key for key in required if not config.get(key)]
    if missing:
        raise RuntimeError(f".env is missing required values: {', '.join(missing)}")

    docker = command_path("docker")
    npm = command_path("npm.cmd" if os.name == "nt" else "npm")

    print("[EduGuard] Starting PostgreSQL and Adminer...", flush=True)
    subprocess.run(
        [docker, "compose", "up", "-d", "postgres", "adminer"],
        cwd=ROOT,
        check=True,
    )

    child_env = os.environ.copy()
    child_env.update(config)
    user = quote(config["POSTGRES_USER"], safe="")
    password = quote(config["POSTGRES_PASSWORD"], safe="")
    database = quote(config["POSTGRES_DB"], safe="")
    port = config["POSTGRES_PORT"]
    child_env["DATABASE_URL"] = (
        f"postgresql+psycopg://{user}:{password}@localhost:{port}/{database}"
    )

    print("[EduGuard] Backend: http://localhost:8000/docs", flush=True)
    print("[EduGuard] Frontend: http://localhost:5173", flush=True)
    print("[EduGuard] Press Ctrl+C to stop backend and frontend.", flush=True)

    creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    backend_process = subprocess.Popen(
        [
            str(VENV_PYTHON),
            "-m",
            "uvicorn",
            "app.main:app",
            "--reload",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        cwd=BACKEND,
        env=child_env,
        creationflags=creation_flags,
    )
    frontend_process = subprocess.Popen(
        [npm, "run", "dev"],
        cwd=FRONTEND,
        env=child_env,
        creationflags=creation_flags,
    )

    try:
        while True:
            backend_code = backend_process.poll()
            frontend_code = frontend_process.poll()
            if backend_code is not None:
                print(
                    f"[EduGuard] Backend exited with code {backend_code}",
                    file=sys.stderr,
                )
                return backend_code
            if frontend_code is not None:
                print(
                    f"[EduGuard] Frontend exited with code {frontend_code}",
                    file=sys.stderr,
                )
                return frontend_code
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[EduGuard] Stopping backend and frontend...", flush=True)
        return 0
    finally:
        terminate(frontend_process)
        terminate(backend_process)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"[EduGuard] Startup failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
