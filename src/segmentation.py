import re 


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
