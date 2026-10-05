"""Прогон логирования по всем эпикризам в input/.

Чистый regex-пайплайн без LLM и без PHI-анонимизации:
- сегментация по SECTION_PATTERNS,
- лог шага сегментации,
- (далее) regex-экстракторы и сборка JSON.
"""

import time
from pathlib import Path

from src.logging_utils import log_step, log_error

INPUT_DIR = Path("input")
LOG_PATH = Path("logs/pipeline.jsonl")


SECTION_PATTERNS = {
    "даты эпизода": [
        r"(?i)\bдата\s+госпитализации",
        r"(?i)\bдата\s+выписки",
        r"(?i)\bпериод\s+лечения",
        r"(?i)\bпоступил[а]?\s*:?\s*\d",
        r"(?i)\bвыписан[а]?\s*:?\s*\d",
        r"(?i)\bгоспитализирован[а]?",
    ],
    "диагноз": [
        r"(?im)^\s*(заключительный|клинический|основной)?\s*диагноз",
        r"(?im)^\s*диагноз\s+при\s+выписке",
    ],
    "осмотр при поступлении": [
        r"(?im)^\s*(первичный\s+статус|осмотр\s+при\s+поступлении|объективно\s+при\s+поступлении|данные\s+осмотра)",
    ],
    "ЭКГ": [
        r"(?im)^\s*(экг|электрокардиография)\b",
        r"(?i)\.\s+(экг|электрокардиография)\s+от",
    ],
    "ЭХО-КГ": [
        r"(?im)^\s*(эхо[- ]?кг|эхокардиография|узи\s+сердца)",
    ],
    "рентген грудной полости": [
        r"(?im)^\s*(рентген(ография)?|р-графия|рентгенолог)",
        r"(?im)^\s*рентгенограмма",
    ],
    "коронарография": [
        r"(?im)^\s*(каг|коронарография|коронароангиография|исследование\s+коронарного\s+русла|инвазивная\s+диагностика|ангиография)",
    ],
    "Лабораторные данные": [
        # было: анализ[ахы]+ — не матчит "Анализы" (один символ после "анализ")
        r"(?i)\b(лабораторные\s+(исследования|данные)|анализ\w*\s+крови|биохимический\s+профиль)",
        r"(?im)^\s*анализы\s+крови\s*:?\s*$",
        r"(?im)^\s*исследования\s*$",
    ],
    "медикаментозная терапия": [
        r"(?im)^\s*(рекомендации(\s+при\s+выписке)?|назначения\s+при\s+выписке|дальнейшее\s+наблюдение|постоянная\s+терапия|терапия\s+в\s+стационаре)",
    ],
}


def segment_document(text: str) -> dict:
    """Сегментация текста по SECTION_PATTERNS.

    Возвращает {group_name: text_chunk, ..., "full": text}.

    Перекрытия матчей разрешаются так: матч, начинающийся внутри уже
    принятого интервала, отбрасывается. Кусок текста между end текущего
    матча и start следующего не теряется — берётся text[start:next_start].
    """
    raw_matches = []
    for name, patterns in SECTION_PATTERNS.items():
        for pat in patterns:
            for m in re.finditer(pat, text):
                raw_matches.append((name, m.start(), m.end()))

    if not raw_matches:
        return {"full": text}

    # Сортировка: по start, затем по длине матча (длиннее = специфичнее)
    raw_matches.sort(key=lambda x: (x[1], -(x[2] - x[1])))

    # Отбрасываем перекрытия
    matches = []
    last_end = -1
    for name, start, end in raw_matches:
        if start < last_end:
            continue
        matches.append((name, start, end))
        last_end = end

    segments = {"full": text}
    for i, (name, start, _end) in enumerate(matches):
        next_start = matches[i + 1][1] if i + 1 < len(matches) else len(text)
        chunk = text[start:next_start].strip()
        if not chunk:
            continue
        existing = segments.get(name, "")
        segments[name] = (existing + "\n\n" + chunk).strip() if existing else chunk

    return segments


def process_one(md_path: Path) -> None:
    doc_name = md_path.stem
    try:
        raw = md_path.read_text(encoding="utf-8")
    except Exception as e:
        log_error(doc_name, "read_file", e, {"path": str(md_path)})
        return

    start = time.perf_counter()
    segments = segment_document(raw)
    found = [k for k in segments if k != "full"]
    missing = [g for g in SECTION_PATTERNS if g not in segments or not segments.get(g)]
    lengths = {g: len(segments[g]) for g in found if segments.get(g)}
    elapsed_ms = int((time.perf_counter() - start) * 1000)

    log_step(doc_name, "segmentation", {
        "latency_ms": elapsed_ms,
        "text_length": len(raw),
        "groups_found": len(found),
        "groups_missing": missing,
        "segment_lengths": lengths,
    })


def main():
    if LOG_PATH.exists():
        LOG_PATH.unlink()

    files = sorted(INPUT_DIR.glob("*.md"))

    if not files:
        print(f"Не найдено .md файлов в {INPUT_DIR}/")
        return

    print(f"Найдено документов: {len(files)}")
    print(f"Первый: {files[0].name}")
    print(f"Последний: {files[-1].name}")
    print()

    start = time.perf_counter()

    for i, md_path in enumerate(files, 1):
        try:
            process_one(md_path)
            if i % 10 == 0 or i == len(files):
                print(f"  [{i}/{len(files)}] {md_path.name}")
        except Exception as e:
            log_error(md_path.stem, "process_one", e, {"file": str(md_path)})
            print(f"{md_path.name}: {e}")

    elapsed = time.perf_counter() - start
    print(f"\nГотово за {elapsed:.2f} сек")
    print(f"Файл: {LOG_PATH}")


if __name__ == "__main__":
    main()