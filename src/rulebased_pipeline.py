"""Пакетная обработка эпикризов: input/*.md → result/<stem>.json.

Пайплайн:
  1. прочитать .md,
  2. сегментировать (src.segmentation),
  3. прогнать regex-экстракторы по каждой группе (src.regex_extractors),
  4. собрать JSON по SCHEMA,
  5. записать result/<stem>.json,
  6. залогировать шаги в logs/pipeline.jsonl.
"""

import json
import time
from pathlib import Path

from src.config import DICTIONARIES_VERSION, PIPELINE_VERSION
from src.logging_utils import log_step, log_error
from src.schema import SCHEMA
from src.segmentation import segment_document
from src.regex_extractors import EXTRACTORS


INPUT_DIR = Path("input")
RESULT_DIR = Path("result")


# ------------------------------------------------------------
# Сборка итогового JSON
# ------------------------------------------------------------

def _default_value(field_type: str) -> str:
    """Значение по умолчанию для пустого поля, по типу из SCHEMA."""
    if field_type == "binary":
        return "0"
    if field_type == "kag":
        return "N"
    # string / number / date / bp / vessel
    return "не указано"


def build_doc_json(extracted: dict[str, dict]) -> dict:
    """Собирает JSON по SCHEMA из результатов экстракторов.

    extracted: {"group_name": {field_name: value_str, ...}, ...}
    Возвращает: {"group_name": {field_name: str, ...}, ...}
    """
    payload: dict[str, dict] = {}

    for group, fields in SCHEMA.items():
        group_result = extracted.get(group) or {}
        group_payload: dict[str, str] = {}

        for field_name, meta in fields.items():
            raw = group_result.get(field_name)

            value = "" if raw is None else str(raw).strip()
            if not value:
                value = _default_value(meta["type"])

            group_payload[field_name] = value

        payload[group] = group_payload

    return payload


# ------------------------------------------------------------
# Обработка одного документа
# ------------------------------------------------------------

def process_one(md_path: Path, out_dir: Path) -> dict:
    """Читает, сегментирует, экстрактит, собирает, пишет JSON.

    Возвращает метрики шага.
    """
    doc_name = md_path.stem
    metrics: dict = {"doc": doc_name}

    # 1. Чтение
    t0 = time.perf_counter()
    try:
        text = md_path.read_text(encoding="utf-8")
    except OSError as e:
        log_error(doc_name, "read_file", e, {"path": str(md_path)})
        raise

    metrics["text_length"] = len(text)

    # 2. Сегментация
    t1 = time.perf_counter()
    segments = segment_document(text)
    metrics["segmentation_ms"] = int((time.perf_counter() - t1) * 1000)

    groups_found = [g for g in SCHEMA if segments.get(g)]
    groups_missing = [g for g in SCHEMA if not segments.get(g)]
    metrics["groups_found"] = len(groups_found)
    metrics["groups_missing"] = groups_missing

    log_step(doc_name, "segmentation", {
        "latency_ms": metrics["segmentation_ms"],
        "text_length": metrics["text_length"],
        "groups_found": metrics["groups_found"],
        "groups_missing": groups_missing,
    })

    # 3. Экстракция
    t2 = time.perf_counter()
    extracted: dict[str, dict] = {}
    for group in SCHEMA:
        segment = segments.get(group, "")
        extractor = EXTRACTORS.get(group)
        if extractor is None:
            extracted[group] = {}
            continue
        try:
            extracted[group] = extractor(segment) or {}
        except Exception as e:
            log_error(doc_name, f"extract:{group}", e, {"group": group})
            extracted[group] = {}
    metrics["extraction_ms"] = int((time.perf_counter() - t2) * 1000)

    # 4. Сборка
    t3 = time.perf_counter()
    payload = build_doc_json(extracted)
    metrics["build_ms"] = int((time.perf_counter() - t3) * 1000)

    # 5. Запись
    t4 = time.perf_counter()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{doc_name}.json"
    try:
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as e:
        log_error(doc_name, "write_result", e, {"path": str(out_path)})
        raise
    metrics["write_ms"] = int((time.perf_counter() - t4) * 1000)

    metrics["total_ms"] = int((time.perf_counter() - t0) * 1000)

    log_step(doc_name, "done", metrics)

    return {"doc": doc_name, "out_path": str(out_path), **metrics}


# ------------------------------------------------------------
# Пакетный прогон
# ------------------------------------------------------------

def run_all(input_dir: Path = INPUT_DIR, out_dir: Path = RESULT_DIR) -> list[dict]:
    files = sorted(input_dir.glob("*.md"))
    if not files:
        print(f"❌ Не найдено .md в {input_dir}/")
        return []

    print(f"📂 Документов: {len(files)}")
    print(f"📄 Первый: {files[0].name}")
    print(f"📄 Последний: {files[-1].name}")
    print(f"🔧 Версии: dictionaries={DICTIONARIES_VERSION}, pipeline={PIPELINE_VERSION}")
    print()

    t_start = time.perf_counter()
    results: list[dict] = []

    for i, md_path in enumerate(files, 1):
        try:
            result = process_one(md_path, out_dir)
            results.append(result)
            if i % 10 == 0 or i == len(files):
                print(f"  [{i}/{len(files)}] {md_path.name}")
        except Exception as e:
            print(f"  ❌ {md_path.name}: {e}")

    elapsed = time.perf_counter() - t_start
    print(f"\n✅ Готово за {elapsed:.2f} сек")
    print(f"💾 Результаты: {out_dir}/")
    print(f"📊 Обработано: {len(results)}/{len(files)}")

    return results


def main():
    run_all()


if __name__ == "__main__":
    main()