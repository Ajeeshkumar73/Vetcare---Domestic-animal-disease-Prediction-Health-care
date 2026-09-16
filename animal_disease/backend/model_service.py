import os
import json
import torch
import torch.nn as nn
from torchvision import transforms, models
from PIL import Image
import joblib
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVED_MODELS_DIR = os.path.join(BASE_DIR, "saved_models")

# Global cached models
_imagenet_model = None
_imagenet_categories = None
_symptom_model = None
_symptom_vectorizer = None
_image_disease_model = None
_image_disease_classes = None

# Animal keywords set for ImageNet verification
ANIMAL_KEYWORDS = {
    'dog', 'cat', 'cow', 'ox', 'bull', 'bison', 'horse', 'pig', 'hog', 'swine', 
    'sheep', 'goat', 'lamb', 'ram', 'rabbit', 'hare', 'donkey', 'mule', 'hound', 
    'terrier', 'spaniel', 'retriever', 'shepherd', 'poodle', 'chihuahua', 'husky', 
    'bulldog', 'beagle', 'boxer', 'rottweiler', 'persian', 'siamese', 'cougar', 
    'lion', 'tiger', 'leopard', 'cheetah', 'bear', 'wolf', 'fox', 'deer', 'elk', 
    'moose', 'antelope', 'gazelle', 'camel', 'llama', 'alpaca', 'elephant', 
    'zebra', 'monkey', 'ape', 'chimpanzee', 'gorilla', 'baboon', 'lemur', 
    'kangaroo', 'koala', 'sloth', 'otter', 'badger', 'skunk', 'weasel', 
    'mink', 'ferret', 'seal', 'walrus', 'squirrel', 'beaver', 'hedgehog', 
    'mouse', 'rat', 'hamster', 'guinea pig', 'calf', 'heifer', 'stallion', 
    'mare', 'foal', 'pony', 'colt', 'filly', 'ewe', 'sow', 'boar', 'piglet', 
    'kitten', 'puppy', 'fauna', 'mammal', 'pet', 'livestock', 'doberman', 
    'corgi', 'collie', 'mastiff', 'dermatitis', 'lesion', 'skin', 'fur', 'animal'
}

def get_imagenet_model():
    global _imagenet_model, _imagenet_categories
    if _imagenet_model is None:
        weights = models.MobileNet_V2_Weights.DEFAULT
        _imagenet_model = models.mobilenet_v2(weights=weights)
        _imagenet_model.eval()
        _imagenet_categories = weights.meta["categories"]
    return _imagenet_model, _imagenet_categories

def get_symptom_model():
    global _symptom_model, _symptom_vectorizer
    if _symptom_model is None:
        model_path = os.path.join(SAVED_MODELS_DIR, "symptom_model.joblib")
        vec_path = os.path.join(SAVED_MODELS_DIR, "symptom_vectorizer.joblib")
        if os.path.exists(model_path) and os.path.exists(vec_path):
            _symptom_model = joblib.load(model_path)
            _symptom_vectorizer = joblib.load(vec_path)
    return _symptom_model, _symptom_vectorizer

def get_image_disease_model():
    global _image_disease_model, _image_disease_classes
    if _image_disease_model is None:
        model_path = os.path.join(SAVED_MODELS_DIR, "image_disease_model.pth")
        cls_path = os.path.join(SAVED_MODELS_DIR, "image_classes.json")
        if os.path.exists(model_path) and os.path.exists(cls_path):
            with open(cls_path, 'r') as f:
                raw_cls = json.load(f)
                _image_disease_classes = {int(k): v for k, v in raw_cls.items()}
            
            num_classes = len(_image_disease_classes)
            model = models.mobilenet_v2(weights=None)
            in_features = model.classifier[1].in_features
            model.classifier[1] = nn.Sequential(
                nn.Dropout(0.2),
                nn.Linear(in_features, num_classes)
            )
            model.load_state_dict(torch.load(model_path, map_location=torch.device('cpu')))
            model.eval()
            _image_disease_model = model
    return _image_disease_model, _image_disease_classes

def is_animal_image(image_path):
    """
    Verifies if the uploaded image is an animal using ImageNet classifier.
    Returns (is_animal: bool, detected_class: str, top_confidence: float)
    """
    try:
        model, categories = get_imagenet_model()
        preprocess = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])
        
        img = Image.open(image_path).convert('RGB')
        img_tensor = preprocess(img).unsqueeze(0)
        
        with torch.no_grad():
            output = model(img_tensor)
            probabilities = torch.nn.functional.softmax(output[0], dim=0)
            
        top5_prob, top5_catid = torch.topk(probabilities, 5)
        
        is_animal = False
        detected_label = categories[top5_catid[0].item()]
        top_conf = float(top5_prob[0].item()) * 100
        
        # Check if any top 5 categories match animal keywords
        for i in range(5):
            cat_name = categories[top5_catid[i].item()].lower()
            cat_words = set(cat_name.replace('-', ' ').replace('_', ' ').split())
            if not cat_words.isdisjoint(ANIMAL_KEYWORDS):
                is_animal = True
                detected_label = categories[top5_catid[i].item()]
                break

        return is_animal, detected_label, top_conf
    except Exception as e:
        print(f"Error in animal detection: {e}")
        # Default to True on processing errors to avoid blocking valid images
        return True, "Unknown Animal", 50.0

