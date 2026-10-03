import os
import re
from razdel import tokenize

PATTERNS = {
    "DATE": r"\b\d{2}\.\d{2}\.\d{4}\b",
    "BP": r"\b\d{2,3}/\d{2,3}\b",
    "BPM": r"(?<=ЧСС )\d{2,3}|(?<=пульс )\d{2,3}",
    "KILLIP": r"Killip\s+[IIVX]+"
}

def convert_to_bio(text):
    entities = []
    for label, pattern in PATTERNS.items():
        for match in re.finditer(pattern, text):
            entities.append({"start": match.start(), "end": match.end(), "label": label})
    
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
    # Создаем папку для готовых файлов, если её нет
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    for filename in os.listdir(input_dir):
        if filename.endswith(".md") or filename.endswith(".txt"):
            filepath = os.path.join(input_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                text = f.read()
            
            bio_text = convert_to_bio(text)
            
            # Формируем имя нового файла и путь для сохранения
            output_filename = filename.rsplit('.', 1)[0] + ".conll"
            output_filepath = os.path.join(output_dir, output_filename)
            
            with open(output_filepath, 'w', encoding='utf-8') as out_f:
                out_f.write(bio_text)

# Укажите папку с исходниками и название новой папки для сохранения
process_directory("participant-kit-realistic-v2-100/documents", "ready_for_annotation")