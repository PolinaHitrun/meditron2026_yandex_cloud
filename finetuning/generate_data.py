import json
import os
from dotenv import load_dotenv
from pathlib import Path
import sys
import time
from yandex_cloud_ml_sdk import YCloudML
from yandex_ai_studio_sdk.auth import APIKeyAuth

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))
from md_to_BIO import expand_abbreviations

CURRENT_DIR = Path(__file__).resolve().parent
INPUT_DIR = ROOT_DIR / "participant-kit-realistic-v2-100" / "documents"
ETALON_FILE = CURRENT_DIR / "few_shot_etalon.json"
OUTPUT_DIR = CURRENT_DIR / "llm_annotated_jsons"

# Имена файлов, которые уже размечены вручную
ETALON_FILENAMES = {"train-0001.md", "train-0021.md"}

sdk = YCloudML(folder_id=os.getenv("FOLDER_ID"), auth=APIKeyAuth(api_key=os.getenv("API_KEY")))

with open(ETALON_FILE, "r", encoding="utf-8") as f:
  etalons = json.load(f)

PROMPT = f"""Ты — опытный медицинский аналитик. Твоя задача — извлекать именованные сущности и клинические параметры из выписных эпикризов пациентов с острым коронарным синдромом.

КРИТИЧЕСКИ ВАЖНОЕ ПРАВИЛО: 
Ты должен возвращать ТОЛЬКО точные подстроки из оригинального текста. Буква в букву. 
Категорически запрещено: 
- менять падежи или окончания слов;
- исправлять опечатки врачей;
- убирать знаки препинания, если они входят в состав термина в тексте;
- придумывать или вычислять значения.

Верни результат в формате валидного JSON, где ключи — это классы сущностей, а значения — списки найденных в тексте подстрок. Если ни одной сущности определенного класса в тексте нет, просто не включай этот ключ в итоговый JSON.

Пример 1:
Текст эпикриза:
{etalons[0]["text"]}

Ожидаемый ответ:
{json.dumps(etalons[0]["entities"], ensure_ascii=False)}

Пример 2:
Текст эпикриза:
{etalons[1]["text"]}

Ожидаемый ответ:
{json.dumps(etalons[1]["entities"], ensure_ascii=False)}
"""


def generate_labels(text):
  model = sdk.models.completions("yandexgpt").configure(
      temperature=0.1, max_tokens=2000
  )

  messages = [
      {"role": "system", "text": PROMPT},
      {"role": "user", "text": text},
  ]

  try:
    result = model.run(messages)
    result_text = result[0].text

    start_idx = result_text.find("{")
    end_idx = result_text.rfind("}") + 1
    if start_idx != -1 and end_idx != 0:
      return json.loads(result_text[start_idx:end_idx])
    else:
      print("JSON не найден в ответе.")
      return {}

  except json.JSONDecodeError:
    print("Ошибка парсинга JSON.")
    return {}
  except Exception as e:
    print(f"Ошибка API: {e}")
    return {}


def process_corpus():
  os.makedirs(OUTPUT_DIR, exist_ok=True)

  filenames = sorted(os.listdir(INPUT_DIR))

  for filename in filenames:
    if not (filename.endswith(".txt") or filename.endswith(".md")):
      continue

    # 1. Пропускаем эталонные файлы
    if filename in ETALON_FILENAMES:
      print(f"Пропуск эталона: {filename}")
      continue

    out_filepath = os.path.join(
        OUTPUT_DIR, filename.replace(".md", ".json").replace(".txt", ".json")
    )

    # 2. Пропускаем уже сгенерированные файлы (на случай рестарта при обрыве сети)
    if os.path.exists(out_filepath):
      print(f"Уже обработан: {filename}")
      continue

    filepath = os.path.join(INPUT_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
      raw_text = f.read()

    expanded_text = expand_abbreviations(raw_text)

    print(f"Генерация для: {filename}")
    llm_result = generate_labels(expanded_text)

    verified_entities = []
    if isinstance(llm_result, dict):
      for label, substrings in llm_result.items():
        if not isinstance(substrings, list):
          continue
        for substring in substrings:
          # Защита от пустых строк и не-строк
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
                  "labels": [label],  # Важно: список 'labels', а не 'label'
              })
              start_idx += len(substring)

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

    time.sleep(1.5)


if __name__ == "__main__":
  process_corpus()