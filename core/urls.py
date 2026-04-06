from django.urls import path
from .views import home,about
#urls
urlpatterns = [
    path('', home, name='home'),
    path('about/', about),
]