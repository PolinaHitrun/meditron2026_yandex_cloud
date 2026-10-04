import json
from collections import defaultdict

def create_few_shot_dataset(input_json, output_json):
    with open(input_json, 'r', encoding='utf-8') as f:
        ls_data = json.load(f)

    few_shot_examples = []

    for task in ls_data:
        # Извлекаем исходный текст документа
        text = task.get('data', {}).get('text', '')
        
        # Если документ не имеет финальной разметки, пропускаем его
        if not task.get('annotations'):
            continue
            
        result = task['annotations'][0].get('result', [])
        entities = defaultdict(list)

        # Проходим по всем выделениям и собираем их в словарь
        for item in result:
            if item.get('type') == 'labels':
                val = item['value']
                label = val['labels'][0]
                fragment = val['text']
                
                # Добавляем текстовый фрагмент в список соответствующего тега
                entities[label].append(fragment)

        # Сохраняем эталон: текст + словарь сущностей
        few_shot_examples.append({
            "text": text,
            "entities": dict(entities)
        })

    # Записываем результат в новый файл с отступами для удобного чтения
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(few_shot_examples, f, ensure_ascii=False, indent=2)

# Укажите скачанный из Label Studio файл
create_few_shot_dataset("raw_annotation.json", "few_shot_etalon.json")