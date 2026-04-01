from django.urls import path
from .views import validate_idea

urlpatterns = [
    path('', validate_idea, name='validate'),
]