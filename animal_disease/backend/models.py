from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('pet_owner', 'Pet Owner'),
        ('veterinarian', 'Veterinarian / Admin'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='pet_owner')
    phone = models.CharField(max_length=20, blank=True, null=True)
    emergency_contacts = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"


class Pet(models.Model):
    SPECIES_CHOICES = (
        ('Dog', 'Dog'),
        ('Cat', 'Cat'),
        ('Bird', 'Bird'),
        ('Cattle', 'Cattle / Cow / Buffalo'),
        ('Horse', 'Horse'),
        ('Rabbit', 'Rabbit'),
        ('Goat', 'Goat / Sheep'),
        ('Other', 'Other Animal'),
    )
    GENDER_CHOICES = (
        ('Male', 'Male'),
        ('Female', 'Female'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pets')
    name = models.CharField(max_length=100)
    species = models.CharField(max_length=50, choices=SPECIES_CHOICES, default='Dog')
    breed = models.CharField(max_length=100, blank=True, default='Unknown / Crossbreed')
    age_years = models.PositiveIntegerField(default=0)
    age_months = models.PositiveIntegerField(default=0)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default='Male')
    weight_kg = models.FloatField(default=0.0)
    photo = models.ImageField(upload_to='pets/', blank=True, null=True)
    microchip_id = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def age_display(self):
        parts = []
        if self.age_years > 0:
            parts.append(f"{self.age_years} yr{'s' if self.age_years > 1 else ''}")
        if self.age_months > 0 or self.age_years == 0:
            parts.append(f"{self.age_months} mo{'s' if self.age_months > 1 else ''}")
        return " ".join(parts) if parts else "0 mos"

    def life_stage(self):
        if self.species in ['Dog', 'Cat']:
            if self.age_years < 1:
                return 'puppy_kitten'
            elif self.age_years >= 7:
                return 'senior'
            return 'adult'
        else:
            if self.age_years < 1:
                return 'puppy_kitten'
            elif self.age_years >= 8:
                return 'senior'
            return 'adult'

    def __str__(self):
        return f"{self.name} ({self.species} - {self.user.username})"


class SymptomCheckResult(models.Model):
    URGENCY_CHOICES = (
        ('mild', 'Mild - Home Monitoring'),
        ('moderate', 'Moderate - Schedule Vet Visit'),
        ('emergency', 'EMERGENCY - Consult Vet Immediately'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='symptom_checks')
    pet = models.ForeignKey(Pet, on_delete=models.SET_NULL, null=True, blank=True, related_name='symptom_checks')
    symptoms = models.JSONField(default=list)
    possible_conditions = models.JSONField(default=list)
    urgency_level = models.CharField(max_length=20, choices=URGENCY_CHOICES, default='mild')
    recommendations = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Symptom Check ({self.urgency_level}) - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class ChatMessage(models.Model):
    SENDER_CHOICES = (
        ('user', 'User'),
        ('bot', 'Virtual Assistant'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_messages')
    pet = models.ForeignKey(Pet, on_delete=models.SET_NULL, null=True, blank=True, related_name='chat_messages')
    sender = models.CharField(max_length=10, choices=SENDER_CHOICES)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.sender}: {self.message[:30]}"


class VaccinationReminder(models.Model):
    STATUS_CHOICES = (
        ('upcoming', 'Upcoming'),
        ('completed', 'Completed'),
        ('missed', 'Missed'),
    )
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='reminders')
    vaccine_name = models.CharField(max_length=150)
    due_date = models.DateField()
    reminder_date = models.DateField()
    recurring_months = models.IntegerField(default=0, help_text="0 for one-time, or cycle in months e.g. 3, 6, 12")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='upcoming')
    notes = models.TextField(blank=True, null=True)
    completed_at = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_due_soon(self):
        if self.status != 'upcoming':
            return False
        today = timezone.now().date()
        return today >= self.reminder_date and today <= self.due_date

    def is_overdue(self):
        if self.status != 'upcoming':
            return False
        return timezone.now().date() > self.due_date

    def __str__(self):
        return f"{self.pet.name} - {self.vaccine_name} (Due: {self.due_date})"


class HealthRecord(models.Model):
    RECORD_TYPES = (
        ('vet_visit', 'Vet Visit Note'),
        ('prescription', 'Prescription / Medication'),
        ('lab_report', 'Lab / Test Report'),
        ('ai_diagnosis', 'Clinical Disease Prediction'),
        ('symptom_check', 'Symptom Evaluation'),
        ('vaccination', 'Vaccination Record'),
        ('weight_entry', 'Weight Log'),
    )
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='health_records')
    record_type = models.CharField(max_length=30, choices=RECORD_TYPES, default='vet_visit')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    attachment = models.FileField(upload_to='health_records/', blank=True, null=True)
    record_date = models.DateField(default=timezone.now)
    ai_prediction_data = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-record_date', '-created_at']

    def __str__(self):
        return f"{self.pet.name} - {self.title} ({self.get_record_type_display()})"


class WeightLog(models.Model):
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='weight_logs')
    weight_kg = models.FloatField()
    recorded_date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['recorded_date']

    def __str__(self):
        return f"{self.pet.name}: {self.weight_kg}kg on {self.recorded_date}"


class GuidanceArticle(models.Model):
    LIFE_STAGE_CHOICES = (
        ('puppy_kitten', 'Puppy / Kitten / Young'),
        ('adult', 'Adult'),
        ('senior', 'Senior'),
        ('all', 'All Life Stages'),
    )
    CATEGORY_CHOICES = (
        ('nutrition', 'Diet & Nutrition'),
        ('grooming', 'Hygiene & Grooming'),
        ('vaccination', 'Vaccination & Care'),
        ('first_aid', 'Emergency First-Aid'),
        ('general', 'General Care'),
    )
    title = models.CharField(max_length=200)
    species = models.CharField(max_length=50, default='All')
    life_stage = models.CharField(max_length=20, choices=LIFE_STAGE_CHOICES, default='all')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')
    summary = models.TextField()
    content = models.TextField()
    icon = models.CharField(max_length=50, default='fa-book-medical')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.species} - {self.category})"
