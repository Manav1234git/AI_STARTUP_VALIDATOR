from django.contrib import admin
from django.urls import path,include

urlpatterns = [
    path('admin/', admin.site.urls),

    path('', include('core.urls')),
    path('validate/', include('validator.urls')),
    path('analysis/',include('analysis.urls')),
    path('api/',include('api.urls')),
    path('dashboard/',include('dashboard.urls')),
    path('reports/',include('reports.urls')),
    path('users/',include('users.urls')),
]
