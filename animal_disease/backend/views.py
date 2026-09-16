import os
from groq import Groq
from django.conf import settings
import json
from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.files.storage import FileSystemStorage
from django.utils import timezone
from django.db.models import Count, Q

# Import models
from .models import (
    UserProfile, Pet, SymptomCheckResult, ChatMessage,
    VaccinationReminder, HealthRecord, WeightLog, GuidanceArticle
)

# Import existing AI disease prediction engine (UNTOUCHED)
from .model_service import predict_multimodal


# ==========================================
# 0. LANDING PAGE
# ==========================================

def landing_view(request):
    pets_count = Pet.objects.count()
    records_count = HealthRecord.objects.count()
    articles_count = GuidanceArticle.objects.count()
    
    context = {
        'pets_count': pets_count,
        'records_count': records_count,
        'articles_count': articles_count,
    }
    return render(request, 'landing.html', context)


# ==========================================
# 1. AUTHENTICATION & USER MANAGEMENT
# ==========================================

def signup_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        role = request.POST.get('role', 'pet_owner')
        phone = request.POST.get('phone', '').strip()

        if not username or not email or not password:
            messages.error(request, "Please fill in all required fields.")
            return render(request, 'auth/signup.html')

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'auth/signup.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username is already taken.")
            return render(request, 'auth/signup.html')

        if User.objects.filter(email=email).exists():
            messages.error(request, "An account with this email already exists.")
            return render(request, 'auth/signup.html')

        user = User.objects.create_user(username=username, email=email, password=password)
        UserProfile.objects.create(user=user, role=role, phone=phone)
        
        login(request, user)
        messages.success(request, f"Welcome to VetCare, {user.username}! Your account has been created.")
        return redirect('dashboard')

    return render(request, 'auth/signup.html')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username_or_email = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        # Allow login via username or email
        user_obj = User.objects.filter(Q(username=username_or_email) | Q(email=username_or_email)).first()
        if user_obj:
            user = authenticate(request, username=user_obj.username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                next_url = request.GET.get('next', 'dashboard')
                return redirect(next_url)
        
        messages.error(request, "Invalid username/email or password.")

    return render(request, 'auth/login.html')


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('login')


def reset_password_view(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        new_password = request.POST.get('new_password', '')
        user = User.objects.filter(email=email).first()
        if user:
            user.set_password(new_password)
            user.save()
            messages.success(request, "Your password has been reset successfully! Please log in.")
            return redirect('login')
        else:
            messages.error(request, "No account found with that email address.")
    return render(request, 'auth/reset_password.html')


# ==========================================
# HELPER: ACTIVE PET CONTEXT
# ==========================================

def get_active_pet(request, user):
    pets = Pet.objects.filter(user=user)
    if not pets.exists():
        return None, pets

    pet_id = request.GET.get('pet_id') or request.session.get('active_pet_id')
    active_pet = None
    if pet_id:
        active_pet = pets.filter(id=pet_id).first()
    
    if not active_pet:
        active_pet = pets.first()

    if active_pet:
        request.session['active_pet_id'] = active_pet.id

    return active_pet, pets


# ==========================================
# 2. DASHBOARD OVERVIEW
# ==========================================

@login_required
def dashboard_view(request):
    user = request.user
    active_pet, pets = get_active_pet(request, user)

    # Global and pet-specific stats
    upcoming_reminders = VaccinationReminder.objects.filter(
        pet__user=user, status='upcoming', due_date__gte=timezone.now().date()
    ).order_by('due_date')[:5]

    overdue_reminders = VaccinationReminder.objects.filter(
        pet__user=user, status='upcoming', due_date__lt=timezone.now().date()
    )

    recent_records = HealthRecord.objects.filter(pet__user=user).select_related('pet')[:6]
    
    # Calculate health score for active pet
    health_score = 100
    health_warnings = []
    if active_pet:
        # Check overdue vaccines
        overdue_count = VaccinationReminder.objects.filter(pet=active_pet, status='upcoming', due_date__lt=timezone.now().date()).count()
        if overdue_count > 0:
            health_score -= (overdue_count * 15)
            health_warnings.append(f"{overdue_count} overdue vaccination(s)")

        # Check recent severe symptom checks
        recent_emergencies = SymptomCheckResult.objects.filter(pet=active_pet, urgency_level='emergency').count()
        if recent_emergencies > 0:
            health_score -= 25
            health_warnings.append("Recent emergency symptom check flagged")

        health_score = max(health_score, 20)

    context = {
        'active_pet': active_pet,
        'pets': pets,
        'upcoming_reminders': upcoming_reminders,
        'overdue_count': overdue_reminders.count(),
        'recent_records': recent_records,
        'health_score': health_score,
        'health_warnings': health_warnings,
        'total_pets': pets.count(),
        'total_records': HealthRecord.objects.filter(pet__user=user).count(),
    }
    return render(request, 'dashboard.html', context)


# ==========================================
# 3. PET PROFILE MANAGEMENT
# ==========================================

@login_required
def pet_list_view(request):
    pets = Pet.objects.filter(user=request.user)
    return render(request, 'pets/pet_list.html', {'pets': pets})


@login_required
def pet_create_view(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        species = request.POST.get('species', 'Dog')
        breed = request.POST.get('breed', 'Unknown')
        age_years = int(request.POST.get('age_years', 0) or 0)
        age_months = int(request.POST.get('age_months', 0) or 0)
        gender = request.POST.get('gender', 'Male')
        weight_kg = float(request.POST.get('weight_kg', 0.0) or 0.0)
        microchip_id = request.POST.get('microchip_id', '').strip()
        notes = request.POST.get('notes', '').strip()
        photo = request.FILES.get('photo')

        pet = Pet.objects.create(
            user=request.user,
            name=name,
            species=species,
            breed=breed,
            age_years=age_years,
            age_months=age_months,
            gender=gender,
            weight_kg=weight_kg,
            microchip_id=microchip_id,
            notes=notes,
            photo=photo
        )

        if weight_kg > 0:
            WeightLog.objects.create(pet=pet, weight_kg=weight_kg)

        request.session['active_pet_id'] = pet.id
        messages.success(request, f"Pet profile for '{pet.name}' created successfully!")
        return redirect('pet_list')

    return render(request, 'pets/pet_form.html', {'title': 'Add New Pet Profile'})


@login_required
def pet_edit_view(request, pet_id):
    pet = get_object_or_404(Pet, id=pet_id, user=request.user)
    if request.method == 'POST':
        pet.name = request.POST.get('name', pet.name).strip()
        pet.species = request.POST.get('species', pet.species)
        pet.breed = request.POST.get('breed', pet.breed).strip()
        pet.age_years = int(request.POST.get('age_years', pet.age_years) or 0)
        pet.age_months = int(request.POST.get('age_months', pet.age_months) or 0)
        pet.gender = request.POST.get('gender', pet.gender)
        
        new_weight = float(request.POST.get('weight_kg', pet.weight_kg) or 0.0)
        if new_weight != pet.weight_kg and new_weight > 0:
            pet.weight_kg = new_weight
            WeightLog.objects.create(pet=pet, weight_kg=new_weight)

        pet.microchip_id = request.POST.get('microchip_id', pet.microchip_id).strip()
        pet.notes = request.POST.get('notes', pet.notes).strip()

        if request.FILES.get('photo'):
            pet.photo = request.FILES.get('photo')

        pet.save()
        messages.success(request, f"Updated profile for '{pet.name}'.")
        return redirect('pet_list')

    return render(request, 'pets/pet_form.html', {'pet': pet, 'title': f'Edit {pet.name}'})


@login_required
def pet_delete_view(request, pet_id):
    pet = get_object_or_404(Pet, id=pet_id, user=request.user)
    if request.method == 'POST':
        name = pet.name
        pet.delete()
        messages.success(request, f"Pet profile for '{name}' was deleted.")
        return redirect('pet_list')
    return render(request, 'pets/pet_confirm_delete.html', {'pet': pet})


@login_required
def switch_active_pet_view(request, pet_id):
    pet = get_object_or_404(Pet, id=pet_id, user=request.user)
    request.session['active_pet_id'] = pet.id
    next_url = request.META.get('HTTP_REFERER', 'dashboard')
    return redirect(next_url)


# ==========================================
# 4. SYMPTOM-BASED DISEASE ANALYSIS (RULE-BASED)
# ==========================================

SYMPTOM_CATALOG = {
    'General & Vital Signs': [
        ('fever', 'High Fever / Abnormally Hot Ears & Nose'),
        ('lethargy', 'Severe Lethargy / Extreme Fatigue'),
        ('appetite_loss', 'Loss of Appetite (Anorexia)'),
        ('weight_loss', 'Unexplained Rapid Weight Loss'),
        ('dehydration', 'Dehydration (Tacky Gums / Sunken Eyes)'),
        ('weakness', 'Muscle Weakness / Collapse'),
    ],
    'Gastrointestinal System': [
        ('vomiting', 'Vomiting / Retching'),
        ('diarrhea', 'Diarrhea / Watery Stool'),
        ('bloody_stool', 'Bloody Stool or Black Tar-like Stool'),
        ('constipation', 'Inability to Defecate / Straining'),
        ('bloat', 'Abdominal Swelling / Hard Tense Stomach'),
        ('salivation', 'Excessive Drooling / Hypersalivation'),
    ],
    'Respiratory & Circulatory': [
        ('coughing', 'Persistent Coughing / Gagging'),
        ('sneezing', 'Frequent Sneezing / Nasal Discharge'),
        ('labored_breathing', 'Difficulty Breathing / Panting / Wheezing'),
        ('pale_gums', 'Pale, White, or Blueish Gums'),
    ],
    'Dermatological & Skin': [
        ('itching', 'Intense Scratching / Biting Skin'),
        ('hair_loss', 'Patchy Hair Loss / Alopecia'),
        ('skin_lesions', 'Red Rashes, Pustules, or Scabs'),
        ('lumps', 'Lumps, Bumps, or Swellings'),
    ],
    'Neurological & Musculoskeletal': [
        ('seizures', 'Seizures, Tremors, or Involuntary Twitching'),
        ('disorientation', 'Disorientation / Wandering / Staring at Walls'),
        ('limping', 'Limping, Lameness, or Joint Stiffness'),
        ('head_tilt', 'Head Tilt / Loss of Balance'),
    ]
}


@login_required
def symptom_checker_view(request):
    active_pet, pets = get_active_pet(request, user=request.user)
    evaluation_result = None

    if request.method == 'POST':
        selected_symptoms = request.POST.getlist('symptoms')
        pet_id = request.POST.get('pet_id')
        selected_pet = pets.filter(id=pet_id).first() if pet_id else active_pet

        # Rule-Based Decision Tree Logic
        urgency = 'mild'
        possible_conditions = []
        recommendations = []

        # Critical / Emergency Rules
        emergency_indicators = {'seizures', 'labored_breathing', 'bloody_stool', 'bloat', 'pale_gums', 'weakness'}
        moderate_indicators = {'fever', 'vomiting', 'diarrhea', 'dehydration', 'head_tilt', 'disorientation'}

        matched_emergencies = [s for s in selected_symptoms if s in emergency_indicators]
        matched_moderates = [s for s in selected_symptoms if s in moderate_indicators]

        if matched_emergencies or len(selected_symptoms) >= 4:
            urgency = 'emergency'
        elif matched_moderates or len(selected_symptoms) >= 2:
            urgency = 'moderate'

        # Disease / Condition Rule Mapping
        s_set = set(selected_symptoms)
        
        if {'fever', 'lethargy', 'appetite_loss', 'vomiting', 'diarrhea'}.issubset(s_set) or {'bloody_stool', 'vomiting'}.issubset(s_set):
            possible_conditions.append({
                'name': 'Severe Gastrointestinal / Viral Infection (e.g. Parvovirus / Panleukopenia)',
                'severity': 'Critical',
                'description': 'High risk of severe dehydration and systemic viral complication.'
            })

        if {'coughing', 'sneezing', 'labored_breathing'}.intersection(s_set):
            possible_conditions.append({
                'name': 'Upper Respiratory Tract Infection / Kennel Cough / Pneumonia',
                'severity': 'Moderate to Severe',
                'description': 'Bacterial or viral respiratory inflammation requiring isolation and supportive therapy.'
            })

        if {'itching', 'hair_loss', 'skin_lesions'}.intersection(s_set):
            possible_conditions.append({
                'name': 'Dermatitis / Fungal Infection (Ringworm) / Flea Allergy',
                'severity': 'Mild to Moderate',
                'description': 'Skin inflammation requiring topical treatment, antifungal shampoo, or antiparasitic therapy.'
            })

        if {'seizures', 'head_tilt', 'disorientation'}.intersection(s_set):
            possible_conditions.append({
                'name': 'Neurological Disturbance / Vestibular Disease / Toxicity',
                'severity': 'EMERGENCY',
                'description': 'Requires immediate veterinary neurology evaluation and toxin screening.'
            })

        if {'limping', 'weakness'}.intersection(s_set):
            possible_conditions.append({
                'name': 'Musculoskeletal Injury / Joint Dysplasia / Fracture',
                'severity': 'Moderate',
                'description': 'Restrict physical activity and obtain orthopedic X-rays.'
            })

        if not possible_conditions:
            possible_conditions.append({
                'name': 'Non-Specific Mild Indisposition',
                'severity': 'Mild',
                'description': 'Monitor animal closely, ensure fresh clean drinking water and a peaceful resting spot.'
            })

        # Generate Action Recommendations
        if urgency == 'emergency':
            recommendations.append("🚨 CRITICAL: Seek immediate emergency veterinary attention!")
            recommendations.append("Keep the animal calm, warm, and transport to the nearest veterinary emergency clinic right away.")
            recommendations.append("Do not attempt to force feed or administer human medication.")
        elif urgency == 'moderate':
            recommendations.append("⚠️ Schedule a veterinary consultation within 24 hours.")
            recommendations.append("Provide fresh water, keep resting area clean, and monitor body temperature.")
            recommendations.append("Record any changes in vomiting frequency or stool consistency for your vet.")
        else:
            recommendations.append("✅ Monitor at home for 24-48 hours.")
            recommendations.append("Ensure regular nutritious food, clean water, and ample rest.")
            recommendations.append("If symptoms worsen or fever persists, consult your local vet.")

        # Readable symptom names
        symptom_labels = []
        for cat, sym_list in SYMPTOM_CATALOG.items():
            for code, name in sym_list:
                if code in selected_symptoms:
                    symptom_labels.append(name)

        # Save result to DB
        result_obj = SymptomCheckResult.objects.create(
            user=request.user,
            pet=selected_pet,
            symptoms=symptom_labels,
            possible_conditions=possible_conditions,
            urgency_level=urgency,
            recommendations="\n".join(recommendations)
        )

        # Automatically link into Health Record if pet is selected
        if selected_pet:
            HealthRecord.objects.create(
                pet=selected_pet,
                record_type='symptom_check',
                title=f"Symptom Check ({urgency.upper()})",
                description=f"Symptoms: {', '.join(symptom_labels)}\n\nPrimary Finding: {possible_conditions[0]['name']}\n\nUrgency: {urgency.capitalize()}",
                record_date=timezone.now().date()
            )

        evaluation_result = result_obj
        messages.success(request, "Symptom analysis completed and logged to health records.")

    context = {
        'symptom_catalog': SYMPTOM_CATALOG,
        'active_pet': active_pet,
        'pets': pets,
        'evaluation_result': evaluation_result,
    }
    return render(request, 'symptoms/symptom_checker.html', context)


# ==========================================
# 5. VIRTUAL PET CARE CHATBOT (SERVICE & UI)
# ==========================================

PET_CARE_KB = {
    'diet': "For healthy pets, provide a balanced species-appropriate diet rich in quality protein. Ensure continuous access to clean, fresh water. Avoid feeding dogs/cats chocolate, onions, garlic, grapes, raisins, avocado, or xylitol.",
    'grooming': "Regular grooming prevents matted fur, skin infections, and hairballs. Brush short coats weekly and long coats daily. Clip nails carefully avoiding the quick, and clean ears with vet-approved cleaner.",
    'vaccination': "Core vaccinations for dogs include Parvovirus, Distemper, Hepatitis, and Rabies. For cats: Feline Panleukopenia, Calicivirus, Rhinotracheitis, and Rabies. Deworm every 3-6 months based on vet guidance.",
    'first_aid': "In an emergency: Keep the pet calm. For bleeding, apply pressure with a clean cloth. For poisoning, collect the packaging and call emergency vet immediately. Never give human pain relievers (aspirin/paracetamol)!",
    'flea': "Use vet-approved topical (spot-on) or oral flea & tick preventatives monthly. Wash pet bedding in hot water and vacuum living areas thoroughly to eliminate flea larvae.",
    'exercise': "Dogs require 30 to 90 minutes of daily exercise tailored to breed and age. Cats benefit from two 10-15 minute interactive play sessions daily using feather wands or laser pointers.",
}


@login_required
def chat_view(request):
    active_pet, pets = get_active_pet(request, user=request.user)
    chat_history = ChatMessage.objects.filter(user=request.user, pet=active_pet) if active_pet else ChatMessage.objects.filter(user=request.user)
    
    context = {
        'active_pet': active_pet,
        'pets': pets,
        'chat_history': chat_history,
    }
    return render(request, 'chatbot/chat.html', context)


def sanitize_bot_response(text):
    if not text:
        return ""
    import re
    # Remove reasoning <think>...</think> blocks
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    # Replace special unicode quotes and hyphens with standard ASCII
    text = text.replace('\u2011', '-').replace('\u2013', '-').replace('\u2014', '-')
    text = text.replace('\u201c', '"').replace('\u201d', '"').replace('\u2018', "'").replace('\u2019', "'")
    # Remove asterisks (*), markdown hashes (#), backticks (`), tildes (~), and underscores (_)
    text = re.sub(r'[\*`#~_]', '', text)
    # Remove emojis
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002700-\U000027BF"
        "\U0001F900-\U0001F9FF"
        "\U0001FA70-\U0001FAFF"
        "\U00002600-\U000026FF"
        "]+",
        flags=re.UNICODE
    )
    text = emoji_pattern.sub('', text)
    # Clean up empty lines and strip leading bullet symbols (-, •, ▪, ‣, numbers like 1.)
    lines = []
    for line in text.splitlines():
        line_str = line.strip()
        # Strip bullet points and list markers at the start of lines
        line_str = re.sub(r'^[•▪‣\-\+\*\d+\.]+\s*', '', line_str)
        if line_str:
            lines.append(line_str)
    return "\n\n".join(lines)


@login_required
def chat_api_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '').strip()
            pet_id = data.get('pet_id')

            if not user_message:
                return JsonResponse({'error': 'Empty message'}, status=400)

            pet = Pet.objects.filter(id=pet_id, user=request.user).first() if pet_id else None

            # Save user message to DB
            ChatMessage.objects.create(
                user=request.user,
                pet=pet,
                sender='user',
                message=user_message
            )

            # ── Build dynamic system prompt with pet context ──────────────────────
            if pet:
                pet_info = (
                    f"The user's active pet is named {pet.name}, a {pet.gender} {pet.species} "
                    f"(breed: {pet.breed}), aged {pet.age_years} year(s) and {pet.age_months} month(s), "
                    f"weighing {pet.weight_kg} kg."
                )
            else:
                pet_info = "The user has not selected a specific pet yet."

            system_prompt = (
                "You are a VetCare virtual assistant, an expert veterinary assistant.\n"
                f"{pet_info}\n"
                "CRITICAL FORMATTING INSTRUCTIONS:\n"
                "1. Answer ONLY the specific question asked by the user clearly, simply, and directly.\n"
                "2. Do NOT use any asterisks (*), markdown formatting, special symbols, or emojis anywhere.\n"
                "3. Use plain sentences without any bullet point symbols or formatting characters.\n"
                "4. Keep your answer brief, concise, and focused strictly on the question."
            )

            # ── Fetch recent conversation history for multi-turn context ──────────
            history_qs = ChatMessage.objects.filter(
                user=request.user, pet=pet
            ).order_by('-timestamp')[:10]
            history_messages = []
            for msg in reversed(list(history_qs)):
                role = 'user' if msg.sender == 'user' else 'assistant'
                history_messages.append({'role': role, 'content': msg.message})

            # Remove the last message (the user turn we just saved) from history
            if history_messages and history_messages[-1]['content'] == user_message:
                history_messages = history_messages[:-1]

            groq_messages = [
                {'role': 'system', 'content': system_prompt},
                *history_messages,
                {'role': 'user', 'content': user_message},
            ]

            # ── Call Groq API with robust model fallbacks ────────────────────────
            groq_api_key = settings.GROQ_API_KEY
            response_text = None

            if groq_api_key:
                try:
                    client = Groq(api_key=groq_api_key)
                    
                    models_to_try = [
                        'groq/compound',
                        'groq/compound-mini',
                        'qwen/qwen3.6-27b',
                        'openai/gpt-oss-20b',
                        'llama-3.3-70b-versatile',
                        'llama-3.1-8b-instant',
                    ]
                    
                    for model_name in models_to_try:
                        try:
                            completion = client.chat.completions.create(
                                model=model_name,
                                messages=groq_messages,
                                temperature=0.5,
                                max_tokens=600,
                            )
                            raw_text = completion.choices[0].message.content or ""
                            clean_text = sanitize_bot_response(raw_text)
                            if clean_text:
                                response_text = clean_text
                                break
                        except Exception as model_err:
                            continue

                except Exception as api_err:
                    response_text = None

            # ── Knowledge Base Fallback if AI models are unavailable ──────────────
            if not response_text:
                msg_lower = user_message.lower()
                pet_name = pet.name if pet else "your pet"
                
                kb_matches = []
                for key, val in PET_CARE_KB.items():
                    if key in msg_lower or any(word in msg_lower for word in [key, key[:4]]):
                        kb_matches.append(val)
                
                if kb_matches:
                    raw_fallback = f"Advice for {pet_name}:\n\n" + "\n\n".join(kb_matches)
                else:
                    raw_fallback = (
                        f"For {pet_name}, ensure balanced nutrition, fresh water, regular exercise, "
                        "and up-to-date vaccinations. Consult a licensed veterinarian if illness symptoms appear."
                    )
                response_text = sanitize_bot_response(raw_fallback)

            # ── Save bot response to DB ───────────────────────────────────────────
            bot_msg = ChatMessage.objects.create(
                user=request.user,
                pet=pet,
                sender='bot',
                message=response_text
            )

            return JsonResponse({
                'status': 'success',
                'message': response_text,
                'timestamp': bot_msg.timestamp.strftime('%H:%M'),
                'quick_replies': [
                    'Diet & Feeding Tips',
                    'Vaccination Schedule',
                    'Grooming Guide',
                    'Emergency First-Aid',
                ]
            })

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid method'}, status=405)


# ==========================================
# 6. VACCINATION & HEALTH REMINDERS
# ==========================================

@login_required
def reminder_list_view(request):
    active_pet, pets = get_active_pet(request, user=request.user)
    
    reminders = VaccinationReminder.objects.filter(pet__user=request.user).select_related('pet').order_by('due_date')
    if active_pet and request.GET.get('filter') == 'active':
        reminders = reminders.filter(pet=active_pet)

    today = timezone.now().date()
    for r in reminders:
        if r.status == 'upcoming' and r.due_date < today:
            r.is_overdue_flag = True
        else:
            r.is_overdue_flag = False

    context = {
        'reminders': reminders,
        'active_pet': active_pet,
        'pets': pets,
        'today': today,
    }
    return render(request, 'reminders/reminder_list.html', context)


@login_required
def reminder_create_view(request):
    pets = Pet.objects.filter(user=request.user)
    if request.method == 'POST':
        pet_id = request.POST.get('pet_id')
        vaccine_name = request.POST.get('vaccine_name', '').strip()
        due_date_str = request.POST.get('due_date')
        recurring_months = int(request.POST.get('recurring_months', 0) or 0)
        notes = request.POST.get('notes', '').strip()

        pet = get_object_or_404(Pet, id=pet_id, user=request.user)
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        reminder_date = due_date - timedelta(days=7) # alert 7 days before

        VaccinationReminder.objects.create(
            pet=pet,
            vaccine_name=vaccine_name,
            due_date=due_date,
            reminder_date=reminder_date,
            recurring_months=recurring_months,
            notes=notes,
            status='upcoming'
        )

        messages.success(request, f"Reminder for '{vaccine_name}' set for {pet.name}.")
        return redirect('reminder_list')

    return render(request, 'reminders/reminder_form.html', {'pets': pets})


@login_required
def reminder_toggle_view(request, reminder_id):
    reminder = get_object_or_404(VaccinationReminder, id=reminder_id, pet__user=request.user)
    if reminder.status == 'completed':
        reminder.status = 'upcoming'
        reminder.completed_at = None
    else:
        reminder.status = 'completed'
        reminder.completed_at = timezone.now().date()

        # If recurring, automatically create next cycle reminder!
        if reminder.recurring_months > 0:
            next_due = reminder.due_date + timedelta(days=30 * reminder.recurring_months)
            VaccinationReminder.objects.create(
                pet=reminder.pet,
                vaccine_name=reminder.vaccine_name,
                due_date=next_due,
                reminder_date=next_due - timedelta(days=7),
                recurring_months=reminder.recurring_months,
                notes=f"Recurring cycle from completed task on {timezone.now().date()}",
                status='upcoming'
            )
            messages.info(request, f"Completed! Next recurring reminder automatically set for {next_due.strftime('%B %d, %Y')}.")

    reminder.save()
    messages.success(request, f"Updated status for '{reminder.vaccine_name}'.")
    return redirect('reminder_list')


@login_required
def reminder_delete_view(request, reminder_id):
    reminder = get_object_or_404(VaccinationReminder, id=reminder_id, pet__user=request.user)
    reminder.delete()
    messages.success(request, "Reminder deleted.")
    return redirect('reminder_list')


# ==========================================
# 7. DIGITAL HEALTH RECORDS & PDF EXPORT
# ==========================================

@login_required
def health_record_list_view(request):
    active_pet, pets = get_active_pet(request, user=request.user)
    
    records = HealthRecord.objects.filter(pet__user=request.user).select_related('pet')
    record_type = request.GET.get('type')
    if record_type:
        records = records.filter(record_type=record_type)

    if active_pet:
        records = records.filter(pet=active_pet)

    context = {
        'records': records,
        'active_pet': active_pet,
        'pets': pets,
        'selected_type': record_type,
    }
    return render(request, 'health_records/record_list.html', context)


@login_required
def health_record_create_view(request):
    pets = Pet.objects.filter(user=request.user)
    if request.method == 'POST':
        pet_id = request.POST.get('pet_id')
        record_type = request.POST.get('record_type', 'vet_visit')
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        record_date = request.POST.get('record_date') or timezone.now().date()
        attachment = request.FILES.get('attachment')

        pet = get_object_or_404(Pet, id=pet_id, user=request.user)

        HealthRecord.objects.create(
            pet=pet,
            record_type=record_type,
            title=title,
            description=description,
            record_date=record_date,
            attachment=attachment
        )

        messages.success(request, f"Health record '{title}' added for {pet.name}.")
        return redirect('health_record_list')

    return render(request, 'health_records/record_form.html', {'pets': pets})


@login_required
def health_record_export_pdf_view(request, pet_id):
    pet = get_object_or_404(Pet, id=pet_id, user=request.user)
    records = HealthRecord.objects.filter(pet=pet).order_by('-record_date')
    reminders = VaccinationReminder.objects.filter(pet=pet).order_by('due_date')

    # Generate PDF using ReportLab
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    import io

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=22, textColor=colors.HexColor('#1e40af'), spaceAfter=10)
    subtitle_style = ParagraphStyle('SubtitleStyle', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor('#0f172a'), spaceAfter=8)
    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=10, leading=14, textColor=colors.HexColor('#334155'))

    story = []

    # Header Banner
    story.append(Paragraph(f"VetCare - Official Medical & Health Record", title_style))
    story.append(Paragraph(f"Generated on {timezone.now().strftime('%B %d, %Y')} for Owner: <b>{request.user.username}</b>", body_style))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#2563eb'), spaceAfter=15))

    # Pet Summary Table
    pet_data = [
        [Paragraph("<b>Pet Name:</b>", body_style), Paragraph(pet.name, body_style), Paragraph("<b>Species / Breed:</b>", body_style), Paragraph(f"{pet.species} / {pet.breed}", body_style)],
        [Paragraph("<b>Age:</b>", body_style), Paragraph(pet.age_display(), body_style), Paragraph("<b>Gender / Weight:</b>", body_style), Paragraph(f"{pet.gender} ({pet.weight_kg} kg)", body_style)],
        [Paragraph("<b>Microchip ID:</b>", body_style), Paragraph(pet.microchip_id or 'N/A', body_style), Paragraph("<b>Health Score:</b>", body_style), Paragraph("Good / Monitored", body_style)],
    ]
    t = Table(pet_data, colWidths=[100, 160, 120, 160])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 15))

    # Health Records Timeline Section
    story.append(Paragraph("Health Events & Clinical History", subtitle_style))
    rec_table_data = [["Date", "Record Type", "Title & Notes"]]
    for r in records:
        rec_table_data.append([
            r.record_date.strftime('%Y-%m-%d'),
            r.get_record_type_display(),
            Paragraph(f"<b>{r.title}</b><br/>{r.description or ''}", body_style)
        ])

    rt = Table(rec_table_data, colWidths=[80, 120, 340])
    rt.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2563eb')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(rt)
    story.append(Spacer(1, 15))

    # Vaccination Table
    story.append(Paragraph("Vaccination & Preventive History", subtitle_style))
    vac_table_data = [["Vaccine / Task", "Due Date", "Status"]]
    for v in reminders:
        vac_table_data.append([
            v.vaccine_name,
            v.due_date.strftime('%Y-%m-%d'),
            v.get_status_display()
        ])

    vt = Table(vac_table_data, colWidths=[200, 140, 200])
    vt.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0284c7')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(vt)

    doc.build(story)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{pet.name}_Medical_Health_Record.pdf"'
    return response


