from django.urls import path
from settings import views

app_name = "settings"

urlpatterns = [
    path("user/", views.user_view, name="user"),
    path("site/", views.site_view, name="site"),
    path("welcome/", views.welcome_view, name="welcome"),
    path("sharex/", views.gen_sharex, name="sharex"),
    path("sharex-url/", views.gen_sharex_url, name="sharex-url"),
    path("flameshot/", views.gen_flameshot, name="flameshot"),
    path("user/qr.png", views.qr_view, name="qrcode"),
    path("user/signature", views.signature_view, name="signature"),
    path("user/password", views.password_view, name="password"),
    path("user/local-auth", views.local_auth_view, name="local-auth"),
    path("user/delete", views.delete_account_view, name="delete-account"),
]
