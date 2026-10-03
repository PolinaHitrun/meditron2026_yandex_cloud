import os
import re
import json
import uuid
from copy import deepcopy
from razdel import tokenize

TEMPLATE = {
    "даты эпизода": {
        "admission_date": "не указано",
        "discharge_date": "не указано",
    },
    "диагноз": {
        "art_hyper": "не указано",
        "atr_fibril": "не указано",
        "ckd": "не указано",
        "copd": "не указано",
        "diagnosis_icd": "не указано",
        "dm": "не указано",
        "hf": "не указано",
        "killip": "не указано",
        "mi_localisation": "не указано",
        "tlt": "не указано",
        "type_acs": "не указано",
    },
    "осмотр при поступлении": {
        "bmi": "не указано",
        "bp": "не указано",
        "bpm": "не указано",
        "height": "не указано",
        "rr": "не указано",
        "smoking": "не указано",
        "spo2": "не указано",
        "weight": "не указано",
    },
    "ЭКГ": {
        "ecg_avb": "не указано",
        "ecg_bpm": "не указано",
        "ecg_elevation": "не указано",
        "ecg_rythm": "не указано",
    },
    "ЭХО-КГ": {
        "echo_ef": "не указано",
        "echo_lvd": "не указано",
        "echo_lvd_2": "не указано",
        "echo_mr": "не указано",
        "echo_zone": "не указано",
    },
    "рентген грудной полости": {
        "rg_date": "не указано",
        "rg_pc": "не указано",
    },
    "коронарография": {
        "ca_date": "не указано",
        "ca_fact": "не указано",
        "ca_lad": "не указано",
        "rca": "не указано",
    },
    "Лабораторные данные": {
        "card_trop": "не указано",
        "crea": "не указано",
        "glu": "не указано",
        "hb": "не указано",
        "ldl": "не указано",
        "leucocytes": "не указано",
        "thrombocytes": "не указано",
        "tot_chol": "не указано",
    },
    "медикаментозная терапия": {
        "2_aag": "не указано",
        "ace_ing_sartan": "не указано",
        "anticoagulant": "не указано",
        "aspirin": "не указано",
        "bb": "не указано",
        "statin": "не указано",
    },
}


# ============================================================
# СЛОВАРЬ АББРЕВИАТУР
# ============================================================
ABBREVIATIONS = {
    "ХС-ЛПНП": "холестерин липопротеинов низкой плотности",
    "АВ-блокада": "атриовентрикулярная блокада",
    "ЭХО-КГ": "эхокардиография",
    "ЭХОКГ": "эхокардиография",
    "ЭхоКГ": "эхокардиография",
    "ОКСбST": "острый коронарный синдром без подъема ST",
    "ОКСпST": "острый коронарный синдром с подъемом ST",
    "МКБ-10": "международная классификация болезней 10 пересмотра",
    "д.р.": "дата рождения",
    "ОКС": "острый коронарный синдром",
    "ИБС": "ишемическая болезнь сердца",
    "ИМ": "инфаркт миокарда",
    "ГБ": "гипертоническая болезнь",
    "ХСН": "хроническая сердечная недостаточность",
    "ХБП": "хроническая болезнь почек",
    "ХОБЛ": "хроническая обструктивная болезнь легких",
    "ОНМК": "острое нарушение мозгового кровообращения",
    "СД": "сахарный диабет",
    "ФК": "функциональный класс",
    "ст.": "стадия",
    "АД": "артериальное давление",
    "ЧСС": "частота сердечных сокращений",
    "ЧДД": "частота дыхательных движений",
    "SpO2": "сатурация кислорода",
    "ИМТ": "индекс массы тела",
    "ЭКГ": "электрокардиограмма",
    "КАГ": "коронарография",
    "ОГК": "органы грудной клетки",
    "КДР": "конечный диастолический размер",
    "ЛЖ": "левый желудочек",
    "ЛП": "левое предсердие",
    "ФВ": "фракция выброса",
    "ПМЖВ": "передняя межжелудочковая ветвь",
    "ПКА": "правая коронарная артерия",
    "ЛКА": "левая коронарная артерия",
    "ОА": "огибающая артерия",
    "ОАК": "общий анализ крови",
    "ОАМ": "общий анализ мочи",
    "БАК": "биохимический анализ крови",
    "АЛТ": "аланинаминотрансфераза",
    "АСТ": "аспартатаминотрансфераза",
    "ЛПНП": "липопротеины низкой плотности",
    "ЛПВП": "липопротеины высокой плотности",
    "ТГ": "триглицериды",
    "СКФ": "скорость клубочковой фильтрации",
    "ХС": "холестерин",
    "АСК": "ацетилсалициловая кислота",
    "ЧКВ": "чрескожное коронарное вмешательство",
    "АКШ": "аортокоронарное шунтирование",
    "ТЛТ": "тромболитическая терапия",
    "МКБ": "международная классификация болезней",
    "СМП": "скорая медицинская помощь",
}
ABBREVIATIONS = dict(
    sorted(ABBREVIATIONS.items(), key=lambda x: -len(x[0]))
)


