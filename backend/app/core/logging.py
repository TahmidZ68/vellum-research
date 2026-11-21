import logging
import re
from collections.abc import Iterable

from app.core.config import get_settings

_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
    re.compile(r"(tvly-)[A-Za-z0-9\-_]{8,}", re.IGNORECASE),
    re.compile(r"(AIza)[A-Za-z0-9\-_]{16,}"),
    re.compile(r"(sk-)[A-Za-z0-9\-_]{16,}"),
]


class SecretRedactingFilter(logging.Filter):
    """Filter that scrubs known API keys and bearer tokens from log messages."""

    def __init__(self, secrets: Iterable[str] | None = None) -> None:
        super().__init__()
        self._secrets = [s for s in (secrets or []) if s and len(s) >= 6]

    def _redact(self, text: str) -> str:
        for secret in self._secrets:
            if secret in text:
                text = text.replace(secret, "[REDACTED]")
        for pattern in _SECRET_PATTERNS:
            text = pattern.sub(r"\1[REDACTED]", text)
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._redact(record.msg)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    self._redact(a) if isinstance(a, str) else a for a in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    k: (self._redact(v) if isinstance(v, str) else v)
                    for k, v in record.args.items()
                }
        return True


def configure_logging() -> None:
    """Configure structured root logger with secret redaction."""
    settings = get_settings()
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    handler.setFormatter(formatter)

    secrets = [
        settings.APP_SECRET_KEY,
        settings.JWT_SECRET_KEY,
        settings.GEMINI_API_KEY,
        settings.OPENAI_API_KEY,
        settings.TAVILY_API_KEY,
    ]
    handler.addFilter(SecretRedactingFilter(secrets))

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    root.addHandler(handler)
