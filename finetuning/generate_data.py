import os
import json
import time
from yandex_cloud_ml_sdk import YCloudML

API_KEY = "API_KEY"  # Замените на ваш реальный API ключ
FOLDER_ID = "b1gb9i2f4erdrpnpmljk"

# Инициализация SDK клиента
sdk = YCloudML(
    folder_id=FOLDER_ID,
    auth=API_KEY,
)

def generate_labels_with_llm(text, prompt):
    # Выбор и настройка модели
    model = sdk.models.completions("gpt://b1gb9i2f4erdrpnpmljk/gpt-oss-20b/latest").configure(
        temperature=0.1,
        max_tokens=2000
    )
    
    messages = [
        {"role": "system", "text": prompt},
        {"role": "user", "text": text}
    ]
    
    try:
        # Синхронный запуск генерации
        result = model.run(messages)
        result_text = result[0].text
        
        # Пытаемся распарсить JSON, отрезая возможный текст до и после
        start_idx = result_text.find('{')
        end_idx = result_text.rfind('}') + 1
        if start_idx != -1 and end_idx != 0:
            json_str = result_text[start_idx:end_idx]
            return json.loads(json_str)
        else:
            print("В ответе модели не найден JSON.")
            return {}
            
    except json.JSONDecodeError:
        print("Ошибка парсинга JSON от модели.")
        return {}
    except Exception as e:
        print(f"Ошибка при обращении к API: {e}")
        return {}

def create_dataset_with_llm(input_dir, output_dir, prompt_template):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for filename in os.listdir(input_dir):
        if filename.endswith(".txt") or filename.endswith(".md"):
            # Пропускаем уже размеченные файлы (эталоны)
            if filename in ["train-0001.md", "train-0021.md"]:
                 continue

            filepath = os.path.join(input_dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                raw_text = f.read()

            print(f"Обработка файла: {filename}")
            
            # В идеале здесь нужно применить expand_abbreviations(raw_text)
            
            # Запускаем LLM
            llm_result = generate_labels_with_llm(raw_text, prompt_template)
            
            # Скрининг: оставляем только те подстроки, которые реально есть в тексте
            verified_entities = []
            for label, substrings in llm_result.items():
                for substring in substrings:
                    if substring in raw_text:
                        # Находим все вхождения подстроки в тексте
                        start_idx = 0
                        while True:
                            start_idx = raw_text.find(substring, start_idx)
                            if start_idx == -1:
                                break
                            verified_entities.append({
                                "start": start_idx,
                                "end": start_idx + len(substring),
                                "label": label,
                                "text": substring
                            })
                            start_idx += len(substring)
            
            # Сохраняем результат в формате Label Studio для последующей конвертации
            task_format = {
                "data": {"text": raw_text},
                "annotations": [{"result": [{"value": ent, "type": "labels"} for ent in verified_entities]}]
            }
            
            out_filepath = os.path.join(output_dir, filename.replace(".md", ".json"))
            with open(out_filepath, "w", encoding="utf-8") as f:
                json.dump([task_format], f, ensure_ascii=False, indent=2)
            
            # Обязательная задержка для соблюдения лимитов API Yandex Cloud (обычно 1 RPS)
            time.sleep(1.5)

# Пример запуска:
# prompt = "Тот самый длинный текст с примерами..."
# create_dataset_with_llm("participant-kit-realistic-v2-100/documents", "llm_annotated_folder", prompt)