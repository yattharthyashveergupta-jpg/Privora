"""Privora — Private Document Intelligence Desktop Launcher
Supervises the unified local engine and launches Microsoft Edge in App Mode.
Handles port conflicts, process lifecycle, health monitoring, and graceful termination.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
import json
from pathlib import Path

# Paths
ROOT = Path(__file__).resolve().parent
LOCAL_APPDATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
PRIVORA_DIR = LOCAL_APPDATA / "Privora"
LOG_DIR = PRIVORA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LAUNCHER_LOG = LOG_DIR / "launcher.log"


def log(msg: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {msg}\n"
    try:
        with open(LAUNCHER_LOG, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def check_privora_health(port: int, host: str = "127.0.0.1") -> bool:
    url = f"http://{host}:{port}/api/health"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PrivoraLauncher/1.1"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("status") == "ok"
    except Exception:
        return False
    return False


def find_suitable_port(start_port: int = 8000, max_attempts: int = 50) -> tuple[int, bool]:
    """Return (port, is_already_privora)."""
    # Check if start_port is already a running Privora instance
    if is_port_in_use(start_port):
        if check_privora_health(start_port):
            return start_port, True
        log(f"Port {start_port} is in use by another service. Searching for open port...")
    else:
        # Start port is free and available
        return start_port, False

    # Find next open port
    for port in range(start_port + 1, start_port + max_attempts):
        if is_port_in_use(port):
            if check_privora_health(port):
                return port, True
            continue
        return port, False

    raise RuntimeError(f"Could not find an available port in range {start_port}-{start_port+max_attempts}")


def detect_edge_browser() -> str | None:
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def start_backend_process(port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env["PORT"] = str(port)
    env["HOST"] = "127.0.0.1"
    env["PRIVORA_DESKTOP"] = "1"

    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW

    if getattr(sys, "frozen", False):
        # Packaged standalone executable
        engine_exe = Path(sys.executable).parent / "privora-engine" / "privora-engine.exe"
        if not engine_exe.exists():
            engine_exe = Path(sys.executable).parent / "privora-engine.exe"
        cmd = [str(engine_exe)]
        cwd = str(Path(sys.executable).parent)
    else:
        # Development / script mode
        server_py = ROOT / "backend" / "desktop_server.py"
        cmd = [sys.executable, str(server_py)]
        cwd = str(ROOT / "backend")

    log(f"Spawning backend engine on 127.0.0.1:{port} (cmd: {cmd})")
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        creationflags=creationflags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc


def wait_for_backend(port: int, timeout_seconds: float = 20.0) -> bool:
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        if check_privora_health(port):
            return True
        time.sleep(0.3)
    return False


def launch_desktop() -> int:
    log("Privora desktop launch initiated.")
    try:
        port, already_running = find_suitable_port(8000)
    except Exception as exc:
        log(f"Fatal error finding port: {exc}")
        return 1

    backend_proc: subprocess.Popen | None = None

    if already_running:
        log(f"Existing Privora instance detected on port {port}. Reconnecting...")
    else:
        log(f"Selected port {port} for new backend instance.")
        backend_proc = start_backend_process(port)

        log("Waiting for backend engine health signal...")
        if not wait_for_backend(port, timeout_seconds=20.0):
            log("Backend engine failed to respond to health check within timeout.")
            if backend_proc:
                backend_proc.terminate()
            return 1
        log(f"Backend engine healthy on http://127.0.0.1:{port}/")

    app_url = f"http://127.0.0.1:{port}/"
    edge_exe = detect_edge_browser()

    if not edge_exe:
        log("Microsoft Edge was not detected on system. Launching system default browser.")
        import webbrowser
        webbrowser.open(app_url)
        return 0

    profile_dir = PRIVORA_DIR / "edge_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    edge_args = [
        edge_exe,
        f"--app={app_url}",
        f"--user-data-dir={profile_dir}",
        "--app-id=PrivoraWorkbench",
        "--window-size=1440,900",
        "--disable-extensions",
        "--disable-background-mode",
        "--disable-features=msStartupBoost",
        "--no-first-run",
        "--no-default-browser-check",
    ]

    log(f"Launching Edge App Mode window: {' '.join(edge_args)}")
    edge_start_time = time.time()
    try:
        edge_proc = subprocess.Popen(edge_args)
        # Wait for the user to close the desktop window
        edge_proc.wait()
        elapsed = time.time() - edge_start_time
        log(f"Edge process exited after {elapsed:.2f}s with code {edge_proc.returncode}.")

        # If Edge exited in under 3 seconds with code 0, it handed off window creation
        # to an already-running Edge broker. Do NOT kill the backend engine!
        if elapsed < 3.0 and edge_proc.returncode == 0:
            log("Edge delegated to existing browser instance. Keeping backend engine active.")
            backend_proc = None  # Detach so finally block does not terminate it
        else:
            log("Edge desktop window closed by user.")
    except Exception as exc:
        log(f"Error launching Edge window: {exc}")
    finally:
        if backend_proc is not None:
            log(f"Shutting down child backend process (PID: {backend_proc.pid})...")
            try:
                backend_proc.terminate()
                backend_proc.wait(timeout=3.0)
            except Exception:
                backend_proc.kill()
            log("Backend engine shutdown cleanly.")

    return 0


if __name__ == "__main__":
    sys.exit(launch_desktop())
