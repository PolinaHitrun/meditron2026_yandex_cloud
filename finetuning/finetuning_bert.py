import os
import torch
from transformers import AutoTokenizer, AutoModelForTokenClassification, TrainingArguments, Trainer, DataCollatorForTokenClassification
from datasets import Dataset

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
label_list = sorted(list(unique_tags))
label2id = {l: i for i, l in enumerate(label_list)}
id2label = {i: l for i, l in enumerate(label_list)}

for doc in raw_data:
    doc["ner_tags"] = [label2id[tag] for tag in doc["ner_tags"]]

dataset = Dataset.from_list(raw_data)
tokenizer = AutoTokenizer.from_pretrained("cointegrated/rubert-tiny2")

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
                label_ids.append(-100)
            previous_word_idx = word_idx
        labels.append(label_ids)
    tokenized_inputs["labels"] = labels
    return tokenized_inputs

tokenized_dataset = dataset.map(tokenize_and_align_labels, batched=True)

model = AutoModelForTokenClassification.from_pretrained("cointegrated/rubert-tiny2", num_labels=len(label_list), id2label=id2label, label2id=label2id)

training_args = TrainingArguments(
    output_dir="./medical_ner_model",
    learning_rate=2e-5,
    per_device_train_batch_size=16,
    num_train_epochs=5,
    weight_decay=0.01,
    save_strategy="epoch"
)

data_collator = DataCollatorForTokenClassification(tokenizer=tokenizer)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_dataset,
    tokenizer=tokenizer,
    data_collator=data_collator
)

trainer.train()
trainer.save_model("./final_medical_ner_model")