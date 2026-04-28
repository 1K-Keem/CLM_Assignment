from contextvars import ContextVar
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


SERVICE = "movie-ticket-web"
ENVIRONMENT = "development"
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"

request_id_var: ContextVar[str] = ContextVar("request_id", default="")
session_id_var: ContextVar[str] = ContextVar("session_id", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")


LOG_FILES = {
    "request": "app.log",
    "browse": "app.log",
    "auth": "auth.log",
    "seat": "booking.log",
    "hold": "booking.log",
    "booking": "booking.log",
    "cancel": "booking.log",
    "concession": "booking.log",
    "admin": "app.log",
    "error": "error.log",
}


def log_event(event: str, category: str, level: str = "INFO", **fields: Any) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "service": SERVICE,
        "environment": ENVIRONMENT,
        "event": event,
        "category": category,
        "request_id": request_id_var.get(),
        "session_id": session_id_var.get(),
        "user_id": user_id_var.get(),
    }
    payload.update({key: value for key, value in fields.items() if value is not None})
    path = LOG_DIR / LOG_FILES.get(category, "app.log")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True, separators=(",", ":")) + "\n")