# ==========================================
# 8. HEALTH REPORTS & ANALYTICS DASHBOARD
# ==========================================

@login_required
def analytics_view(request):
    active_pet, pets = get_active_pet(request, user=request.user)

    # Weight Chart Data
    weight_logs = WeightLog.objects.filter(pet=active_pet).order_by('recorded_date') if active_pet else []
    weight_dates = [w.recorded_date.strftime('%b %d') for w in weight_logs]
    weight_values = [w.weight_kg for w in weight_logs]

    # Vaccination Compliance Gauge Data
    all_reminders = VaccinationReminder.objects.filter(pet=active_pet) if active_pet else VaccinationReminder.objects.filter(pet__user=request.user)
    completed_count = all_reminders.filter(status='completed').count()
    upcoming_count = all_reminders.filter(status='upcoming', due_date__gte=timezone.now().date()).count()
    missed_count = all_reminders.filter(status='upcoming', due_date__lt=timezone.now().date()).count()

    # Record Type Distribution
    record_counts = HealthRecord.objects.filter(pet=active_pet).values('record_type').annotate(total=Count('id')) if active_pet else []
    record_labels = [r['record_type'].replace('_', ' ').title() for r in record_counts]
    record_data = [r['total'] for r in record_counts]

    context = {
        'active_pet': active_pet,
        'pets': pets,
        'weight_dates_json': json.dumps(weight_dates),
        'weight_values_json': json.dumps(weight_values),
        'vac_stats_json': json.dumps([completed_count, upcoming_count, missed_count]),
        'record_labels_json': json.dumps(record_labels),
        'record_data_json': json.dumps(record_data),
    }
    return render(request, 'analytics/analytics.html', context)


