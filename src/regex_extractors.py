"""Regex-экстракторы под схему из кейса + negation detection.

Учтены ловушки синтетических эпикризов:
- аббревиатуры (КДР ЛЖ, ЛП, ЛПНП, ИМТ, ХБП, ХОБЛ, ХСН, ЧСС, АВ-блокада)
  заменяются полными формами;
- даты могут задаваться через "Период лечения: с ... по ...";
- rg_pc — с учётом отрицаний до и после фразы;
- медикаменты — обрезается нумерация списка;
- smoking — включая "Прекратил(а) курить";
- card_trop — любое тире (—, –, -);
- ca_date = "не указано" при ca_fact = R.
"""

import re


# ============================================================
# Negation detection
# ============================================================

NEG_MARKERS = (
    r"(не\s+(выявлен|обнаружен|отмеча|подтвержд|установлен|зарегистрирован"
    r"|провод|выполнял|применял|использовал|назначал|отмечен|определял"
    r"|получен|зафиксирован)"
    r"|отрица|отсутству|нет\b|без\b|не\s+наблюд|не\s+было|данных\s+за)"
)


def has_positive(segment: str, keyword_pattern: str) -> str:
    """
    Возвращает '1' если keyword упомянут БЕЗ отрицания,
    '0' если с отрицанием или отсутствует.
    """
    for m in re.finditer(keyword_pattern, segment, re.IGNORECASE):
        start = max(0, m.start() - 40)
        end = min(len(segment), m.end() + 40)

        left = segment[start:m.start()]
        right = segment[m.end():end]

        if "." in left:
            left = left[left.rfind(".") + 1:]
        if "." in right:
            right = right[:right.find(".")]

        context = (left + " " + right).lower()

        if re.search(NEG_MARKERS, context):
            return "0"
        return "1"

    return "0"


# ============================================================
# Утилиты
# ============================================================

def _to_float_str(raw: str) -> str:
    """'27,4' -> '27.4'."""
    return raw.replace(",", ".")


def _clean_med_line(line: str) -> str:
    """Убирает нумерацию списка и хвостовые служебные фразы."""
    line = re.sub(r"^\s*(?:\d+[.)]\s*|[-–—•]\s*)", "", line).strip()
    line = re.sub(
        r"\s+(разъяснен\w*|уточня\w*|рекомендован\w*|обсужден\w*)\s*\.?\s*$",
        "",
        line,
        flags=re.IGNORECASE,
    )
    return line.strip()


# ============================================================
# Экстракторы по группам
# ============================================================

def extract_dates(segment: str) -> dict:
    result = {"admission_date": "не указано", "discharge_date": "не указано"}

    # 1. Поступил / Выписан
    m = re.search(r"(?i)поступил[а]?\s*:?\s*(\d{2}\.\d{2}\.\d{4})", segment)
    if m:
        result["admission_date"] = m.group(1)

    m = re.search(r"(?i)выписан[а]?\s*:?\s*(\d{2}\.\d{2}\.\d{4})", segment)
    if m:
        result["discharge_date"] = m.group(1)

    # 2. Дата госпитализации / Дата выписки
    if result["admission_date"] == "не указано":
        m = re.search(
            r"(?i)дата\s+госпитализации\s*:?\s*(\d{2}\.\d{2}\.\d{4})", segment
        )
        if m:
            result["admission_date"] = m.group(1)

    if result["discharge_date"] == "не указано":
        m = re.search(
            r"(?i)дата\s+выписки\s*:?\s*(\d{2}\.\d{2}\.\d{4})", segment
        )
        if m:
            result["discharge_date"] = m.group(1)

    # 3. Период лечения: с DD.MM.YYYY по DD.MM.YYYY
    if result["admission_date"] == "не указано" or result["discharge_date"] == "не указано":
        m = re.search(
            r"(?i)период\s+лечения\s*:?\s*с\s*(\d{2}\.\d{2}\.\d{4})\s+по\s+(\d{2}\.\d{2}\.\d{4})",
            segment,
        )
        if m:
            if result["admission_date"] == "не указано":
                result["admission_date"] = m.group(1)
            if result["discharge_date"] == "не указано":
                result["discharge_date"] = m.group(2)

    return result


