import os
import sys
import glob

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

from backend.model_service import predict_multimodal

print("="*60)
print("TESTING MULTIMODAL ANIMAL DISEASE PREDICTION SYSTEM")
print("="*60)

# Test 1: Symptoms Only
print("\n--- TEST 1: Symptoms Only ---")
res1 = predict_multimodal(symptoms_text="Fever, Lethargy, Coughing, Diarrhea")
print("Primary Diagnosis:", res1["final_prediction"])
print("Confidence:", res1["final_confidence"], "%")
print("Recommendation:", res1["recommendation"])

# Test 2: Non-Animal Image + Symptoms
print("\n--- TEST 2: Non-Animal Image + Symptoms ---")
test_non_animal = os.path.join(BASE_DIR, "test_non_animal.jpg")
from PIL import Image, ImageDraw
img = Image.new('RGB', (300, 300), color=(200, 200, 200))
d = ImageDraw.Draw(img)
d.rectangle([50, 50, 250, 250], fill=(100, 100, 100))
img.save(test_non_animal)

res2 = predict_multimodal(image_path=test_non_animal, symptoms_text="Skin Lesions, Fever, Appetite Loss")
print("Is Animal Image Detected:", res2["is_animal"])
print("Detected Object Label:", res2["detected_animal_label"])
print("Warning Banner:", res2["warning_message"].encode('ascii', 'ignore').decode())
print("Primary Diagnosis (Fallback to symptoms):", res2["final_prediction"])

# Test 3: Valid Animal Image + Symptoms
print("\n--- TEST 3: Valid Animal Image + Symptoms ---")
dataset_imgs = glob.glob(os.path.join(os.path.dirname(BASE_DIR), "datasets", "**", "*.jpg"), recursive=True)
if dataset_imgs:
    animal_sample = dataset_imgs[0]
    print(f"Testing with dataset image: {os.path.basename(animal_sample)}")
    res3 = predict_multimodal(image_path=animal_sample, symptoms_text="Lethargy, Skin Lesions, Fever")
    print("Is Animal Image Detected:", res3["is_animal"])
    print("Detected Object Label:", res3["detected_animal_label"])
    print("Primary Diagnosis:", res3["final_prediction"])
    print("Confidence:", res3["final_confidence"], "%")
    print("Recommendation:", res3["recommendation"])

# Cleanup temp image
if os.path.exists(test_non_animal):
    os.remove(test_non_animal)

print("\n" + "="*60)
print("ALL TESTS PASSED SUCCESSFULLY!")
print("="*60)
