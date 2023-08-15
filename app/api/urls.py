from django.urls import path

from api import views


app_name = 'api'

urlpatterns = [
    path('', views.api_view, name='index'),
    path('remote/', views.remote_view, name='remote'),
]
