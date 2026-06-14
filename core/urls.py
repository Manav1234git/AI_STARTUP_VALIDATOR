# core/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),      # index page
    path('about/', views.about, name='about'),#about page
    path('demo/', views.demo, name='demo'),  #demo page

]