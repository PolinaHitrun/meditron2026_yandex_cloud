import json
import os
from pathlib import Path
import sys
import time
from dotenv import load_dotenv
from yandex_ai_studio_sdk.auth import APIKeyAuth
from yandex_cloud_ml_sdk import YCloudML

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))
from md_to_BIO import expand_abbreviations

CURRENT_DIR = Path(__file__).resolve().parent
ETALON_FILE = CURRENT_DIR / "few_shot_etalon.json"
OUTPUT_DIR = CURRENT_DIR / "synthetic_annotated_jsons"

# Количество синтетических эпикризов для генерации
NUM_SAMPLES = 50

sdk = YCloudML(
    folder_id=os.getenv("FOLDER_ID"),
    auth=APIKeyAuth(api_key=os.getenv("API_KEY")),
)

with open(ETALON_FILE, "r", encoding="utf-8") as f:
  etalons = json.load(f)

# Формируем примеры для few-shot генерации текста вместе с разметкой
example_1 = {
    "text": etalons[0]["text"],
    "entities": etalons[0]["entities"],
}
example_2 = {
    "text": etalons[1]["text"],
    "entities": etalons[1]["entities"],
}

PROMPT = f"""Ты — медицинский генератор клинических данных. Твоя задача — сгенерировать реалистичный выписной эпикриз пациента с острым коронарным синдромом (ОКС) и сразу предоставить точную разметку сущностей для него.

ВАЖНЫЕ ПРАВИЛА:
1. Создавай разнообразные клинические случаи: меняй ФИО, даты, возраст, анамнез, тип ОКС (с элевацией или без элевации ST), показатели ЭКГ, КАГ, лабораторных анализов и назначения.
2. Текст должен быть структурирован строго как в примерах (паспортная часть, диагноз, анамнез, статус, инструментальные исследования, анализы, динамика, рекомендации).
3. Используй термины в раскрытом виде без сокращений (например: "частота сердечных сокращений" вместо "ЧСС", "артериальное давление" вместо "АД", "электрокардиограмма" вместо "ЭКГ").
4. В поле "entities" включай ТОЛЬКО точные подстроки, которые буквально присутствуют в сгенерированном поле "text".

Верни строго валидный JSON следующего формата:
{{
  "text": "Полный текст выписного эпикриза...",
  "entities": {{
    "admission_date": ["..."],
    "discharge_date": ["..."],
    "type_acs": ["..."],
    "diagnosis_icd": ["..."],
    "bp": ["..."],
    "bpm": ["..."],
    ...
  }}
}}

Пример 1:
{json.dumps(example_1, ensure_ascii=False)}

Пример 2:
{json.dumps(example_2, ensure_ascii=False)}
"""


def generate_synthetic_case():
  model = sdk.models.completions("yandexgpt").configure(
      temperature=0.6,  # Умеренная вариативность для генерации разных пациентов
      max_tokens=4000,
  )

  messages = [
      {"role": "system", "text": PROMPT},
      {
          "role": "user",
          "text": (
              "Сгенерируй новый уникальный выписной эпикриз пациента с ОКС и"
              " разметь его в формате JSON."
          ),
      },
  ]

  try:
    result = model.run(messages)
    result_text = result[0].text

    start_idx = result_text.find("{")
    end_idx = result_text.rfind("}") + 1
    if start_idx != -1 and end_idx != 0:
      return json.loads(result_text[start_idx:end_idx])
    else:
      print("JSON не найден в ответе модели.")
      return None

  except json.JSONDecodeError:
    print("Ошибка парсинга JSON от модели.")
    return None
  except Exception as e:
    print(f"Ошибка API: {e}")
    return None


def generate_corpus():
  os.makedirs(OUTPUT_DIR, exist_ok=True)

  generated_count = 0
  sample_id = 1

  while generated_count < NUM_SAMPLES:
    out_filename = f"synthetic-{sample_id:04d}.json"
    out_filepath = OUTPUT_DIR / out_filename

    # Пропускаем, если такой файл уже есть
    if os.path.exists(out_filepath):
      sample_id += 1
      continue

    print(
        f"[{generated_count + 1}/{NUM_SAMPLES}] Генерация"
        f" {out_filename}..."
    )
    case_data = generate_synthetic_case()

    if not case_data or not isinstance(case_data, dict):
      print("Пропуск итерации из-за ошибки генерации, повтор через 2 сек...")
      time.sleep(2.0)
      continue

    raw_text = case_data.get("text", "")
    entities = case_data.get("entities", {})

    if not raw_text or not isinstance(entities, dict):
      print("Некорректный формат ответа, повтор...")
      time.sleep(2.0)
      continue

    # Страховка: дополнительно раскрываем аббревиатуры, если модель их сократила
    expanded_text = expand_abbreviations(raw_text)

    # Верификация и поиск точных смещений подстрок (скрининг)
    verified_entities = []
    for label, substrings in entities.items():
      if not isinstance(substrings, list):
        continue
      for substring in substrings:
        if not isinstance(substring, str) or not substring.strip():
          continue

        if substring in expanded_text:
          start_idx = 0
          while True:
            start_idx = expanded_text.find(substring, start_idx)
            if start_idx == -1:
              break
            verified_entities.append({
                "start": start_idx,
                "end": start_idx + len(substring),
                "text": substring,
                "labels": [label],
            })
            start_idx += len(substring)

    # Приведение к совместимому формату Label Studio
    task_format = {
        "data": {"text": expanded_text},
        "annotations": [{
            "result": [
                {"value": ent, "type": "labels"} for ent in verified_entities
            ]
        }],
    }

    with open(out_filepath, "w", encoding="utf-8") as f:
      json.dump([task_format], f, ensure_ascii=False, indent=2)

    generated_count += 1
    sample_id += 1
    time.sleep(1.5)

  print(f"\nУспешно сгенерировано {generated_count} синтетических документов!")


if __name__ == "__main__":
  generate_corpus()