def extract_diagnosis(segment: str) -> dict:
    """Диагноз — с negation detection."""
    result = {
        "art_hyper": "0",
        "atr_fibril": "0",
        "ckd": "не указано",
        "copd": "0",
        "diagnosis_icd": "не указано",
        "dm": "0",
        "hf": "не указано",
        "killip": "не указано",
        "mi_localisation": "не указано",
        "tlt": "0",
        "type_acs": "не указано",
    }

    # МКБ-10
    m = re.search(r"\b([A-Z]\d{2}\.\d)\b", segment)
    if m:
        result["diagnosis_icd"] = m.group(1)

    # Killip → число
    m = re.search(r"Killip\s+(IV|III|II|I)\b", segment)
    if m:
        roman = {"I": "1", "II": "2", "III": "3", "IV": "4"}
        result["killip"] = roman[m.group(1)]

    # ХБП — полная форма или аббревиатура
    m = re.search(
        r"(?i)(?:ХБП|хроническ\w+\s+болезн\w+\s+почек)\s*(\d[АБ]?)",
        segment,
    )
    if m:
        result["ckd"] = f"ХБП {m.group(1)}"

    # ХСН — полная форма или аббревиатура
    m = re.search(
        r"(?i)(?:ХСН\s*\d[АБ]?(?:,?\s*ФК\s*\d)?"
        r"|хроническ\w+\s+сердечн\w+\s+недостаточн\w+\s*\d[АБ]?"
        r"(?:,?\s*функциональн\w+\s+класс\s*\d)?)",
        segment,
    )
    if m:
        result["hf"] = m.group(0).strip().rstrip(",")

    # Тип ОКС
    s = segment.lower()
    if "с подъёмом st" in s or "с подъемом st" in s or "с элевацией st" in s:
        result["type_acs"] = "STEMI"
    elif "без подъёма st" in s or "без подъема st" in s:
        result["type_acs"] = "NSTEMI"
    elif "нестабильная стенокардия" in s:
        result["type_acs"] = "NA"

    # Локализация — буква
    if "передней" in s or "передняя" in s:
        result["mi_localisation"] = "A"
    elif "нижней" in s or "нижняя" in s:
        result["mi_localisation"] = "I"
    elif "боковой" in s or "боковая" in s:
        result["mi_localisation"] = "L"
    else:
        result["mi_localisation"] = "N"

    # Бинарные — через has_positive
    result["art_hyper"] = has_positive(
        segment,
        r"гипертоническая\s+болезнь|артериальная\s+гипертензия|\bГБ\b",
    )
    result["atr_fibril"] = has_positive(
        segment, r"фибрилляция\s+предсердий|трепетание\s+предсердий"
    )
    result["copd"] = has_positive(
        segment,
        r"ХОБЛ|хроническ\w+\s+обструктивн\w+\s+болезн\w+\s+лёгк\w*"
        r"|хроническ\w+\s+обструктивн\w+\s+болезн\w+\s+легк\w*",
    )
    result["dm"] = has_positive(
        segment, r"сахарн\w+\s+диабет"
    )
    result["tlt"] = has_positive(
        segment, r"тромболизис|системн\w+\s+тромболизис"
    )

    return result


