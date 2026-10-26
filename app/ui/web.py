"""Local FastAPI server with a plain HTML/CSS/JavaScript interface."""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Iterator, Sequence
from pathlib import Path
from threading import Lock
from typing import Annotated, Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app import config
from app.services.errors import UserFacingError
from app.services.ocr_service import iter_recognize_documents
from app.services.pronunciation_dictionary import (
    create_pronunciation,
    delete_pronunciation,
    list_pronunciations,
    update_pronunciation,
)
from app.services.tts_service import VieNeuLocalTTS
from app.services.workflow import generate_bulletin, preview_pronunciation, preview_voice
from app.utils.file_helper import new_job_directory, safe_filename
from app.utils.validators import ALLOWED_DOCUMENT_SUFFIXES

# The local ONNX engine is CPU-intensive and is shared by all TTS requests.
# Match the former one-job-at-a-time UI behaviour instead of allowing a double
# click (or two browser tabs) to compete for the model and CPU.
_tts_operation_lock = Lock()


def _open_directory(directory: Path) -> None:
    """Open a local directory with Windows Explorer without ShellExecute.

    ``os.startfile`` can return WinError 5 for directories when the web server
    was launched from a hidden/background process.  Starting Explorer directly
    avoids that file-association path while keeping arguments shell-free.
    """
    if os.name != "nt":
        raise OSError("Chức năng này hiện chỉ hỗ trợ Windows.")
    resolved = directory.resolve()
    explorer = Path(os.environ.get("WINDIR", r"C:\Windows")) / "explorer.exe"
    executable = str(explorer) if explorer.is_file() else "explorer.exe"
    subprocess.Popen([executable, str(resolved)], close_fds=True)  # noqa: S603


def _event(name: str, payload: dict[str, Any]) -> str:
    """Serialize one Server-Sent Event without allowing user text to break it."""
    return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _save_uploads(files: Sequence[Any]) -> list[Path]:
    """Copy browser uploads to the app's temporary directory with enforced limits."""
    if not files:
        raise UserFacingError("Hãy chọn ít nhất một ảnh JPG, PNG hoặc PDF trước khi nhận diện.")

    upload_dir = new_job_directory("upload")
    paths: list[Path] = []
    for index, upload in enumerate(files, start=1):
        original_name = safe_filename(getattr(upload, "filename", "tep"))
        extension = Path(original_name).suffix.lower()
        if extension not in ALLOWED_DOCUMENT_SUFFIXES:
            raise UserFacingError(f"{original_name}: chỉ hỗ trợ ảnh JPG, PNG hoặc PDF.")
        maximum = config.MAX_PDF_BYTES if extension == ".pdf" else config.MAX_IMAGE_BYTES
        destination = upload_dir / f"{index:03d}_{original_name}"
        received = 0
        with destination.open("wb") as target:
            while chunk := upload.file.read(1024 * 1024):
                received += len(chunk)
                if received > maximum:
                    target.close()
                    destination.unlink(missing_ok=True)
                    maximum_mb = maximum // (1024 * 1024)
                    kind = "PDF" if extension == ".pdf" else "ảnh"
                    raise UserFacingError(f"{original_name}: {kind} lớn hơn giới hạn {maximum_mb} MB.")
                target.write(chunk)
        paths.append(destination)
    return paths


def _ocr_events(paths: Sequence[Path]) -> Iterator[str]:
    """Emit an OCR snapshot immediately after each completed page."""
    def report(value: float, message: str) -> None:
        # OCR work is synchronous.  Page text is sent by the iterator below;
        # this status is included in the next visible event.
        nonlocal last_progress
        last_progress = {"fraction": value, "message": message}

    last_progress: dict[str, Any] = {"fraction": 0.0, "message": "Đang chuẩn bị nhận diện…"}
    final_snapshot = None
    yield _event("status", last_progress)
    try:
        for snapshot in iter_recognize_documents(paths, report):
            # Send this snapshot now — do not wait for the next page.  The
            # final snapshot is sent a second time as `complete` so it can
            # include whole-document warnings without delaying any text.
            yield _event(
                "page",
                {
                    "text": snapshot.text,
                    "page_count": snapshot.page_count,
                    "engine": snapshot.engine,
                    "progress": last_progress,
                },
            )
            final_snapshot = snapshot
        if final_snapshot is None:
            raise UserFacingError("Không nhận diện được chữ từ các tệp đã chọn.")
        yield _event(
            "complete",
            {
                "text": final_snapshot.text,
                "page_count": final_snapshot.page_count,
                "engine": final_snapshot.engine,
                "warnings": list(final_snapshot.warnings),
            },
        )
    except UserFacingError as exc:
        yield _event("error", {"message": str(exc)})
    except Exception:  # noqa: BLE001  # pragma: no cover - defensive browser boundary
        yield _event("error", {"message": "OCR gặp lỗi không mong muốn. Hãy thử lại với tệp khác."})


