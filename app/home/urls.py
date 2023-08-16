from django.urls import path, re_path

from home import views

app_name = 'home'

urlpatterns = [
    path('', views.home_view, name='index'),
    path('files/', views.files_view, name='files'),
    path('gallery/', views.gallery_view, name='gallery'),
    path('uppy/', views.uppy_view, name='uppy'),
    path('shorts/', views.shorts_view, name='shorts'),
    path('settings/', views.settings_view, name='settings'),
    path('stats/', views.stats_view, name='stats'),
    re_path(r'^upload/?$', views.upload_view, name='upload'),
    re_path(r'^api/upload/?$', views.upload_view, name='api-upload'),
    re_path(r'^shorten/?$', views.shorten_view, name='shorten'),
    re_path(r'^api/shorten/?$', views.shorten_view, name='api-shorten'),
    path('s/<str:short>', views.shorten_short_view, name='short'),
    path('ajax/update/stats/', views.update_stats_ajax, name='update-stats'),
    path('ajax/delete/file/<int:pk>/', views.delete_file_ajax, name='delete-file'),
    path('ajax/delete/hook/<int:pk>/', views.delete_hook_ajax, name='delete-hook'),
    path('gen/sharex/', views.gen_sharex, name='gen-sharex'),
    path('gen/sharex-url/', views.gen_sharex_url, name='gen-sharex-url'),
    path('gen/flameshot/', views.gen_flameshot, name='gen-flameshot'),
    path('u/<path:filename>', views.url_route_view, name='url-route'),
    path('r/<path:filename>', views.url_route_view, name='url-raw'),
]