# ==========================================
# 9. PET CARE, NUTRITION & HYGIENE GUIDANCE
# ==========================================

@login_required
def guidance_list_view(request):
    active_pet, pets = get_active_pet(request, user=request.user)
    articles = GuidanceArticle.objects.all()

    species_filter = request.GET.get('species')
    category_filter = request.GET.get('category')
    search_query = request.GET.get('q')

    if species_filter and species_filter != 'All':
        articles = articles.filter(Q(species=species_filter) | Q(species='All'))

    if category_filter:
        articles = articles.filter(category=category_filter)

    if search_query:
        articles = articles.filter(Q(title__icontains=search_query) | Q(summary__icontains=search_query) | Q(content__icontains=search_query))

    # Personalized Suggestions based on active pet
    personalized_articles = []
    if active_pet:
        personalized_articles = GuidanceArticle.objects.filter(
            Q(species=active_pet.species) | Q(species='All'),
            Q(life_stage=active_pet.life_stage()) | Q(life_stage='all')
        )[:3]

    context = {
        'articles': articles,
        'personalized_articles': personalized_articles,
        'active_pet': active_pet,
        'pets': pets,
        'species_filter': species_filter,
        'category_filter': category_filter,
    }
    return render(request, 'guidance/guidance_list.html', context)


