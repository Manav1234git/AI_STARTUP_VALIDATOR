from django.urls import path
from users.views import login, signup

urlpatterns = [
    path("login/", login),
    path('signup/' ,signup),
]