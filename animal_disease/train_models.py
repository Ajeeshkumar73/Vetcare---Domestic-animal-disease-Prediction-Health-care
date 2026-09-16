import os
import glob
import json
import random
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, models
from PIL import Image
import pandas as pd
import numpy as np
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier

# Base Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_DIR = os.path.dirname(BASE_DIR)
DATASETS_DIR = os.path.join(WORKSPACE_DIR, "datasets")
SAVED_MODELS_DIR = os.path.join(BASE_DIR, "saved_models")
os.makedirs(SAVED_MODELS_DIR, exist_ok=True)

print("="*60)
print("1. TRAINING SYMPTOM-BASED DISEASE PREDICTION MODEL")
print("="*60)

csv_path = os.path.join(DATASETS_DIR, "animal disease symsptoms", "cleaned_animal_disease_prediction.csv")

if os.path.exists(csv_path):
    df = pd.read_csv(csv_path)
    print(f"Loaded symptom dataset with {len(df)} records.")
    
    symptom_cols = ['Symptom_1', 'Symptom_2', 'Symptom_3', 'Symptom_4']
    bool_symptom_cols = ['Appetite_Loss', 'Vomiting', 'Diarrhea', 'Coughing', 
                         'Labored_Breathing', 'Lameness', 'Skin_Lesions', 
                         'Nasal_Discharge', 'Eye_Discharge']
    
    combined_texts = []
    for idx, row in df.iterrows():
        text_parts = []
        animal = str(row.get('Animal_Type', '')).strip()
        if animal and animal != 'nan':
            text_parts.append(animal.lower())
            
        for sc in symptom_cols:
            val = str(row.get(sc, '')).strip()
            if val and val.lower() != 'no' and val.lower() != 'nan':
                text_parts.append(val.lower())
                
        for bcol in bool_symptom_cols:
            val = str(row.get(bcol, '')).strip().lower()
            if val == 'yes':
                text_parts.append(bcol.replace('_', ' ').lower())
                
        combined_texts.append(" ".join(text_parts))

    y_symptoms = df['Disease_Prediction'].values

    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1)
    X_tfidf = vectorizer.fit_transform(combined_texts)

    symptom_clf = RandomForestClassifier(n_estimators=150, max_depth=20, random_state=42)
    symptom_clf.fit(X_tfidf, y_symptoms)

    print(f"Symptom model accuracy: {symptom_clf.score(X_tfidf, y_symptoms):.4f}")
    
    joblib.dump(symptom_clf, os.path.join(SAVED_MODELS_DIR, "symptom_model.joblib"))
    joblib.dump(vectorizer, os.path.join(SAVED_MODELS_DIR, "symptom_vectorizer.joblib"))
    print("Symptom model saved successfully!")
else:
    print(f"ERROR: Symptom CSV not found at {csv_path}")


print("\n" + "="*60)
print("2. TRAINING IMAGE-BASED ANIMAL DISEASE CLASSIFIER")
print("="*60)

class_mapping = {
    "healthycows": "Healthy / Normal Skin",
    "lumpycows": "Lumpy Skin Disease",
    "Lumpy Skin": "Lumpy Skin Disease",
    "Normal Skin": "Healthy / Normal Skin",
    "Dermatitis": "Dermatitis",
    "Fungal_infections": "Fungal Infection",
    "Healthy": "Healthy / Normal Skin",
    "Hypersensitivity": "Hypersensitivity / Allergy",
    "demodicosis": "Demodicosis / Mange",
    "ringworm": "Ringworm"
}

class_images = {}

def add_images(sub_path, label):
    if label not in class_images:
        class_images[label] = []
    for ext in ('*.jpg', '*.jpeg', '*.png', '*.JPG', '*.PNG'):
        class_images[label].extend(glob.glob(os.path.join(sub_path, ext)))