def predict_symptoms(symptoms_text):
    """
    Predicts animal disease from symptoms text using trained Random Forest model.
    """
    model, vectorizer = get_symptom_model()
    if model is None or vectorizer is None:
        return {"disease": "Model Not Trained", "confidence": 0.0, "alternatives": []}
    
    vec = vectorizer.transform([symptoms_text.lower()])
    probs = model.predict_proba(vec)[0]
    classes = model.classes_
    
    top_indices = np.argsort(probs)[::-1]
    
    top_disease = classes[top_indices[0]]
    top_conf = round(float(probs[top_indices[0]]) * 100, 2)
    
    # Collect top alternative candidates
    alternatives = []
    for idx in top_indices[1:4]:
        if probs[idx] > 0.05:
            alternatives.append({
                "disease": classes[idx],
                "confidence": round(float(probs[idx]) * 100, 2)
            })
            
    return {
        "disease": top_disease,
        "confidence": top_conf,
        "alternatives": alternatives
    }

def predict_image(image_path):
    """
    Predicts skin disease from animal image using trained PyTorch model.
    """
    model, class_dict = get_image_disease_model()
    if model is None or class_dict is None:
        return {"disease": "Model Not Trained", "confidence": 0.0, "alternatives": []}
        
    try:
        preprocess = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])
        
        img = Image.open(image_path).convert('RGB')
        img_tensor = preprocess(img).unsqueeze(0)
        
        with torch.no_grad():
            output = model(img_tensor)
            probs = torch.nn.functional.softmax(output[0], dim=0).cpu().numpy()
            
        top_indices = np.argsort(probs)[::-1]
        
        top_disease = class_dict[top_indices[0]]
        top_conf = round(float(probs[top_indices[0]]) * 100, 2)
        
        alternatives = []
        for idx in top_indices[1:4]:
            if probs[idx] > 0.05:
                alternatives.append({
                    "disease": class_dict[idx],
                    "confidence": round(float(probs[idx]) * 100, 2)
                })
                
        return {
            "disease": top_disease,
            "confidence": top_conf,
            "alternatives": alternatives
        }
    except Exception as e:
        print(f"Error in image prediction: {e}")
        return {"disease": "Error Processing Image", "confidence": 0.0, "alternatives": []}

def predict_multimodal(image_path=None, symptoms_text=None):
    """
    Multimodal prediction orchestrator following business rules:
    - If image upload is NOT an animal image: show warning, fallback to symptoms prediction.
    - If symptoms only: predict with symptoms.
    - If image only & valid animal: predict with image.
    - If both valid image + symptoms: fuse both predictions.
    """
    result = {
        "has_image": False,
        "is_animal": False,
        "detected_animal_label": "",
        "warning_message": "",
        "symptom_prediction": None,
        "image_prediction": None,
        "final_prediction": "",
        "final_confidence": 0.0,
        "recommendation": ""
    }
    
    has_image = bool(image_path and os.path.exists(image_path))
    has_symptoms = bool(symptoms_text and symptoms_text.strip())
    
    result["has_image"] = has_image
    
    if has_image:
        is_animal, detected_label, top_conf = is_animal_image(image_path)
        result["is_animal"] = is_animal
        result["detected_animal_label"] = detected_label
        
        if not is_animal:
            result["warning_message"] = (
                "⚠️ Warning: The uploaded photo does not appear to be an animal image "
                f"(Detected object: '{detected_label}'). Image prediction was skipped. "
                "The analysis below is based strictly on symptoms."
            )
            
    # Decision matrix
    if has_image and result["is_animal"]:
        # Valid image analysis
        img_res = predict_image(image_path)
        result["image_prediction"] = img_res
        
        if has_symptoms:
            sym_res = predict_symptoms(symptoms_text)
            result["symptom_prediction"] = sym_res
            
            # Fused prediction logic
            # If symptom disease matches or relates to image disease, boost confidence
            sym_disease = sym_res["disease"]
            img_disease = img_res["disease"]
            
            if sym_disease.lower() in img_disease.lower() or img_disease.lower() in sym_disease.lower():
                result["final_prediction"] = f"{sym_disease} (Confirmed by Image & Symptoms)"
                result["final_confidence"] = round((sym_res["confidence"] + img_res["confidence"]) / 2, 2)
            else:
                # Primary prediction from symptoms combined with visual indicators
                result["final_prediction"] = f"{sym_disease} / {img_disease}"
                result["final_confidence"] = max(sym_res["confidence"], img_res["confidence"])
                
            result["recommendation"] = (
                f"Multimodal diagnosis performed. Symptom analysis indicated '{sym_disease}' ({sym_res['confidence']}%), "
                f"while visual image analysis indicated '{img_disease}' ({img_res['confidence']}%). "
                "Please consult a certified veterinarian for confirmatory clinical testing."
            )
        else:
            result["final_prediction"] = img_res["disease"]
            result["final_confidence"] = img_res["confidence"]
            result["recommendation"] = (
                f"Visual diagnosis based on uploaded animal photo indicates '{img_res['disease']}' "
                f"with {img_res['confidence']}% confidence."
            )
            
    elif has_symptoms:
        # Symptom-only or Non-animal image fallback
        sym_res = predict_symptoms(symptoms_text)
        result["symptom_prediction"] = sym_res
        result["final_prediction"] = sym_res["disease"]
        result["final_confidence"] = sym_res["confidence"]
        
        rec_prefix = ""
        if has_image and not result["is_animal"]:
            rec_prefix = "Non-animal image detected and skipped. "
            
        result["recommendation"] = (
            f"{rec_prefix}Symptom-based prediction indicates '{sym_res['disease']}' "
            f"with {sym_res['confidence']}% confidence based on reported symptoms."
        )
    else:
        result["final_prediction"] = "Insufficient Data"
        result["final_confidence"] = 0.0
        result["warning_message"] = "⚠️ Please provide animal symptoms or upload a clear animal photo."
        result["recommendation"] = "Enter observed symptoms (e.g. fever, coughing, lethargy) or upload an animal image."
        
    return result
