from django.urls import path

from oauth import views


app_name = 'oauth'

urlpatterns = [
    path('', views.oauth_show, name='login'),
    path('discord/', views.oauth_discord, name='discord'),
    path('github/', views.oauth_github, name='github'),
    path('google/', views.oauth_google, name='google'),
    path('webhook/', views.oauth_webhook, name='webhook'),
    path('logout/', views.oauth_logout, name='logout'),
    path('callback/', views.oauth_callback, name='callback'),
    path('duo/', views.duo_callback, name='duo'),
]
