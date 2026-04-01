from django.urls import path
from .views import home
#urls
urlpatterns = [
    path('', home, name='home'),
]