def create_web_app() -> Any:
    """Create the loopback-only web application; no external assets are used."""
    static_dir = config.WEB_UI_DIR / "static"
    index_file = config.WEB_UI_DIR / "templates" / "index.html"
    app = FastAPI(title=config.APP_NAME, docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return index_file.read_text(encoding="utf-8")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {
            "app": "phat-thanh-ai",
            "status": "ok",
            "version": config.RUNTIME_VERSION,
        }

    @app.get("/api/voices")
    def voices() -> dict[str, Any]:
        try:
            choices = VieNeuLocalTTS().list_preset_voices()
            return {"voices": [{"label": label, "value": value} for label, value in choices]}
        except UserFacingError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/ocr/stream")
    def ocr_stream(files: Annotated[list[UploadFile], File()]) -> Any:
        try:
            paths = _save_uploads(files)
        except UserFacingError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return StreamingResponse(
            _ocr_events(paths),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/voice-preview")
    def voice_preview(payload: dict[str, str]) -> Any:
        try:
            voice = payload.get("voice") or config.DEFAULT_VOICE
            with _tts_operation_lock:
                preview = preview_voice(voice)
            return FileResponse(preview, media_type="audio/wav", filename="nghe_thu_giong.wav")
        except UserFacingError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/pronunciations")
    def pronunciations() -> dict[str, Any]:
        try:
            entries = list_pronunciations()
            return {
                "entries": [entry.to_dict() for entry in entries],
                "storage": str(config.PRONUNCIATION_DICTIONARY_PATH),
            }
        except UserFacingError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/pronunciations")
    def add_pronunciation(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            entry = create_pronunciation(
                payload.get("source"),
                payload.get("spoken"),
                enabled=bool(payload.get("enabled", True)),
            )
            return {"entry": entry.to_dict()}
        except UserFacingError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/pronunciations/{entry_id}")
    def edit_pronunciation(entry_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            entry = update_pronunciation(
                entry_id,
                payload.get("source"),
                payload.get("spoken"),
                enabled=bool(payload.get("enabled", True)),
            )
            return {"entry": entry.to_dict()}
        except UserFacingError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/pronunciations/{entry_id}")
    def remove_pronunciation(entry_id: str) -> dict[str, str]:
        try:
            delete_pronunciation(entry_id)
            return {"message": "Đã xóa mục khỏi từ điển phát âm."}
        except UserFacingError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/pronunciations/preview")
    def pronunciation_preview(payload: dict[str, Any]) -> Any:
        try:
            voice = str(payload.get("voice") or config.DEFAULT_VOICE)
            spoken = str(payload.get("spoken") or "")
            with _tts_operation_lock:
                preview = preview_pronunciation(spoken, voice)
            return FileResponse(
                preview,
                media_type="audio/wav",
                filename="nghe_thu_phat_am.wav",
            )
        except UserFacingError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/generate")
    def generate(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            with _tts_operation_lock:
                result = generate_bulletin(
                    str(payload.get("text") or ""),
                    bool(payload.get("confirmed")),
                    voice=str(payload.get("voice") or config.DEFAULT_VOICE),
                )
            return {
                "filename": result.mp3_path.name,
                "url": f"/api/output/{result.mp3_path.name}",
                "segment_count": result.segment_count,
                "normalizations": list(result.preparation.changes),
            }
        except UserFacingError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/output/{filename}")
    def output_file(filename: str) -> Any:
        safe_name = Path(filename).name
        if safe_name != filename:
            raise HTTPException(status_code=404, detail="Không tìm thấy file âm thanh.")
        output = config.OUTPUT_DIR / safe_name
        if not output.is_file() or output.suffix.lower() != ".mp3":
            raise HTTPException(status_code=404, detail="Không tìm thấy file âm thanh.")
        return FileResponse(output, media_type="audio/mpeg", filename=safe_name)

    @app.post("/api/open-output")
    def open_output() -> JSONResponse:
        config.ensure_runtime_directories()
        try:
            _open_directory(config.OUTPUT_DIR)
            return JSONResponse({"message": f"Đã mở thư mục: {config.OUTPUT_DIR}"})
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Không thể mở thư mục: {exc}") from exc

    return app