# ============================================================
# ПАТТЕРНЫ
# Формат: label -> (pattern, group)
#   group = 0 — размечаем всё совпадение (для BIO)
#   group = 1 — размечаем только группу (для BIO)
# Для evidence сохраняем match_start/match_end всего совпадения.
# ============================================================
PATTERNS = {
    "ADMISSION_DATE": (
        r"(?:Поступил[а]?|Дата госпитализации|дата госпитализации)"
        r"[\s:\-]{0,5}(\d{2}\.\d{2}\.\d{4})",
        1,
    ),
    "DISCHARGE_DATE": (
        r"(?:Выписан[а]?|Дата выписки|дата выписки)"
        r"[\s:\-]{0,5}(\d{2}\.\d{2}\.\d{4})",
        1,
    ),
    "DATE": (
        r"\b\d{2}\.\d{2}\.\d{4}(?!\d)",
        0,
    ),
    "BP": (
        r"артериальное давление[\s:\-=]{0,5}(\d{2,3}\s*/\s*\d{2,3})",
        1,
    ),
    "BPM_PULSE": (
        r"пульс[\s:\-=]{0,5}(\d{2,3})",
        1,
    ),
    "BPM_ECG": (
        r"электрокардиограмма[^.]{0,150}?частота сердечных сокращений"
        r"[\s:\-=]{0,5}(\d{2,3})",
        1,
    ),
    "KILLIP": (
        r"Killip\s*(IV|III|II|I)(?!\w)",
        1,
    ),
}


# ============================================================
# НОРМАЛИЗАЦИЯ
# ============================================================
def normalize_decimal_commas(text):
    """4,6 → 4.6 (только между цифрами)."""
    return re.sub(r"(\d),(\d)", r"\1.\2", text)


def normalize_dates(text):
    """24 . 10 . 2024 → 24.10.2024."""
    return re.sub(
        r"(\d{2})\s*\.\s*(\d{2})\s*\.\s*(\d{4})",
        r"\1.\2.\3",
        text,
    )


def expand_abbreviations(text):
    """Раскрывает сокращения на полные формы."""
    for abbr, full in ABBREVIATIONS.items():
        pattern = re.escape(abbr)
        pattern = rf"(?<![А-Яа-яA-Za-z]){pattern}(?![А-Яа-яA-Za-z])"
        text = re.sub(pattern, full, text)
    return text


# ============================================================
# ПОИСК СУЩНОСТЕЙ
# ============================================================
def find_entities(text):
    """
    Возвращает список сущностей с координатами в text.
    Каждая сущность: start, end (для BIO), match_start, match_end (для evidence),
    label, text (значение).
    """
    entities = []
    for label, (pattern, group) in PATTERNS.items():
        for match in re.finditer(pattern, text, re.IGNORECASE):
            entities.append({
                "start": match.start(group),
                "end": match.end(group),
                "match_start": match.start(),
                "match_end": match.end(),
                "label": label,
                "text": match.group(group),
            })
    entities.sort(key=lambda e: (-(e["end"] - e["start"]), e["start"]))
    resolved = []
    for ent in entities:
        overlap = False
        for acc in resolved:
            if not (ent["end"] <= acc["start"] or ent["start"] >= acc["end"]):
                overlap = True
                break
        if not overlap:
            resolved.append(ent)

    return sorted(resolved, key=lambda e: e["start"])

