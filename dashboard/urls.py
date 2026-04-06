from django.urls import path
from .views import dashboard
#urls
urlpatterns = [
    path('dashboard/', dashboard),
]