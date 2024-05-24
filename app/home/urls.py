from django.urls import path, re_path

from api.views import shorten_view, upload_view
from home import views

app_name = 'home'

urlpatterns = [
    path('', views.home_view, name='index'),
    path('files/', views.files_view, name='files'),
    path('gallery/', views.files_view, name='gallery'),
    path('uppy/', views.uppy_view, name='uppy'),
    path('paste/', views.paste_view, name='paste'),
    path('shorts/', views.shorts_view, name='shorts'),
    path('stats/', views.stats_view, name='stats'),
    path('public/', views.pub_uppy_view, name='public-uppy'),
    path('i/', views.invite_view, name='invite-base'),
    path('i/<str:invite>', views.invite_view, name='invite'),
    re_path(r'^upload/?$', upload_view, name='upload'),
    re_path(r'^shorten/?$', shorten_view, name='shorten'),
    path('s/<str:short>', views.shorten_short_view, name='short'),
    path('ajax/update/stats/', views.update_stats_ajax, name='update-stats'),
    path('ajax/delete/short/<int:pk>/', views.delete_short_ajax, name='delete-short'),
    path('ajax/delete/file/<int:pk>/', views.delete_file_ajax, name='delete-file'),
    path('ajax/set_password/file/<int:pk>/', views.set_password_file_ajax, name='set-password-file'),
    path('ajax/set_expr/file/<int:pk>/', views.set_expr_file_ajax, name='set-expr-file'),
    path('ajax/toggle_private/file/<int:pk>/', views.toggle_private_file_ajax, name='toggle-private-file'),
    path('ajax/delete/hook/<int:pk>/', views.delete_hook_ajax, name='delete-hook'),
    path('ajax/check_password/file/<int:pk>/', views.check_password_file_ajax, name='check-password-file'),
    path('u/<path:filename>', views.url_route_view, name='url-route'),
    path('p/<path:filename>', views.proxy_route_view, name='proxy-route'),
    path('raw/<path:filename>', views.raw_redirect_view, name='url-raw-redirect'),
    path('r/<path:filename>', views.url_route_view, name='url-raw'),
]
