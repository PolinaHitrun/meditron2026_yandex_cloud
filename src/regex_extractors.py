"""Regex-экстракторы под схему из кейса + negation detection."""

import re


# ============================================================
# Negation detection
# ============================================================

NEG_MARKERS = (
    r"(не\s+(выявлен|обнаружен|отмеча|подтвержд|установлен|зарегистрирован"
    r"|провод|выполнял|применял|использовал|назначал|отмечен|определял)"
    r"|отрица|отсутству|нет\b|без\b|не\s+наблюд|не\s+было)"
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
# Экстракторы по группам
# ============================================================

def extract_dates(segment: str) -> dict:
    result = {"admission_date": "не указано", "discharge_date": "не указано"}

    m = re.search(r"(?i)поступил[а]?\s*:?\s*(\d{2}\.\d{2}\.\d{4})", segment)
    if m:
        result["admission_date"] = m.group(1)
    else:
        dates = re.findall(r"\b\d{2}\.\d{2}\.\d{4}\b", segment)
        if len(dates) >= 2:
            result["admission_date"] = dates[1]

    m = re.search(r"(?i)выписан[а]?\s*:?\s*(\d{2}\.\d{2}\.\d{4})", segment)
    if m:
        result["discharge_date"] = m.group(1)
    else:
        dates = re.findall(r"\b\d{2}\.\d{2}\.\d{4}\b", segment)
        if len(dates) >= 3:
            result["discharge_date"] = dates[2]

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

    # ХБП — строка
    m = re.search(r"(?i)(ХБП\s*\d[АБ]?)", segment)
    if m:
        result["ckd"] = m.group(1)

    # ХСН — строка
    m = re.search(r"(?i)(ХСН\s*\d[АБ]?,?\s*ФК\s*\d)", segment)
    if m:
        result["hf"] = m.group(1)
    else:
        m = re.search(r"(?i)(ХСН\s*[\dАБФК,\s]+)", segment)
        if m:
            result["hf"] = m.group(1).strip().rstrip(",")

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
        segment, r"гипертоническая\s+болезнь|артериальная\s+гипертензия|\bГБ\b"
    )
    result["atr_fibril"] = has_positive(
        segment, r"фибрилляция\s+предсердий|трепетание\s+предсердий"
    )
    result["copd"] = has_positive(segment, r"ХОБЛ")
    result["dm"] = has_positive(segment, r"сахарный\s+диабет")
    result["tlt"] = has_positive(
        segment, r"тромболизис|системный\s+тромболизис"
    )

    return result


def extract_admission_exam(segment: str) -> dict:
    result = {
        "bmi": "не указано", "bp": "не указано", "bpm": "не указано",
        "height": "не указано", "rr": "не указано", "smoking": "не указано",
        "spo2": "не указано", "weight": "не указано",
    }

    m = re.search(r"(?i)пульс\s+(\d{2,3})", segment)
    if m:
        result["bpm"] = m.group(1)

    m = re.search(r"(?i)масса\s+тела\s+(\d{2,3})", segment)
    if m:
        result["weight"] = m.group(1)

    m = re.search(r"(?i)ЧДД\s+(\d{1,2})", segment)
    if m:
        result["rr"] = m.group(1)

    m = re.search(r"(?i)SpO2\s+(\d{2,3})", segment)
    if m:
        result["spo2"] = m.group(1)

    m = re.search(r"(?i)рост\s+(\d{3})", segment)
    if m:
        result["height"] = m.group(1)

    m = re.search(r"(?i)ИМТ\s+(\d{1,2}[.,]\d)", segment)
    if m:
        result["bmi"] = m.group(1).replace(",", ".")

    m = re.search(r"(?i)АД\s+(\d{2,3}/\d{2,3})", segment)
    if m:
        result["bp"] = m.group(1)

    s = segment.lower()
    if "не курит" in s:
        result["smoking"] = "Не курит"
    elif "бросил" in s:
        result["smoking"] = "Бросил"
    elif "курит" in s:
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

    m = re.search(r"(?i)ЧСС\s+(\d{2,3})", segment)
    if m:
        result["ecg_bpm"] = m.group(1)

    s = segment.lower()
    if "фибрилляция предсердий" in s or "фибрилляции предсердий" in s:
        result["ecg_rythm"] = "фибрилляция предсердий"
    elif "синусовый ритм" in s:
        result["ecg_rythm"] = "синусовый"

    # Элевация ST — с negation detection
    result["ecg_elevation"] = has_positive(
        segment,
        r"элевац|подъём\s+ST|подъем\s+ST|подъём\s+сегмента\s+ST"
    )

    # АВ-блокада — через has_positive
    result["ecg_avb"] = has_positive(segment, r"АВ-блокада|AV-блокада")

    return result


