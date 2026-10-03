import os
import json
import re

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

PATTERNS = {
    "DATE":   (r"\b\d{2}\s*\.\s*\d{2}\s*\.\s*\d{4}(?!\d)", 0),
    "BP":     (r"артериальное давление[\s:\-=]{0,5}(\d{2,3}\s*/\s*\d{2,3})", 1),
    "BPM":    (r"(?:частота сердечных сокращений|пульс)[\s:\-=]{0,5}(\d{2,3})", 1),
    "KILLIP": (r"Killip\s*(?:IV|III|II|I)(?!\w)", 0),
}


def expand_abbreviations(text):
    """Раскрывает медицинские сокращения на полные формы."""
    for abbr, full in ABBREVIATIONS.items():
        pattern = re.escape(abbr)
        pattern = rf"(?<![А-Яа-яA-Za-z]){pattern}(?![А-Яа-яA-Za-z])"
        text = re.sub(pattern, full, text)
    return text


def process_directory_to_ls_json(input_dir, output_file):
    tasks = []
    
    for filename in os.listdir(input_dir):
        if filename.endswith(".md") or filename.endswith(".txt"):
            filepath = os.path.join(input_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                raw_text = f.read()
            
            # Применяем словарь сокращений к сырому тексту
            text = expand_abbreviations(raw_text)
            
            results = []
            for label, (pattern, group_idx) in PATTERNS.items():
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    results.append({
                        "from_name": "label",
                        "to_name": "text",
                        "type": "labels",
                        "value": {
                            "start": match.start(group_idx),
                            "end": match.end(group_idx),
                            "text": match.group(group_idx),
                            "labels": [label]
                        }
                    })
            
            tasks.append({
                "data": {"text": text},
                "predictions": [{
                    "model_version": "regex_with_abbr",
                    "result": results
                }]
            })

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


process_directory_to_ls_json("participant-kit-realistic-v2-100/documents", "label_studio_import.json")