@login_required
def guidance_detail_view(request, article_id):
    article = get_object_or_404(GuidanceArticle, id=article_id)
    return render(request, 'guidance/guidance_detail.html', {'article': article})


# ==========================================
# 10. EMERGENCY FIRST-AID & VET LOCATOR
# ==========================================

FIRST_AID_GUIDES = [
    {
        'id': 'choking',
        'title': 'Choking & Airway Obstruction',
        'icon': 'fa-mask-ventilator',
        'steps': [
            'Stay calm and secure the animal gently.',
            'Open the mouth carefully and inspect for visible foreign objects (balls, sticks, bones).',
            'If object is visible, use fingers or blunt tweezers to remove it carefully.',
            'For dogs, perform Heimlich maneuver: place hands around waist behind ribs, press upward firmly.',
            'If unconscious, clear mouth and perform chest compressions.'
        ]
    },
    {
        'id': 'poisoning',
        'title': 'Poisoning & Toxic Substance Ingestion',
        'icon': 'fa-skull-crossbones',
        'steps': [
            'Do NOT induce vomiting unless specifically instructed by a veterinarian!',
            'Identify the packaging, plant, chemical, or substance ingested.',
            'Keep animal calm and restrict movement to slow toxic absorption.',
            'Call the nearest emergency veterinary clinic or animal poison helpline immediately.'
        ]
    },
    {
        'id': 'heatstroke',
        'title': 'Heatstroke & Severe Overheating',
        'icon': 'fa-temperature-arrow-up',
        'steps': [
            'Move the animal into a shaded, air-conditioned environment immediately.',
            'Apply cool (NOT ice cold) water to the belly, paws, and neck using towels.',
            'Offer small sips of fresh cool water (do not force drinking).',
            'Transport to emergency vet while running vehicle air conditioning.'
        ]
    },
    {
        'id': 'bleeding',
        'title': 'Severe Wounds & Arterial Bleeding',
        'icon': 'fa-droplet',
        'steps': [
            'Place a sterile gauze pad or clean towel directly over the wound.',
            'Apply firm, continuous pressure for at least 5-10 minutes without lifting to check.',
            'If blood soaks through, place another towel directly over it.',
            'Elevate the injured limb if possible and rush to emergency vet.'
        ]
    }
]


