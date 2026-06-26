from django.urls import path
from oauth import views

app_name = "oauth"

urlpatterns = [
    path("", views.oauth_show, name="login"),
    path("discord/", views.oauth_discord, name="discord"),
    path("github/", views.oauth_github, name="github"),
    path("google/", views.oauth_google, name="google"),
    path("webhook/", views.oauth_webhook, name="webhook"),
    path("logout/", views.oauth_logout, name="logout"),
    path("callback/<str:oauth_provider>", views.oauth_callback, name="callback"),
    path("duo/", views.duo_callback, name="duo"),
    path("passkey/register/begin", views.passkey_register_begin, name="passkey-register-begin"),
    path("passkey/register/complete", views.passkey_register_complete, name="passkey-register-complete"),
    path("passkey/list", views.passkey_list, name="passkey-list"),
    path("passkey/<int:pk>/delete", views.passkey_delete, name="passkey-delete"),
    path("passkey/auth/begin", views.passkey_auth_begin, name="passkey-auth-begin"),
    path("passkey/auth/complete", views.passkey_auth_complete, name="passkey-auth-complete"),
]