def extract_admission_exam(segment: str) -> dict:
    result = {
        "bmi": "не указано", "bp": "не указано", "bpm": "не указано",
        "height": "не указано", "rr": "не указано", "smoking": "не указано",
        "spo2": "не указано", "weight": "не указано",
    }

    # Пульс при первичном осмотре
    m = re.search(r"(?i)пульс\s+(\d{2,3})", segment)
    if m:
        result["bpm"] = m.group(1)

    # Масса тела
    m = re.search(r"(?i)масса\s+тела\s+(\d{2,3})", segment)
    if m:
        result["weight"] = m.group(1)

    # ЧДД
    m = re.search(r"(?i)ЧДД\s+(\d{1,2})", segment)
    if m:
        result["rr"] = m.group(1)

    # SpO2
    m = re.search(r"(?i)SpO2\s+(\d{2,3})", segment)
    if m:
        result["spo2"] = m.group(1)

    # Рост
    m = re.search(r"(?i)рост\s+(\d{3})", segment)
    if m:
        result["height"] = m.group(1)

    # ИМТ — полная форма или аббревиатура
    m = re.search(
        r"(?i)(?:ИМТ|индекс\w*\s+массы\s+тела)\s+(\d{1,2}[.,]\d)",
        segment,
    )
    if m:
        result["bmi"] = _to_float_str(m.group(1))

    # АД
    m = re.search(r"(?i)АД\s+(\d{2,3}/\d{2,3})", segment)
    if m:
        result["bp"] = m.group(1)

    # Курение
    s = segment.lower()
    if "не курит" in s:
        result["smoking"] = "Не курит"
    elif re.search(r"бросил\w*|прекратил\w*\s+курить", s):
        result["smoking"] = "Бросил"
    elif re.search(r"\bкурит\b", s):
        result["smoking"] = "Курит"

    return result


def extract_ecg(segment: str) -> dict:
    """ЭКГ — с negation detection."""
    result = {
        "ecg_avb": "0",
        "ecg_bpm": "не указано",
        "ecg_elevation": "0",
        "ecg_rythm": "не указано",
    }

    # ЧСС / частота сердечных сокращений
    m = re.search(
        r"(?i)(?:ЧСС|частота\s+сердечных\s+сокращений)\s+(\d{2,3})",
        segment,
    )
    if m:
        result["ecg_bpm"] = m.group(1)

    # Ритм
    s = segment.lower()
    if "фибрилляция предсердий" in s or "фибрилляции предсердий" in s:
        result["ecg_rythm"] = "фибрилляция предсердий"
    elif "синусовый ритм" in s:
        result["ecg_rythm"] = "синусовый"

    # Элевация ST — с negation detection
    result["ecg_elevation"] = has_positive(
        segment,
        r"элевац|подъём\s+ST|подъем\s+ST|подъём\s+сегмента\s+ST",
    )

    # АВ-блокада — полная форма или аббревиатура
    result["ecg_avb"] = has_positive(
        segment,
        r"АВ-?блокад\w*|AV-?блокад\w*|атриовентрикулярн\w+\s+блокад\w*",
    )

    return result


def extract_echo(segment: str) -> dict:
    result = {
        "echo_ef": "не указано", "echo_lvd": "не указано",
        "echo_lvd_2": "не указано", "echo_mr": "не указано",
        "echo_zone": "не указано",
    }

    # ФВ — "ФВ ЛЖ 45" или "фракция выброса левый желудочек 43"
    m = re.search(
        r"(?i)(?:ФВ\s+ЛЖ|фракци\w+\s+выброса(?:\s+лев\w+\s+желудочк\w*)?)\s+(\d{1,3})",
        segment,
    )
    if m:
        result["echo_ef"] = m.group(1)

    # КДР ЛЖ — "КДР ЛЖ 50" или "конечный диастолический размер ... 50"
    m = re.search(
        r"(?i)(?:КДР\s+ЛЖ|конечн\w+\s+диастолическ\w+\s+размер\w*"
        r"(?:\s+лев\w+\s+желудочк\w*)?)\s+(\d{2})",
        segment,
    )
    if m:
        result["echo_lvd"] = m.group(1)

    # ЛП — "ЛП 43" или "левое предсердие 43"
    m = re.search(
        r"(?i)(?:ЛП|лев\w+\s+предсерди\w*)\s+(\d{2})",
        segment,
    )
    if m:
        result["echo_lvd_2"] = m.group(1)

    # Митральная регургитация
    m = re.search(
        r"(?i)(митральн\w+\s+регургитаци\w+\s+\d\s*ст\.?)",
        segment,
    )
    if m:
        result["echo_mr"] = m.group(1).strip()

    # Зона гипокинеза
    m = re.search(r"(?i)(гипокинез\w*\s+\S+\s+стенк\w*)", segment)
    if m:
        result["echo_zone"] = m.group(1).strip()

    return result


