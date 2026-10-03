import os
import re
from razdel import tokenize


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

def convert_to_bio(text):
    text = expand_abbreviations(text)

    entities = []
    for label, (pattern, group) in PATTERNS.items():
        for match in re.finditer(pattern, text, re.IGNORECASE):
            entities.append({
                "start": match.start(group),
                "end": match.end(group),
                "label": label,
            })
    
    tokens = list(tokenize(text))
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
    return "\n".join(bio_output)

def process_directory(input_dir, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    for filename in os.listdir(input_dir):
        if filename.endswith(".md") or filename.endswith(".txt"):
            filepath = os.path.join(input_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                text = f.read()
            
            bio_text = convert_to_bio(text)
            
            output_filename = filename.rsplit('.', 1)[0] + ".conll"
            output_filepath = os.path.join(output_dir, output_filename)
            
            with open(output_filepath, 'w', encoding='utf-8') as out_f:
                out_f.write(bio_text)

process_directory("participant-kit-realistic-v2-100/documents", "ready_for_annotation")