# Collect images per class
cow_lumpy_dir = os.path.join(DATASETS_DIR, "Cow lumpy disease dataset")
if os.path.exists(cow_lumpy_dir):
    for sub in os.listdir(cow_lumpy_dir):
        sub_path = os.path.join(cow_lumpy_dir, sub)
        if os.path.isdir(sub_path) and sub in class_mapping:
            add_images(sub_path, class_mapping[sub])

dog_skin_dir = os.path.join(DATASETS_DIR, "Dog's skin diseases")
if os.path.exists(dog_skin_dir):
    for split in ['train', 'valid']:
        split_dir = os.path.join(dog_skin_dir, split)
        if os.path.exists(split_dir):
            for sub in os.listdir(split_dir):
                sub_path = os.path.join(split_dir, sub)
                if os.path.isdir(sub_path) and sub in class_mapping:
                    add_images(sub_path, class_mapping[sub])

lumpy_dataset_dir = os.path.join(DATASETS_DIR, "Lumpy Skin Images Dataset", "Lumpy Skin Images Dataset")
if os.path.exists(lumpy_dataset_dir):
    for sub in os.listdir(lumpy_dataset_dir):
        sub_path = os.path.join(lumpy_dataset_dir, sub)
        if os.path.isdir(sub_path) and sub in class_mapping:
            add_images(sub_path, class_mapping[sub])

# Sample up to 150 images per class for fast, balanced training
random.seed(42)
final_paths = []
final_labels = []

for label, paths in class_images.items():
    sampled = random.sample(paths, min(len(paths), 150))
    final_paths.extend(sampled)
    final_labels.extend([label] * len(sampled))

print(f"Sampled {len(final_paths)} images across {len(class_images)} classes.")

if len(final_paths) > 0:
    unique_classes = sorted(list(set(final_labels)))
    class_to_idx = {c: i for i, c in enumerate(unique_classes)}
    idx_to_class = {i: c for i, c in enumerate(unique_classes)}

    class AnimalImageDataset(Dataset):
        def __init__(self, paths, labels, class_map, transform=None):
            self.paths = paths
            self.labels = labels
            self.class_map = class_map
            self.transform = transform

        def __len__(self):
            return len(self.paths)

        def __getitem__(self, idx):
            path = self.paths[idx]
            label_str = self.labels[idx]
            label = self.class_map[label_str]
            try:
                img = Image.open(path).convert('RGB')
            except Exception:
                img = Image.new('RGB', (224, 224), (0, 0, 0))
            if self.transform:
                img = self.transform(img)
            return img, label

    data_transforms = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])

    dataset = AnimalImageDataset(final_paths, final_labels, class_to_idx, transform=data_transforms)
    dataloader = DataLoader(dataset, batch_size=32, shuffle=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training PyTorch MobileNetV2 on device: {device}")

    # Transfer Learning with frozen features
    model = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.DEFAULT)
    for param in model.parameters():
        param.requires_grad = False

    in_features = model.classifier[1].in_features
    model.classifier[1] = nn.Sequential(
        nn.Dropout(0.2),
        nn.Linear(in_features, len(unique_classes))
    )
    model = model.to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.classifier.parameters(), lr=1e-3)

    epochs = 2
    for epoch in range(epochs):
        model.train()
        running_loss = 0.0
        correct = 0
        total = 0

        for inputs, targets in dataloader:
            inputs, targets = inputs.to(device), targets.to(device)
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()

            running_loss += loss.item() * inputs.size(0)
            _, predicted = torch.max(outputs, 1)
            total += targets.size(0)
            correct += (predicted == targets).sum().item()

        epoch_loss = running_loss / total
        epoch_acc = correct / total
        print(f"Epoch [{epoch+1}/{epochs}] Loss: {epoch_loss:.4f} - Accuracy: {epoch_acc:.4f}")

    model_save_path = os.path.join(SAVED_MODELS_DIR, "image_disease_model.pth")
    torch.save(model.state_dict(), model_save_path)
    
    with open(os.path.join(SAVED_MODELS_DIR, "image_classes.json"), "w") as f:
        json.dump(idx_to_class, f, indent=2)

    print("Image Disease model saved successfully to:", model_save_path)