def extract_xray(segment: str) -> dict:
    result = {"rg_date": "не указано", "rg_pc": "не указано"}

    m = re.search(r"(\d{2}\.\d{2}\.\d{4})", segment)
    if m:
        result["rg_date"] = m.group(1)

    # rg_pc — положительные формулировки; отрицания отсекаем
    m = re.search(
        r"(?i)(признак\w*\s+венозн\w+\s+застоя[^.\n]*"
        r"|венозн\w+\s+застой[^.\n]*"
        r"|признак\w*\s+отёка\s+лёгк\w*[^.\n]*"
        r"|признак\w*\s+отека\s+легк\w*[^.\n]*)",
        segment,
    )
    if m:
        fragment = m.group(1).strip()
        low = fragment.lower()
        # Отрицание внутри фрагмента — отсекаем
        if not re.search(
            r"не\s+(выявлен|обнаружен|получен|отмеч|определ)", low
        ):
            # Отрицание до фразы — тоже отсекаем
            before = segment[max(0, m.start() - 60):m.start()].lower()
            if not re.search(
                r"(не\s+(выявлен|обнаружен|получен|отмеч|определ)"
                r"|данных\s+за[^.]*не|отсутств)",
                before,
            ):
                result["rg_pc"] = fragment

    return result


def extract_ca(segment: str) -> dict:
    result = {
        "ca_date": "не указано", "ca_fact": "N",
        "ca_lad": "не указано", "rca": "не указано",
    }

    kag_names = r"(?:каг|коронарографи\w*|коронароангиографи\w*|ангиографи\w*\s+коронарн\w*)"

    # Дата КАГ — привязана к КАГ
    m = re.search(
        rf"(?i){kag_names}\s+от\s+(\d{{2}}\.\d{{2}}\.\d{{4}})", segment
    )
    if m:
        result["ca_date"] = m.group(1)
    else:
        m = re.search(r"(\d{2}\.\d{2}\.\d{4})", segment)
        if m:
            result["ca_date"] = m.group(1)

    # 1. Отказ
    if re.search(
        r"(?i)отказ\w*|не\s+выполнен\w*|пациент\w*\s+отказал\w*"
        r"|предложенн\w+\s+коронарографи\w+\s+не\s+выполнен\w*",
        segment,
    ):
        result["ca_fact"] = "R"
        result["ca_date"] = "не указано"
        return result

    # 2. Выполнение — только явные маркеры
    performed_patterns = [
        rf"(?i){kag_names}\s+выполнен\w*",
        rf"(?i)выполнен\w*\s+{kag_names}",
        rf"(?i)проведен\w*\s+{kag_names}",
        rf"(?i){kag_names}\s+от\s+\d{{2}}\.\d{{2}}\.\d{{4}}",
        rf"(?i)по\s+(?:данным|результатам)\s+{kag_names}",
    ]
    if any(re.search(p, segment) for p in performed_patterns):
        result["ca_fact"] = "Y"
    else:
        return result  # N

    # 3. Стенозы — только если Y
    def stenosis_code(text: str) -> str:
        t = text.lower()
        if "окклюз" in t or re.search(r"\b(?:9\d|100)\s*%", t):
            return "2"
        m = re.search(r"\b(\d{1,3})\s*%", t)
        if m:
            n = int(m.group(1))
            if n >= 90:
                return "2"
            if n >= 50:
                return "1"
            return "0"
        return "не указано"

    m = re.search(r"(?i)ПМЖВ[:\s\-–—]+([^;.]*)", segment)
    if m:
        result["ca_lad"] = stenosis_code(m.group(1))

    m = re.search(r"(?i)(?:ПКА|RCA)[:\s\-–—]+([^;.]*)", segment)
    if m:
        result["rca"] = stenosis_code(m.group(1))

    return result


