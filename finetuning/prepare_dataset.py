import os
import json
from pathlib import Path
from razdel import tokenize, sentenize

def text_and_spans_to_conll(text, spans, out_filepath):
    """Превращает текст и координаты сущностей в формат BIO/CoNLL."""
    # Сортируем спаны по индексу начала
    spans.sort(key=lambda x: x[0])
    conll_lines = []
    
    for sent in sentenize(text):
        sent_start = sent.start
        tokens = list(tokenize(sent.text))
        tags = ["O"] * len(tokens)
        
        for s_start, s_end, s_label in spans:
            span_tokens = []
            for idx, t in enumerate(tokens):
                t_start = sent_start + t.start
                t_end = sent_start + t.stop
                
                # Проверяем физическое пересечение токена и спана
                if t_start < s_end and t_end > s_start:
                    span_tokens.append(idx)
                    
            if span_tokens:
                # Защита от наложения конфликтующих тегов (например, одинаковых дат)
                if tags[span_tokens[0]] == "O":
                    tags[span_tokens[0]] = "B-" + s_label
                    for idx in span_tokens[1:]:
                        tags[idx] = "I-" + s_label
        
        for t, tag in zip(tokens, tags):
            conll_lines.append(f"{t.text}\t{tag}")
        conll_lines.append("")
        
    with open(out_filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(conll_lines))


def process_ls_format(json_path, output_dir):
    """Парсер для файлов сгенерированных LLM (формат Label Studio)."""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    for doc_idx, task in enumerate(data):
        text = task.get("data", {}).get("text", "")
        annotations = task.get("annotations", [])
        if not annotations:
            continue
            
        spans = []
        for item in annotations[0].get("result", []):
            if item.get("type") == "labels":
                val = item["value"]
                spans.append((val["start"], val["end"], val["labels"][0]))
                
        base_name = Path(json_path).stem
        out_filename = f"{base_name}_{doc_idx + 1}.conll" if len(data) > 1 else f"{base_name}.conll"
        text_and_spans_to_conll(text, spans, Path(output_dir) / out_filename)


def process_etalon_format(json_path, output_dir):
    """Парсер для few_shot_etalon.json (восстановление индексов из строк)."""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    for doc_idx, doc in enumerate(data):
        text = doc.get("text", "")
        entities = doc.get("entities", {})
        
        spans = []
        for label, substrings in entities.items():
            for substring in substrings:
                start_idx = 0
                while True:
                    start_idx = text.find(substring, start_idx)
                    if start_idx == -1:
                        break
                    spans.append((start_idx, start_idx + len(substring), label))
                    start_idx += len(substring)
                    
        out_filename = f"etalon_{doc_idx + 1}.conll"
        text_and_spans_to_conll(text, spans, Path(output_dir) / out_filename)


def main():
    current_dir = Path(__file__).resolve().parent
    output_dir = current_dir.parent / "ready_for_annotation"
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Читаем эталоны (few_shot_etalon.json)
    etalon_file = current_dir / "few_shot_etalon.json"
    if os.path.exists(etalon_file):
        print(f"Конвертация эталонов: {etalon_file.name}")
        process_etalon_format(etalon_file, output_dir)
        
    # 2. Читаем сгенерированную разметку
    for folder_name in ["llm_annotated_jsons", "synthetic_annotated_jsons"]:
        folder = current_dir / folder_name
        if os.path.exists(folder):
            print(f"Конвертация папки: {folder_name}")
            for filename in os.listdir(folder):
                if filename.endswith(".json"):
                    process_ls_format(os.path.join(folder, filename), output_dir)

    print("\nГотово! Все файлы .conll сохранены в ready_for_annotation.")

if __name__ == "__main__":
    main()