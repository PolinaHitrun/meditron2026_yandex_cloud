import os
import re
import json
import uuid
from razdel import tokenize

ABBREVIATIONS = {
    "мм рт. ст.": "миллиметры ртутного столба",
    "мм.рт.ст.": "миллиметры ртутного столба",
    "мм рт ст": "миллиметры ртутного столба",
    "мм. рт. ст.": "миллиметры ртутного столба",
    "уд/мин": "ударов в минуту",
    "уд.мин": "ударов в минуту",
    "кг/м²": "килограмм на квадратный метр",
    "кг/м2": "килограмм на квадратный метр",
    "мкмоль/л": "микромоль на литр",
    "ммоль/л": "миллимоль на литр",
    "нг/мл": "нанограмм на миллилитр",
    "мг/дл": "миллиграмм на децилитр",
    "г/л": "грамм на литр",
    "Ед/л": "единиц на литр",
    "ед/л": "единиц на литр",
    "×10⁹/л": "×10 в 9 степени на литр",
    "×10⁹": "×10 в 9 степени",

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

PATTERNS = {
    "DATE": (r"\b\d{2}\.\d{2}\.\d{4}(?!\d)", 0),
    "BP": (r"артериальное давление[\s:\-=]{0,5}(\d{2,3}\s*/\s*\d{2,3})", 1),
    "BPM_PULSE": (r"пульс[\s:\-=]{0,5}(\d{2,3})", 1),
    "BPM_ECG": (r"электрокардиограмма[^.]{0,150}?частота сердечных сокращений[\s:\-=]{0,5}(\d{2,3})", 1),
    "KILLIP": (r"Killip\s*(IV|III|II|I)(?!\w)", 1),
}


def normalize_decimal_commas(text):
    return re.sub(r"(\d),(\d)", r"\1.\2", text)

def normalize_dates(text):
    return re.sub(r"(\d{2})\s*\.\s*(\d{2})\s*\.\s*(\d{4})", r"\1.\2.\3", text)

def expand_abbreviations(text):
    for abbr, full in ABBREVIATIONS.items():
        pattern = rf"(?<![А-Яа-яA-Za-z]){re.escape(abbr)}(?![А-Яа-яA-Za-z])"
        text = re.sub(pattern, full, text)
    return text

def find_entities(text):
    entities = []
    for label, (pattern, group) in PATTERNS.items():
        for match in re.finditer(pattern, text, re.IGNORECASE):
            entities.append({
                "start": match.start(group),
                "end": match.end(group),
                "label": label,
                "text": match.group(group),
            })

    entities.sort(key=lambda e: (-(e["end"] - e["start"]), e["start"]))
    resolved = []
    for ent in entities:
        if not any(not (ent["end"] <= acc["start"] or ent["start"] >= acc["end"]) for acc in resolved):
            resolved.append(ent)
    return sorted(resolved, key=lambda e: e["start"])

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
        "data": {
            "text": text
        },
        "predictions": [
            {
                "model_version": "regex-v1",
                "result": spans,
            }
        ],
    }

def process_directory(input_dir, output_ls_json):
    ls_tasks = []
    counter = 1

    for filename in sorted(os.listdir(input_dir)):
        if not (filename.endswith(".md") or filename.endswith(".txt")):
            continue

        filepath = os.path.join(input_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            original_text = f.read()

        text = normalize_decimal_commas(original_text)
        text = normalize_dates(text)
        text = expand_abbreviations(text)

        entities = find_entities(text)

        task = to_label_studio_task(counter, text, entities)
        ls_tasks.append(task)
        counter += 1

    with open(output_ls_json, "w", encoding="utf-8") as f:
        json.dump(ls_tasks, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    process_directory(
        input_dir="participant-kit-realistic-v2-100/documents",
        output_ls_json="label_studio_tasks.json"
    )
