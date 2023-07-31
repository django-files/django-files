from django.urls import path

from . import views


app_name = 'oauth'

urlpatterns = [
    path('', views.oauth_show, name='login'),
    path('start/', views.oauth_start, name='start'),
    path('logout/', views.oauth_logout, name='logout'),
    path('callback/', views.oauth_callback, name='callback'),
    path('webhook/', views.oauth_webhook, name='webhook'),
]
