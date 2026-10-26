"""Application entry point.  The server is intentionally loopback-only."""

from __future__ import annotations

import json
import socket
import webbrowser
from threading import Timer
from urllib.error import URLError
from urllib.request import urlopen

from app import config
from app.ui.web import create_web_app
from app.utils.file_helper import purge_expired_temp_files


def _app_url(port: int) -> str:
    return f"http://{config.SERVER_HOST}:{port}"


def _local_server_is_running(port: int = config.SERVER_PORT) -> bool:
    """Return whether this application's loopback server already answers."""
    try:
        response = urlopen(f"{_app_url(port)}/api/health", timeout=1)
    except (OSError, URLError):
        return False
    try:
        if response.status != 200:
            return False
        payload = json.loads(response.read())
        return (
            payload.get("app") == "phat-thanh-ai"
            and payload.get("version") == config.RUNTIME_VERSION
        )
    except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
        return False
    finally:
        response.close()


def _find_server_port() -> tuple[int, bool]:
    """Reuse an existing app or select an available loopback port near 7860."""
    for port in range(config.SERVER_PORT, config.SERVER_PORT + 11):
        if _local_server_is_running(port):
            return port, True
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind((config.SERVER_HOST, port))
            except OSError:
                continue
        return port, False
    raise RuntimeError("Không tìm được cổng trống từ 7860 đến 7870 để khởi động ứng dụng.")


def build_app():
    config.configure_local_environment(offline=True)
    config.ensure_runtime_directories()
    purge_expired_temp_files()
    return create_web_app()


def run_app(*, open_browser: bool = False) -> None:
    port, already_running = _find_server_port()
    app_url = _app_url(port)
    if already_running:
        print(f"PHÁT THANH AI đang chạy tại {app_url}.")
        if open_browser:
            webbrowser.open(app_url)
        return

    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - installation dependent
        raise RuntimeError("Chưa cài máy chủ web cục bộ. Hãy cài requirements.txt.") from exc

    if open_browser:
        Timer(0.8, lambda: webbrowser.open(app_url)).start()
    uvicorn.run(
        build_app(),
        host=config.SERVER_HOST,
        port=port,
        access_log=False,
        log_level="warning",
    )


if __name__ == "__main__":
    run_app(open_browser=False)
