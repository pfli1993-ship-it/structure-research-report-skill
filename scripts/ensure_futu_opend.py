#!/usr/bin/env python3

"""Start Futu OpenD if the local quote API port is not already listening."""

import argparse
import json
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path


DEFAULT_APP_CANDIDATES = [
    "/Applications/Futu_OpenD.app",
    "/Applications/Futu OpenD.app",
    "/Applications/FutuOpenD.app",
    "/Applications/OpenD.app",
    "~/Applications/Futu_OpenD.app",
    "~/Applications/Futu OpenD.app",
    "~/Applications/FutuOpenD.app",
    "~/Applications/OpenD.app",
]


def is_port_open(host, port, timeout=0.4):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def find_app_path(extra_candidates=None):
    candidates = list(extra_candidates or []) + DEFAULT_APP_CANDIDATES
    for candidate in candidates:
        path = Path(candidate).expanduser()
        if path.exists():
            return str(path)
    return None


def open_app(app_path):
    if sys.platform != "darwin":
        raise RuntimeError("Auto-starting Futu OpenD is currently implemented for macOS only.")
    if not shutil.which("open"):
        raise RuntimeError("macOS 'open' command is unavailable.")
    subprocess.run(["open", "-a", app_path], check=True)


def ensure_opend(host, port, wait_seconds, app_candidates=None):
    if is_port_open(host, port):
        return {
            "ok": True,
            "already_running": True,
            "started": False,
            "host": host,
            "port": port,
            "app_path": None,
            "message": "Futu OpenD is already listening.",
        }

    app_path = find_app_path(app_candidates)
    if not app_path:
        return {
            "ok": False,
            "already_running": False,
            "started": False,
            "host": host,
            "port": port,
            "app_path": None,
            "error": "Futu OpenD app was not found in /Applications or ~/Applications.",
        }

    try:
        open_app(app_path)
    except Exception as error:
        return {
            "ok": False,
            "already_running": False,
            "started": False,
            "host": host,
            "port": port,
            "app_path": app_path,
            "error": str(error),
        }

    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if is_port_open(host, port):
            return {
                "ok": True,
                "already_running": False,
                "started": True,
                "host": host,
                "port": port,
                "app_path": app_path,
                "message": "Futu OpenD was opened and the local API port is listening.",
            }
        time.sleep(0.5)

    return {
        "ok": False,
        "already_running": False,
        "started": True,
        "host": host,
        "port": port,
        "app_path": app_path,
        "error": f"Opened Futu OpenD but port {host}:{port} did not become reachable within {wait_seconds}s.",
    }


def main():
    parser = argparse.ArgumentParser(description="Ensure Futu OpenD is running locally.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=11111)
    parser.add_argument("--wait-seconds", type=float, default=12)
    parser.add_argument("--app", action="append", default=[], help="Extra Futu OpenD .app path candidate.")
    args = parser.parse_args()

    result = ensure_opend(args.host, args.port, args.wait_seconds, args.app)
    print(json.dumps(result, ensure_ascii=False))
    if not result.get("ok"):
        sys.exit(1)


if __name__ == "__main__":
    main()
