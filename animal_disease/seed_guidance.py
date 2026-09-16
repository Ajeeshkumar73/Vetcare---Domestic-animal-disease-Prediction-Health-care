import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'animal_disease.settings')
django.setup()

from backend.models import GuidanceArticle

articles = [
    {
        'title': 'Canine Nutrition 101: Balanced Diet Plans for Puppies and Adult Dogs',
        'species': 'Dog',
        'life_stage': 'all',
        'category': 'nutrition',
        'summary': 'A complete guide to essential proteins, fats, vitamins, and dangerous toxic foods for dogs.',
        'content': """Providing balanced nutrition is the cornerstone of lifelong canine health.

1. Protein Requirements: Active dogs need high-quality animal protein (chicken, lamb, salmon) to support muscle maintenance and immune strength.
2. Dangerous Toxic Foods: Never feed dogs chocolate, grapes, raisins, onions, garlic, macadamia nuts, or foods containing Xylitol sweetener.
3. Puppy vs. Senior Needs: Puppies require higher calories and calcium-to-phosphorus ratios for bone development, whereas senior dogs benefit from joint support supplements (glucosamine) and controlled calorie intake.""",
        'icon': 'fa-bowl-food'
    },
    {
        'title': 'Feline Grooming & Hairball Prevention Techniques',
        'species': 'Cat',
        'life_stage': 'all',
        'category': 'grooming',
        'summary': 'Daily brushing routines, claw trimming tips, and preventing hairball blockages in cats.',
        'content': """While cats groom themselves continuously, owner assistance is vital for coat health and preventing digestive obstruction.

1. Brushing Schedule: Long-haired breeds (Persian, Maine Coon) require daily brushing to prevent painful mats. Short-haired breeds benefit from weekly grooming.
2. Hairball Control: Incorporate dietary fiber or hairball remedies to assist smooth transit of ingested fur through the digestive system.
3. Ear & Eye Hygiene: Gently wipe eye corners with moist cotton pads. Inspect ears weekly for dark waxy buildup which may indicate ear mites.""",
        'icon': 'fa-soap'
    },
    {
        'title': 'Core Vaccination Schedule for Dogs and Cats',
        'species': 'All',
        'life_stage': 'puppy_kitten',
        'category': 'vaccination',
        'summary': 'Timeline for core vaccines (Rabies, Parvovirus, Distemper, Panleukopenia) and booster shots.',
        'content': """Immunization protects your pets against highly contagious and potentially fatal viral infections.

Core Vaccines for Puppies:
- 6 to 8 Weeks: DHPP (Distemper, Hepatitis, Parvovirus, Parainfluenza)
- 10 to 12 Weeks: DHPP Booster + Leptospirosis
- 14 to 16 Weeks: DHPP Booster + Rabies Vaccine

Core Vaccines for Kittens:
- 6 to 8 Weeks: FVRCP (Feline Viral Rhinotracheitis, Calicivirus, Panleukopenia)
- 10 to 12 Weeks: FVRCP Booster
- 14 to 16 Weeks: FVRCP Booster + Rabies Vaccine""",
        'icon': 'fa-syringe'
    },
    {
        'title': 'Cattle & Livestock Health Management & Foot Rot Prevention',
        'species': 'Cattle',
        'life_stage': 'adult',
        'category': 'general',
        'summary': 'Best practices for pasture hygiene, hoof trimming, and early detection of livestock infections.',
        'content': """Livestock health requires diligent environment management and timely medical intervention.

1. Foot Rot Prevention: Keep standing areas dry and well-drained. Perform routine hoof trimming and use zinc sulfate foot baths.
2. Deworming Protocol: Rotate antiparasitic classes annually to mitigate drug resistance.
3. Vaccination: Ensure annual vaccination against Clostridial diseases, Blackleg, and Bovine Respiratory Syncytial Virus (BRSV).""",
        'icon': 'fa-cow'
    }
]

for art_data in articles:
    obj, created = GuidanceArticle.objects.get_or_create(
        title=art_data['title'],
        defaults=art_data
    )
    if created:
        print(f"Created guidance article: {obj.title}")
    else:
        print(f"Article already exists: {obj.title}")