@login_required
def emergency_view(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST' and 'add_contact' in request.POST:
        c_name = request.POST.get('contact_name', '').strip()
        c_phone = request.POST.get('contact_phone', '').strip()
        c_clinic = request.POST.get('contact_clinic', '').strip()

        contacts = profile.emergency_contacts or []
        contacts.append({'name': c_name, 'phone': c_phone, 'clinic': c_clinic})
        profile.emergency_contacts = contacts
        profile.save()
        messages.success(request, f"Added emergency contact '{c_name}'.")
        return redirect('emergency')

    context = {
        'first_aid_guides': FIRST_AID_GUIDES,
        'emergency_contacts': profile.emergency_contacts or [],
    }
    return render(request, 'emergency/emergency.html', context)


# ==========================================
# 11. INTEGRATED AI DISEASE DETECTION VIEW
# ==========================================

def disease_prediction(request):
    """
    INTEGRATED VIEW: Preserves the existing AI multimodal model (`predict_multimodal`)
    and connects outputs into pet digital health records if logged in.
    """
    image_context = None
    symptoms = ""
    result = None

    user_pets = Pet.objects.filter(user=request.user) if request.user.is_authenticated else []
    active_pet, _ = get_active_pet(request, request.user) if request.user.is_authenticated else (None, [])

    if request.method == 'POST':
        # Handle saving an existing prediction result to a pet's health record
        if 'save_to_pet' in request.POST and request.user.is_authenticated:
            pet_id = request.POST.get('pet_id')
            pred_disease = request.POST.get('pred_disease')
            pred_confidence = request.POST.get('pred_confidence')
            pred_recommendation = request.POST.get('pred_recommendation')

            pet = get_object_or_404(Pet, id=pet_id, user=request.user)
            
            HealthRecord.objects.create(
                pet=pet,
                record_type='ai_diagnosis',
                title=f"AI Diagnosis: {pred_disease}",
                description=f"Predicted Condition: {pred_disease}\nConfidence Score: {pred_confidence}%\n\nClinical Guidance:\n{pred_recommendation}",
                record_date=timezone.now().date(),
                ai_prediction_data={
                    'disease': pred_disease,
                    'confidence': pred_confidence,
                    'recommendation': pred_recommendation
                }
            )
            messages.success(request, f"Clinical Disease Prediction saved directly to {pet.name}'s digital health records!")
            return redirect('health_record_list')

        # Standard AI Prediction Form Submit
        image = request.FILES.get('image')
        symptoms = request.POST.get('symptoms', '')
        
        image_path = None
        if image:
            fs = FileSystemStorage()
            filename = fs.save(image.name, image)
            image_url = fs.url(filename)
            image_context = {'url': image_url}
            image_path = fs.path(filename)
            
        result = predict_multimodal(image_path=image_path, symptoms_text=symptoms)

    context = {
        "image": image_context,
        "symptoms": symptoms,
        "result": result,
        "user_pets": user_pets,
        "active_pet": active_pet,
    }    
    return render(request, 'disease_prediction.html', context)