def extract_labs(segment: str) -> dict:
    result = {
        "card_trop": "не указано", "crea": "не указано", "glu": "не указано",
        "hb": "не указано", "ldl": "не указано", "leucocytes": "не указано",
        "thrombocytes": "не указано", "tot_chol": "не указано",
    }

    m = re.search(r"(?i)креатинин\s+(\d{2,3})", segment)
    if m:
        result["crea"] = m.group(1)

    m = re.search(r"(?i)глюкоза\s+(\d{1,2}[.,]\d)", segment)
    if m:
        result["glu"] = _to_float_str(m.group(1))

    m = re.search(r"(?i)гемоглобин\s+(\d{2,3})", segment)
    if m:
        result["hb"] = m.group(1)

    # ЛПНП — полная форма или аббревиатура
    m = re.search(
        r"(?i)(?:ХС-?ЛПНП|холестерин\w*\s+липопротеинов\s+низкой\s+плотности)"
        r"\s+(\d{1,2}[.,]\d)",
        segment,
    )
    if m:
        result["ldl"] = _to_float_str(m.group(1))

    # Лейкоциты — до/без ×10⁹/л
    m = re.search(r"(?i)лейкоциты\s+(\d{1,2}[.,]\d)", segment)
    if m:
        result["leucocytes"] = _to_float_str(m.group(1))

    # Тромбоциты — до ×10⁹/л
    m = re.search(r"(?i)тромбоциты\s+(\d{2,3})", segment)
    if m:
        result["thrombocytes"] = m.group(1)

    # Общий холестерин
    m = re.search(r"(?i)общий\s+холестерин\s+(\d{1,2}[.,]\d)", segment)
    if m:
        result["tot_chol"] = _to_float_str(m.group(1))

    # Тропонин — любое тире
    if re.search(
        r"(?i)тропонинов\w+\s+тест\s*[—–-]\s*положительн\w*", segment
    ):
        result["card_trop"] = "положительный"
    elif re.search(
        r"(?i)тропонинов\w+\s+тест\s*[—–-]\s*отрицательн\w*", segment
    ):
        result["card_trop"] = "отрицательный"

    return result


def extract_meds(segment: str) -> dict:
    result = {
        "2_aag": "не указано", "ace_ing_sartan": "не указано",
        "anticoagulant": "не указано", "aspirin": "не указано",
        "bb": "не указано", "statin": "не указано",
    }

    lines = [l.strip() for l in segment.split("\n") if l.strip()]

    for line in lines:
        low = line.lower()
        if re.search(r"ацетилсалициловая|аспирин|\bаск\b", low):
            result["aspirin"] = _clean_med_line(line)
        elif re.search(r"клопидогрел|тикагрелор|прасугрел", low):
            result["2_aag"] = _clean_med_line(line)
        elif re.search(r"периндоприл|рамиприл|лозартан|эналаприл|валсартан", low):
            result["ace_ing_sartan"] = _clean_med_line(line)
        elif re.search(r"апиксабан|ривароксабан|варфарин|дабигатран", low):
            result["anticoagulant"] = _clean_med_line(line)
        elif re.search(r"бисопролол|метопролол|карведилол|небиволол", low):
            result["bb"] = _clean_med_line(line)
        elif re.search(r"аторвастатин|розувастатин|симвастатин", low):
            result["statin"] = _clean_med_line(line)

    return result


EXTRACTORS = {
    "даты эпизода": extract_dates,
    "диагноз": extract_diagnosis,
    "осмотр при поступлении": extract_admission_exam,
    "ЭКГ": extract_ecg,
    "ЭХО-КГ": extract_echo,
    "рентген грудной полости": extract_xray,
    "коронарография": extract_ca,
    "Лабораторные данные": extract_labs,
    "медикаментозная терапия": extract_meds,
}