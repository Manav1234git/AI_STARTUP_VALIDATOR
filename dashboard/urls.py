from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_home, name='dashboard'),

    path('ask_gemini/',views.ai_idea_view,name='ask_gemini'),
    
    # path('ask_groq/', views.ai_idea_view, name='ask_groq'),

    path('export-pdf/', views.export_pdf, name='export_pdf'),

    path('location-intel/', views.location_intelligence, name='location_intel'),  # ✅ NEW

]
    # path('api/check-auth/', views.check_auth),
    # path('api/diagnose/', views.diagnose),
    # path('/signup/',views.singup,name='signup')
