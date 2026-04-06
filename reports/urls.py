from django.urls import path
from .views import reports
#urls
urlpatterns = [
    path('reports/', reports),
]