def make_bio_lines(tokens, entities):
    """Список строк вида 'токен\\tBIO-тег'."""
    bio_output = []
    for token in tokens:
        current_tag = "O"
        for ent in entities:
            if token.start >= ent["start"] and token.stop <= ent["end"]:
                if token.start == ent["start"]:
                    current_tag = f"B-{ent['label']}"
                else:
                    current_tag = f"I-{ent['label']}"
                break
        bio_output.append(f"{token.text}\t{current_tag}")
    return bio_output

def process_document(original_text):
    """
    Полный пайплайн для одного документа.
    Возвращает: expanded_text, entities, bio_lines.
    """
    text = normalize_decimal_commas(original_text)
    text = normalize_dates(text)
    text = expand_abbreviations(text)

    entities = find_entities(text)
    tokens = list(tokenize(text))
    bio_lines = make_bio_lines(tokens, entities)

    return text, entities, bio_lines

LABEL_TO_FIELD = {
    "ADMISSION_DATE": ("даты эпизода", "admission_date"),
    "DISCHARGE_DATE": ("даты эпизода", "discharge_date"),
    "BP": ("осмотр при поступлении", "bp"),
    "BPM_PULSE": ("осмотр при поступлении", "bpm"),
    "BPM_ECG": ("ЭКГ", "ecg_bpm"),
    "KILLIP": ("диагноз", "killip"),
}


def entities_to_json(entities):
    """
    Заполняет шаблон JSON значениями из сущностей.
    Если поле уже заполнено — берём первое вхождение (правило кейса).
    """
    result = deepcopy(TEMPLATE)
    for ent in entities:
        label = ent["label"]
        if label not in LABEL_TO_FIELD:
            continue
        group, key = LABEL_TO_FIELD[label]
        if result[group][key] == "не указано":
            result[group][key] = ent["text"]
    return result


def make_evidence(entities, text):
    evidence = {}
    for ent in entities:
        label = ent["label"]
        if label not in LABEL_TO_FIELD:
            continue
        group, key = LABEL_TO_FIELD[label]
        field_path = f"{group}.{key}"
        if field_path not in evidence:
            fragment = text[ent["match_start"]:ent["match_end"]].strip()
            evidence[field_path] = fragment
    return evidence

def to_label_studio_task(doc_id, text, entities):
    spans = []
    for ent in entities:
        spans.append({
            "id": str(uuid.uuid4())[:8],
            "from_name": "label",
            "to_name": "text",
            "type": "labels",
            "value": {
                "start": ent["start"],
                "end": ent["end"],
                "text": ent["text"],
                "labels": [ent["label"]],
            },
        })

    return {
        "id": doc_id,
        "data": {"text": text},
        "predictions": [
            {"model_version": "regex-v1", "result": spans}
        ],
    }

def process_directory(input_dir, output_conll_dir, output_json_dir, ls_tasks_path):
    os.makedirs(output_conll_dir, exist_ok=True)
    os.makedirs(output_json_dir, exist_ok=True)

    ls_tasks = []
    counter = 1

    for filename in sorted(os.listdir(input_dir)):
        if not (filename.endswith(".md") or filename.endswith(".txt")):
            continue

        filepath = os.path.join(input_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            original_text = f.read()

        expanded_text, entities, bio_lines = process_document(original_text)
        base_name = filename.rsplit(".", 1)[0]

        # 1) CoNLL для Label Studio / обучения NER
        with open(
            os.path.join(output_conll_dir, base_name + ".conll"),
            "w", encoding="utf-8",
        ) as f:
            f.write("\n".join(bio_lines))

        result_json = entities_to_json(entities)
        result_json["_evidence"] = make_evidence(entities, expanded_text)

        with open(
            os.path.join(output_json_dir, base_name + ".json"),
            "w", encoding="utf-8",
        ) as f:
            json.dump(result_json, f, ensure_ascii=False, indent=2)

        ls_tasks.append(to_label_studio_task(counter, expanded_text, entities))
        counter += 1

    with open(ls_tasks_path, "w", encoding="utf-8") as f:
        json.dump(ls_tasks, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    process_directory(
        input_dir="participant-kit-realistic-v2-100/documents",
        output_conll_dir="ready_for_annotation",
        output_json_dir="result",
        ls_tasks_path="label_studio_tasks.json",
    )
