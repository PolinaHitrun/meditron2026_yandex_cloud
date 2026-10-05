"""
Логирование метрик пайплайна.

Каждый шаг пишет запись в logs/pipeline.jsonl.
Формат: JSON Lines — каждая строка отдельный валидный JSON.
"""

import json
import time
import traceback
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager

from src.config import (
    PROMPT_VERSION,
    DICTIONARIES_VERSION,
    MODEL_VERSION,
    PIPELINE_VERSION,
)

LOG_PATH = Path("logs/pipeline.jsonl")

LEVELS = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}
CURRENT_LEVEL = "INFO"


def _write_record(record: dict) -> None:
    """Пишет одну запись в jsonl."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _base_record(doc_name: str, step: str, level: str) -> dict:
    """Базовая структура записи."""
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "doc": doc_name,
        "step": step,
        "level": level,
        "versions": {
            "prompt": PROMPT_VERSION,
            "dictionaries": DICTIONARIES_VERSION,
            "model": MODEL_VERSION,
            "pipeline": PIPELINE_VERSION,
        },
    }


def log_step(
    doc_name: str,
    step: str,
    metrics: dict,
    level: str = "INFO",
) -> None:
    """Пишет одну запись метрик в logs/pipeline.jsonl."""
    if LEVELS.get(level, 1) < LEVELS.get(CURRENT_LEVEL, 1):
        return

    record = _base_record(doc_name, step, level)
    record["metrics"] = metrics
    _write_record(record)


def log_error(
    doc_name: str,
    step: str,
    error: Exception,
    context: dict | None = None,
) -> None:
    """Логирует ошибку с трейсбеком."""
    record = _base_record(doc_name, step, "ERROR")
    record["error_type"] = type(error).__name__
    record["error_message"] = str(error)
    record["traceback"] = traceback.format_exc()
    record["context"] = context or {}
    _write_record(record)


@contextmanager
def log_duration(
    doc_name: str,
    step: str,
    extra_metrics: dict | None = None,
    level: str = "INFO",
):
    """Замеряет время шага и логирует его автоматически."""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        metrics = {"latency_ms": elapsed_ms}
        if extra_metrics:
            metrics.update(extra_metrics)
        log_step(doc_name, step, metrics, level=level)
