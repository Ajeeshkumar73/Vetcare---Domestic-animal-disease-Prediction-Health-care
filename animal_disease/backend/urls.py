from django.urls import path
from . import views

urlpatterns = [
    # Landing Page
    path('', views.landing_view, name='landing'),

    # Existing Clinical Disease Prediction Tool
    path('disease-prediction/', views.disease_prediction, name='disease_prediction'),

    # Auth Routes
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('password-reset/', views.reset_password_view, name='reset_password'),

    # Dashboard
    path('dashboard/', views.dashboard_view, name='dashboard'),

    # Pet Profiles
    path('pets/', views.pet_list_view, name='pet_list'),
    path('pets/add/', views.pet_create_view, name='pet_create'),
    path('pets/<int:pet_id>/edit/', views.pet_edit_view, name='pet_edit'),
    path('pets/<int:pet_id>/delete/', views.pet_delete_view, name='pet_delete'),
    path('pets/<int:pet_id>/switch/', views.switch_active_pet_view, name='switch_active_pet'),

    # Symptom Checker (Rule-based)
    path('symptom-checker/', views.symptom_checker_view, name='symptom_checker'),

    # Virtual Pet Care Chatbot
    path('chatbot/', views.chat_view, name='chat'),
    path('api/chat/', views.chat_api_view, name='chat_api'),

    # Vaccination & Health Reminders
    path('reminders/', views.reminder_list_view, name='reminder_list'),
    path('reminders/add/', views.reminder_create_view, name='reminder_create'),
    path('reminders/<int:reminder_id>/toggle/', views.reminder_toggle_view, name='reminder_toggle'),
    path('reminders/<int:reminder_id>/delete/', views.reminder_delete_view, name='reminder_delete'),

    # Digital Health Records & PDF Export
    path('health-records/', views.health_record_list_view, name='health_record_list'),
    path('health-records/add/', views.health_record_create_view, name='health_record_create'),
    path('health-records/export-pdf/<int:pet_id>/', views.health_record_export_pdf_view, name='health_record_export_pdf'),

    # Health Analytics Dashboard
    path('analytics/', views.analytics_view, name='analytics'),

    # Pet Guidance & Nutrition Library
    path('guidance/', views.guidance_list_view, name='guidance_list'),
    path('guidance/<int:article_id>/', views.guidance_detail_view, name='guidance_detail'),

    # Emergency First-Aid & Vet Locator
    path('emergency/', views.emergency_view, name='emergency'),
]