from django.urls import path

from api import views

app_name = 'api'

urlpatterns = [
    path('', views.api_view, name='status'),
    path('recent/', views.recent_view, name='recent'),
    path('remote/', views.remote_view, name='remote'),
    path('stats/', views.stats_view, name='stats'),
]
