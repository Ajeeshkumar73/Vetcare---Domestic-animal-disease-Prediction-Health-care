import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'animal_disease.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from backend.models import Pet, VaccinationReminder, HealthRecord, SymptomCheckResult, ChatMessage, UserProfile

def run_tests():
    print("==========================================")
    print("RUNNING END-TO-END SYSTEM FUNCTIONALITY TESTS")
    print("==========================================")

    client = Client()

    # Clean previous test user if exists
    User.objects.filter(username='testowner').delete()

    # 1. Test Signup
    print("[1/9] Testing User Registration...")
    response = client.post('/signup/', {
        'username': 'testowner',
        'email': 'testowner@example.com',
        'password': 'Password123!',
        'confirm_password': 'Password123!',
        'role': 'pet_owner',
        'phone': '1234567890'
    })
    assert response.status_code == 302, f"Signup failed with status {response.status_code}"
    print(" -> Signup PASS")

    # 2. Test Login
    print("[2/9] Testing Login...")
    login_success = client.login(username='testowner', password='Password123!')
    assert login_success, "Login failed"
    print(" -> Login PASS")

    # 3. Test Pet Profile Creation
    print("[3/9] Testing Pet Profile Management...")
    response = client.post('/pets/add/', {
        'name': 'Buddy',
        'species': 'Dog',
        'breed': 'Golden Retriever',
        'age_years': 3,
        'age_months': 6,
        'gender': 'Male',
        'weight_kg': 28.5,
        'notes': 'Allergic to fleas'
    })
    assert response.status_code == 302, f"Pet creation failed with status {response.status_code}"
    pet = Pet.objects.filter(name='Buddy').first()
    assert pet is not None, "Pet object not saved in DB"
    print(f" -> Pet Profile Created: {pet.name} (ID: {pet.id}) - PASS")

    # 4. Test Symptom Evaluation Engine
    print("[4/9] Testing Symptom Checker Rule Engine...")
    response = client.post('/symptom-checker/', {
        'pet_id': pet.id,
        'symptoms': ['seizures', 'fever', 'vomiting']
    })
    assert response.status_code == 200, f"Symptom checker failed with status {response.status_code}"
    symptom_res = SymptomCheckResult.objects.filter(pet=pet).last()
    assert symptom_res.urgency_level == 'emergency', f"Expected emergency urgency, got {symptom_res.urgency_level}"
    print(f" -> Symptom Engine Urgency Rating: {symptom_res.urgency_level.upper()} - PASS")

    # 5. Test AI Chatbot API
    print("[5/9] Testing AI Care Chatbot API...")
    response = client.post('/api/chat/', data='{"message": "What should I feed my puppy?", "pet_id": ' + str(pet.id) + '}', content_type='application/json')
    assert response.status_code == 200, f"Chatbot API failed with status {response.status_code}"
    json_data = response.json()
    assert json_data['status'] == 'success', "Chatbot status not success"
    assert ChatMessage.objects.filter(pet=pet).count() >= 2, "Chat messages not saved in DB"
    print(" -> Chatbot API & Conversation Storage - PASS")

    # 6. Test Vaccination Reminder Schedule
    print("[6/9] Testing Vaccination Reminders...")
    response = client.post('/reminders/add/', {
        'pet_id': pet.id,
        'vaccine_name': 'Rabies Annual Shot',
        'due_date': '2026-09-15',
        'recurring_months': 12,
        'notes': 'Dr. Smith Clinic'
    })
    assert response.status_code == 302, f"Reminder creation failed with status {response.status_code}"
    rem = VaccinationReminder.objects.filter(pet=pet).first()
    assert rem is not None, "Reminder not saved in DB"
    print(f" -> Vaccination Schedule Created: {rem.vaccine_name} - PASS")

    # 7. Test PDF Medical Record Export
    print("[7/9] Testing PDF Health Record Generation...")
    response = client.get(f'/health-records/export-pdf/{pet.id}/')
    assert response.status_code == 200, f"PDF export failed with status {response.status_code}"
    assert response['Content-Type'] == 'application/pdf', "Content-Type is not application/pdf"
    assert len(response.content) > 500, "Generated PDF is empty"
    print(f" -> PDF Export Successfully Generated ({len(response.content)} bytes) - PASS")

    # 8. Test Analytics & Guidance Views
    print("[8/9] Testing Analytics & Guidance Views...")
    resp_analytics = client.get('/analytics/')
    assert resp_analytics.status_code == 200, "Analytics view failed"
    resp_guidance = client.get('/guidance/')
    assert resp_guidance.status_code == 200, "Guidance list view failed"
    print(" -> Analytics & Guidance Views - PASS")

    # 9. Test Landing Page & AI Disease Prediction Linkage
    print("[9/9] Testing Landing Page & AI Disease Prediction Linking...")
    resp_landing = client.get('/')
    assert resp_landing.status_code == 200, "Landing page view failed"

    resp_diag = client.get('/disease-prediction/')
    assert resp_diag.status_code == 200, "Disease prediction view failed"

    response_save = client.post('/disease-prediction/', {
        'save_to_pet': '1',
        'pet_id': pet.id,
        'pred_disease': 'Lumpy Skin Disease (Simulated AI)',
        'pred_confidence': '94.5',
        'pred_recommendation': 'Isolate animal and apply topical antiseptics.'
    })
    assert response_save.status_code == 302, "Saving AI diagnosis failed"
    record = HealthRecord.objects.filter(pet=pet, record_type='ai_diagnosis').first()
    assert record is not None, "AI Diagnosis record not saved to pet health history"
    print(f" -> Landing Page & AI Diagnosis to Pet Record: {record.title} - PASS")

    print("\n==========================================")
    print("ALL 9 MODULES & AI INTEGRATION PASSED empiric verification!")
    print("==========================================")

if __name__ == '__main__':
    run_tests()
