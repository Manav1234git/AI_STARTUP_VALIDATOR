from django.urls import path
from analysis.views import analysis

urlpatterns = [
    path("analysis/", analysis)
]