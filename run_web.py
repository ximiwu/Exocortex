from __future__ import annotations

import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from argparse import ArgumentParser, Namespace
from pathlib import Path
from shutil import which

import uvicorn

from server.app import app
from server.config import HOST, browser_root_url, health_url


REPO_ROOT = Path(__file__).resolve().parent
WEB_DIR = REPO_ROOT / "web"
WEB_DIST_INDEX = WEB_DIR / "dist" / "index.html"
WEB_BUILD_INPUTS = [
    WEB_DIR / "index.html",
    WEB_DIR / "package.json",
    WEB_DIR / "package-lock.json",
    WEB_DIR / "vite.config.ts",
]


def parse_args() -> Namespace:
    parser = ArgumentParser(description="Launch Exocortex with either a desktop shell or the system browser.")
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Development mode: auto-build frontend when source files are newer than web/dist.",
    )
    parser.add_argument(
        "--browser",
        action="store_true",
        help="Force using the system browser instead of an embedded desktop window.",
    )
    parser.add_argument(
        "--title",
        default="Exocortex",
        help="Window title used by the embedded desktop shell.",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1440,
        help="Initial embedded window width.",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=960,
        help="Initial embedded window height.",
    )
    return parser.parse_args()


def _latest_mtime(root: Path) -> float:
    if not root.exists():
        return 0.0

    return max((path.stat().st_mtime for path in root.rglob("*") if path.is_file()), default=0.0)


def frontend_build_required() -> bool:
    if not WEB_DIST_INDEX.is_file():
        return True

    latest_input = max(
        _latest_mtime(WEB_DIR / "src"),
        _latest_mtime(WEB_DIR / "public"),
        max((path.stat().st_mtime for path in WEB_BUILD_INPUTS if path.exists()), default=0.0),
    )
    return WEB_DIST_INDEX.stat().st_mtime < latest_input


def ensure_frontend_built() -> None:
    if not frontend_build_required():
        return

    print("Building web frontend...", flush=True)
    npm_executable = which("npm.cmd") if sys.platform == "win32" else which("npm")
    if npm_executable is None:
        npm_executable = which("npm")
    if npm_executable is None:
        raise RuntimeError("`npm` was not found. Install Node.js and npm to build the frontend.")
    try:
        subprocess.run([npm_executable, "run", "build"], check=True, cwd=WEB_DIR)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Frontend build failed with exit code {exc.returncode}.") from exc


def ensure_frontend_dist_available() -> None:
    if WEB_DIST_INDEX.is_file():
        return
    raise RuntimeError(
        "Frontend dist is missing. Build it first with `cd web && npm run build`, "
        "or launch with `python run_web.py --dev`."
    )


def find_free_port(host: str = HOST) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return int(sock.getsockname()[1])


def wait_for_healthcheck(url: str, *, timeout_seconds: float = 20.0, interval_seconds: float = 0.25) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as response:
                if 200 <= response.status < 300:
                    return True
        except (urllib.error.URLError, TimeoutError):
            time.sleep(interval_seconds)
    return False


def open_in_system_browser(root_url: str) -> None:
    print(root_url)
    try:
        webbrowser.open(root_url)
    except Exception:
        pass


def open_in_desktop_shell(root_url: str, *, title: str, width: int, height: int) -> bool:
    try:
        import webview
    except ImportError:
        return False

    print(f"{root_url} (desktop shell)")
    window = webview.create_window(title, root_url, width=width, height=height)
    webview.start(gui="edgechromium" if sys.platform == "win32" else None, debug=False)
    return window is not None


def main() -> int:
    args = parse_args()
    try:
        if args.dev:
            ensure_frontend_built()
        else:
            ensure_frontend_dist_available()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    port = find_free_port()
    root_url = browser_root_url(port)
    api_health = health_url(port)

    config = uvicorn.Config(app, host=HOST, port=port, log_level="info")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="exocortex-web-server", daemon=True)
    thread.start()

    if not wait_for_healthcheck(api_health):
        print(f"Server did not become healthy at {api_health}", file=sys.stderr)
        server.should_exit = True
        thread.join(timeout=5)
        return 1

    try:
        opened_desktop = False
        if not args.browser:
            opened_desktop = open_in_desktop_shell(
                root_url,
                title=args.title,
                width=max(640, args.width),
                height=max(480, args.height),
            )
        if not opened_desktop:
            open_in_system_browser(root_url)

        while thread.is_alive():
            thread.join(timeout=0.5)
    except KeyboardInterrupt:
        server.should_exit = True
        thread.join(timeout=10)
    finally:
        server.should_exit = True
        if thread.is_alive():
            thread.join(timeout=10)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
