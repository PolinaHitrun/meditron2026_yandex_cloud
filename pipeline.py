"""Пакетная обработка эпикризов: input/*.md → result/<stem>.json.

Пайплайн:
  1. прочитать .md,
  2. сегментировать (src.segmentation),
  3. прогнать regex-экстракторы по каждой группе (src.regex_extractors),
  4. собрать JSON по SCHEMA,
  5. ML NER: добрать пропущенные значения с помощью BERT,
  6. записать result/<stem>.json,
  7. залогировать шаги в logs/pipeline.jsonl.
"""

import re
import json
import time
import torch
from pathlib import Path

from src.config import DICTIONARIES_VERSION, PIPELINE_VERSION
from src.logging_utils import log_step, log_error
from src.schema import SCHEMA
from src.segmentation import segment_document
from src.regex_extractors import EXTRACTORS

from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline
from razdel import sentenize

INPUT_DIR = Path("input")
RESULT_DIR = Path("result")
MODEL_PATH = Path("final_medical_ner_model")

# Настройки ML NER

BINARY_KEYS = {"art_hyper", "atr_fibril", "copd", "dm", "tlt", "ecg_avb", "ecg_elevation"}

LABEL_MAP = {
    "admission_date": ("даты эпизода", "admission_date"),
    "discharge_date": ("даты эпизода", "discharge_date"),
    "art_hyper": ("диагноз", "art_hyper"),
    "atr_fibril": ("диагноз", "atr_fibril"),
    "ckd": ("диагноз", "ckd"),
    "copd": ("диагноз", "copd"),
    "diagnosis_icd": ("диагноз", "diagnosis_icd"),
    "dm": ("диагноз", "dm"),
    "hf": ("диагноз", "hf"),
    "killip": ("диагноз", "killip"),
    "mi_localisation": ("диагноз", "mi_localisation"),
    "tlt": ("диагноз", "tlt"),
    "type_acs": ("диагноз", "type_acs"),
    "bmi": ("осмотр при поступлении", "bmi"),
    "bp": ("осмотр при поступлении", "bp"),
    "bpm": ("осмотр при поступлении", "bpm"),
    "height": ("осмотр при поступлении", "height"),
    "rr": ("осмотр при поступлении", "rr"),
    "smoking": ("осмотр при поступлении", "smoking"),
    "spo2": ("осмотр при поступлении", "spo2"),
    "weight": ("осмотр при поступлении", "weight"),
    "ecg_avb": ("ЭКГ", "ecg_avb"),
    "ecg_bpm": ("ЭКГ", "ecg_bpm"),
    "ecg_elevation": ("ЭКГ", "ecg_elevation"),
    "ecg_rythm": ("ЭКГ", "ecg_rythm"),
    "echo_ef": ("ЭХО-КГ", "echo_ef"),
    "echo_lvd": ("ЭХО-КГ", "echo_lvd"),
    "echo_lvd_2": ("ЭХО-КГ", "echo_lvd_2"),
    "echo_mr": ("ЭХО-КГ", "echo_mr"),
    "echo_zone": ("ЭХО-КГ", "echo_zone"),
    "rg_date": ("рентген грудной полости", "rg_date"),
    "rg_pc": ("рентген грудной полости", "rg_pc"),
    "ca_date": ("коронарография", "ca_date"),
    "ca_fact": ("коронарография", "ca_fact"),
    "ca_lad": ("коронарография", "ca_lad"),
    "rca": ("коронарография", "rca"),
    "card_trop": ("Лабораторные данные", "card_trop"),
    "crea": ("Лабораторные данные", "crea"),
    "glu": ("Лабораторные данные", "glu"),
    "hb": ("Лабораторные данные", "hb"),
    "ldl": ("Лабораторные данные", "ldl"),
    "leucocytes": ("Лабораторные данные", "leucocytes"),
    "thrombocytes": ("Лабораторные данные", "thrombocytes"),
    "tot_chol": ("Лабораторные данные", "tot_chol"),
    "2_aag": ("медикаментозная терапия", "2_aag"),
    "ace_ing_sartan": ("медикаментозная терапия", "ace_ing_sartan"),
    "anticoagulant": ("медикаментозная терапия", "anticoagulant"),
    "aspirin": ("медикаментозная терапия", "aspirin"),
    "bb": ("медикаментозная терапия", "bb"),
    "statin": ("медикаментозная терапия", "statin")
}

def format_ner_value(key: str, raw_text: str) -> str:
    """Нормализация сырого текста от BERT под формат хакатона."""
    if key in BINARY_KEYS:
        return "1"
    
    numeric_keys = {"bmi", "bp", "bpm", "height", "rr", "spo2", "weight", "ecg_bpm", "echo_ef", "echo_lvd", "echo_lvd_2", "crea", "glu", "hb", "ldl", "leucocytes", "thrombocytes", "tot_chol"}
    if key in numeric_keys:
        cleaned = raw_text.replace(',', '.')
        match = re.search(r'\d+(?:[./]\d+)?', cleaned)
        if match:
            return match.group(0)
            
    if key == "ca_fact":
        if "отказ" in raw_text.lower(): return "R"
        return "Y"
        
    if key == "killip":
        match = re.search(r'(IV|III|II|I|\d)', raw_text, re.IGNORECASE)
        if match:
            val = match.group(1).upper()
            roman_to_arab = {"I": "1", "II": "2", "III": "3", "IV": "4"}
            return roman_to_arab.get(val, val)
            
    if key == "diagnosis_icd":
        match = re.search(r'[A-ZА-Я]\d{2}(?:\.\d)?', raw_text, re.IGNORECASE)
        if match: return match.group(0)

    return raw_text.strip(".,;: ")