def extract_echo(segment: str) -> dict:
    result = {
        "echo_ef": "не указано", "echo_lvd": "не указано",
        "echo_lvd_2": "не указано", "echo_mr": "не указано",
        "echo_zone": "не указано",
    }

    m = re.search(r"(?i)ФВ\s+ЛЖ\s+(\d{1,3})", segment)
    if m:
        result["echo_ef"] = m.group(1)

    m = re.search(r"(?i)КДР\s+ЛЖ\s+(\d{2})", segment)
    if m:
        result["echo_lvd"] = m.group(1)

    m = re.search(r"(?i)ЛП\s+(\d{2})", segment)
    if m:
        result["echo_lvd_2"] = m.group(1)

    m = re.search(r"(?i)(митральная\s+регургитация\s+\d\s*ст\.?)", segment)
    if m:
        result["echo_mr"] = m.group(1).strip()

    m = re.search(r"(?i)(гипокинез\s+\S+\s+стенки)", segment)
    if m:
        result["echo_zone"] = m.group(1).strip()

    return result


def extract_xray(segment: str) -> dict:
    result = {"rg_date": "не указано", "rg_pc": "не указано"}

    m = re.search(r"(\d{2}\.\d{2}\.\d{4})", segment)
    if m:
        result["rg_date"] = m.group(1)

    m = re.search(r"(?i)(признаки\s+венозного\s+застоя[^.\n]*)", segment)
    if m and "не получено" not in m.group(1).lower():
        result["rg_pc"] = m.group(1).strip()

    return result


def extract_ca(segment: str) -> dict:
    result = {
        "ca_date": "не указано", "ca_fact": "N",
        "ca_lad": "не указано", "rca": "не указано",
    }

    kag_names = r"(?:каг|коронарографи\w*|коронароангиографи\w*|ангиографи\w*\s+коронарн\w*)"

    # Дата КАГ — привязана к КАГ, а не просто "первая дата"
    m = re.search(rf"(?i){kag_names}\s+от\s+(\d{{2}}\.\d{{2}}\.\d{{4}})", segment)
    if m:
        result["ca_date"] = m.group(1)
    else:
        m = re.search(r"(\d{2}\.\d{2}\.\d{4})", segment)
        if m:
            result["ca_date"] = m.group(1)

    # 1. Отказ
    if re.search(r"(?i)отказ\w*|не\s+выполнена|пациент\w*\s+отказал\w*", segment):
        result["ca_fact"] = "R"
        return result

    # 2. Выполнение — только явные маркеры про КАГ
    performed_patterns = [
        rf"(?i){kag_names}\s+выполнен\w*",                       # "КАГ выполнена"
        rf"(?i)выполнен\w*\s+{kag_names}",                       # "выполнена КАГ"
        rf"(?i)проведен\w*\s+{kag_names}",                       # "проведена коронарография"
        rf"(?i){kag_names}\s+от\s+\d{{2}}\.\d{{2}}\.\d{{4}}",    # "КАГ от 01.01.2020"
        rf"(?i)по\s+(?:данным|результатам)\s+{kag_names}",       # "по данным КАГ"
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
        result["glu"] = m.group(1).replace(",", ".")

    m = re.search(r"(?i)гемоглобин\s+(\d{2,3})", segment)
    if m:
        result["hb"] = m.group(1)

    m = re.search(r"(?i)ХС-ЛПНП\s+(\d{1,2}[.,]\d)", segment)
    if m:
        result["ldl"] = m.group(1).replace(",", ".")

    m = re.search(r"(?i)лейкоциты\s+(\d{1,2}[.,]\d)", segment)
    if m:
        result["leucocytes"] = m.group(1).replace(",", ".")

    m = re.search(r"(?i)тромбоциты\s+(\d{2,3})", segment)
    if m:
        result["thrombocytes"] = m.group(1)

    m = re.search(r"(?i)общий\s+холестерин\s+(\d{1,2}[.,]\d)", segment)
    if m:
        result["tot_chol"] = m.group(1).replace(",", ".")

    if re.search(r"(?i)тропониновый\s+тест\s+—\s+положительный", segment):
        result["card_trop"] = "положительный"
    elif re.search(r"(?i)тропониновый\s+тест\s+—\s+отрицательный", segment):
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
            result["aspirin"] = line
        elif re.search(r"клопидогрел|тикагрелор|прасугрел", low):
            result["2_aag"] = line
        elif re.search(r"периндоприл|рамиприл|лозартан|эналаприл|валсартан", low):
            result["ace_ing_sartan"] = line
        elif re.search(r"апиксабан|ривароксабан|варфарин|дабигатран", low):
            result["anticoagulant"] = line
        elif re.search(r"бисопролол|метопролол|карведилол|небиволол", low):
            result["bb"] = line
        elif re.search(r"аторвастатин|розувастатин|симвастатин", low):
            result["statin"] = line

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