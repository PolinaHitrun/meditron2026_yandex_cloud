import os
import torch
import numpy as np
import evaluate
from transformers import AutoTokenizer, AutoModelForTokenClassification, TrainingArguments, Trainer, DataCollatorForTokenClassification
from datasets import Dataset
from transformers import EarlyStoppingCallback

def read_conll(dir_path):
    data = []
    for filename in os.listdir(dir_path):
        if filename.endswith(".conll"):
            with open(os.path.join(dir_path, filename), "r", encoding="utf-8") as f:
                words, labels = [], []
                for line in f:
                    line = line.strip()
                    if line:
                        parts = line.split("\t")
                        if len(parts) == 2:
                            words.append(parts[0])
                            labels.append(parts[1])
                    elif words:
                        data.append({"tokens": words, "ner_tags": labels})
                        words, labels = [], []
                if words:
                    data.append({"tokens": words, "ner_tags": labels})
    return data

raw_data = read_conll("ready_for_annotation")

unique_tags = set(tag for doc in raw_data for tag in doc["ner_tags"])
expanded_tags = set(unique_tags)
for tag in unique_tags:
    if tag.startswith("B-"):
        expanded_tags.add("I-" + tag[2:])
label_list = sorted(list(expanded_tags))
label2id = {l: i for i, l in enumerate(label_list)}
id2label = {i: l for i, l in enumerate(label_list)}

for doc in raw_data:
    doc["ner_tags"] = [label2id[tag] for tag in doc["ner_tags"]]

# Инициализируем датасет и сразу разбиваем на train и test (90% / 10%)
dataset = Dataset.from_list(raw_data)
dataset = dataset.train_test_split(test_size=0.1, seed=42)

tokenizer = AutoTokenizer.from_pretrained("DeepPavlov/rubert-base-cased")

def tokenize_and_align_labels(examples):
    tokenized_inputs = tokenizer(examples["tokens"], truncation=True, is_split_into_words=True, max_length=512)
    labels = []
    for i, label in enumerate(examples["ner_tags"]):
        word_ids = tokenized_inputs.word_ids(batch_index=i)
        previous_word_idx = None
        label_ids = []
        for word_idx in word_ids:
            if word_idx is None:
                label_ids.append(-100)
            elif word_idx != previous_word_idx:
                label_ids.append(label[word_idx])
            else:
                # Магия BIO-формата: превращаем B-тег в I-тег для хвостов слов (##-токенов)
                curr_label_id = label[word_idx]
                curr_label_str = id2label[curr_label_id]
                if curr_label_str.startswith("B-"):
                    i_label_str = "I-" + curr_label_str[2:]
                    # Ищем I-тег в словаре. Если его там нет, оставляем как есть
                    label_ids.append(label2id.get(i_label_str, curr_label_id))
                else:
                    label_ids.append(curr_label_id)
            previous_word_idx = word_idx
        labels.append(label_ids)
    tokenized_inputs["labels"] = labels
    return tokenized_inputs

# Маппинг применится к обеим выборкам (train и test)
tokenized_dataset = dataset.map(tokenize_and_align_labels, batched=True)

model = AutoModelForTokenClassification.from_pretrained(
    "DeepPavlov/rubert-base-cased", 
    num_labels=len(label_list), 
    id2label=id2label, 
    label2id=label2id
)

# Загружаем метрику для задачи NER
metric = evaluate.load("seqeval")

def compute_metrics(p):
    predictions, labels = p
    # Выбираем наиболее вероятный класс для каждого токена
    predictions = np.argmax(predictions, axis=2)

    # Убираем специальные токены (-100) из расчета метрик
    true_predictions = [
        [label_list[p] for (p, l) in zip(prediction, label) if l != -100]
        for prediction, label in zip(predictions, labels)
    ]
    true_labels = [
        [label_list[l] for (p, l) in zip(prediction, label) if l != -100]
        for prediction, label in zip(predictions, labels)
    ]

    results = metric.compute(predictions=true_predictions, references=true_labels)
    return {
        "precision": results["overall_precision"],
        "recall": results["overall_recall"],
        "f1": results["overall_f1"],
        "accuracy": results["overall_accuracy"],
    }

# Включаем оценку метрик в конце каждой эпохи
training_args = TrainingArguments(
    output_dir="./medical_ner_model",
    learning_rate=3e-5,         
    per_device_train_batch_size=16,
    per_device_eval_batch_size=16,
    num_train_epochs=12,         # Умеренное число эпох
    weight_decay=0.01,
    lr_scheduler_type="cosine",  # Плавно гасит шаг обучения (предотвращает скачки лосса)
    eval_strategy="epoch",  
    save_strategy="epoch",
    load_best_model_at_end=True,
    metric_for_best_model="f1",
    greater_is_better=True
)

data_collator = DataCollatorForTokenClassification(tokenizer=tokenizer)
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_dataset["train"],
    eval_dataset=tokenized_dataset["test"],
    processing_class=tokenizer,
    data_collator=data_collator,
    compute_metrics=compute_metrics,
    callbacks=[EarlyStoppingCallback(early_stopping_patience=2)]
)

trainer.train()
trainer.save_model("./final_medical_ner_model")
tokenizer.save_pretrained("./final_medical_ner_model")