def load_ner_pipeline():
    if not MODEL_PATH.exists():
        print(f"Модель NER не найдена по пути {MODEL_PATH}")
        return None
        
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
    model = AutoModelForTokenClassification.from_pretrained(MODEL_PATH)
    return pipeline(
        "ner", 
        model=model, 
        tokenizer=tokenizer, 
        aggregation_strategy="simple",
        device=device
    )

# Сборка итогового JSON

def _default_value(field_type: str) -> str:
    """Значение по умолчанию для пустого поля, по типу из SCHEMA."""
    if field_type == "binary":
        return "0"
    if field_type == "kag":
        return "N"
    # string / number / date / bp / vessel
    return "не указано"

def build_doc_json(extracted: dict[str, dict]) -> dict:
    """Собирает JSON по SCHEMA из результатов экстракторов."""
    payload: dict[str, dict] = {}

    for group, fields in SCHEMA.items():
        group_result = extracted.get(group) or {}
        group_payload: dict[str, str] = {}

        for field_name, meta in fields.items():
            raw = group_result.get(field_name)

            value = "" if raw is None else str(raw).strip()
            if not value:
                value = _default_value(meta["type"])

            group_payload[field_name] = value

        payload[group] = group_payload

    return payload

# Обработка одного документа

def process_one(md_path: Path, out_dir: Path, ner_pipe) -> dict:
    """Читает, сегментирует, экстрактит, добирает через NER, пишет JSON."""
    doc_name = md_path.stem
    metrics: dict = {"doc": doc_name}

    # 1. Чтение
    t0 = time.perf_counter()
    try:
        text = md_path.read_text(encoding="utf-8")
    except OSError as e:
        log_error(doc_name, "read_file", e, {"path": str(md_path)})
        raise
    metrics["text_length"] = len(text)

    # 2. Сегментация
    t1 = time.perf_counter()
    segments = segment_document(text)
    metrics["segmentation_ms"] = int((time.perf_counter() - t1) * 1000)

    groups_found = [g for g in SCHEMA if segments.get(g)]
    groups_missing = [g for g in SCHEMA if not segments.get(g)]
    metrics["groups_found"] = len(groups_found)
    metrics["groups_missing"] = groups_missing

    # 3. Экстракция (Rules)
    t2 = time.perf_counter()
    extracted: dict[str, dict] = {}
    for group in SCHEMA:
        segment = segments.get(group, "")
        extractor = EXTRACTORS.get(group)
        if extractor is None:
            extracted[group] = {}
            continue
        try:
            extracted[group] = extractor(segment) or {}
        except Exception as e:
            log_error(doc_name, f"extract:{group}", e, {"group": group})
            extracted[group] = {}
    metrics["extraction_ms"] = int((time.perf_counter() - t2) * 1000)

    # 4. Сборка базы
    t3 = time.perf_counter()
    payload = build_doc_json(extracted)
    metrics["build_ms"] = int((time.perf_counter() - t3) * 1000)

    # 5. ML NER
    t_ner = time.perf_counter()
    if ner_pipe:
        for sentence in sentenize(text):
            text_chunk = sentence.text.strip()
            if not text_chunk:
                continue
                
            entities = ner_pipe(text_chunk)
            for ent in entities:
                word = ent['word'].strip()
                label = ent['entity_group']
                score = ent['score']
                
                if len(word) > 1 and score > 0.6 and label in LABEL_MAP:
                    group, key = LABEL_MAP[label]
                    
                    # Проверяем, пустое ли поле (стоит дефолтное значение)
                    current_val = payload[group].get(key)
                    if current_val in ["не указано", "0", "N"]:
                        formatted_val = format_ner_value(key, word)
                        if formatted_val:
                            payload[group][key] = formatted_val
                            
    metrics["ner_ms"] = int((time.perf_counter() - t_ner) * 1000)

    # 6. Запись
    t4 = time.perf_counter()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{doc_name}.json"
    try:
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as e:
        log_error(doc_name, "write_result", e, {"path": str(out_path)})
        raise
    metrics["write_ms"] = int((time.perf_counter() - t4) * 1000)

    metrics["total_ms"] = int((time.perf_counter() - t0) * 1000)
    log_step(doc_name, "done", metrics)

    return {"doc": doc_name, "out_path": str(out_path), **metrics}

# Пакетный прогон

def run_all(input_dir: Path = INPUT_DIR, out_dir: Path = RESULT_DIR) -> list[dict]:
    files = sorted(input_dir.glob("*.md"))
    if not files:
        print(f"Не найдено .md в {input_dir}/")
        return []

    print(f"Документов: {len(files)}")
    print(f"Версии: dictionaries={DICTIONARIES_VERSION}, pipeline={PIPELINE_VERSION}")
    
    print("Инициализация ML NER пайплайна...")
    ner_pipe = load_ner_pipeline()
    if ner_pipe:
        print("Модель успешно загружена в память.")
    print()

    t_start = time.perf_counter()
    results: list[dict] = []

    for i, md_path in enumerate(files, 1):
        try:
            result = process_one(md_path, out_dir, ner_pipe)
            results.append(result)
            if i % 10 == 0 or i == len(files):
                print(f"  [{i}/{len(files)}] {md_path.name}")
        except Exception as e:
            print(f"{md_path.name}: {e}")

    elapsed = time.perf_counter() - t_start
    print(f"\nГотово за {elapsed:.2f} сек")
    print(f"Результаты: {out_dir}/")
    print(f"Обработано: {len(results)}/{len(files)}")

    return results

def main():
    run_all()

if __name__ == "__main__":
    main()