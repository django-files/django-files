from django.urls import path

from . import views


app_name = 'home'

urlpatterns = [
    path('', views.home_view, name='index'),
    path('files/', views.files_view, name='files'),
    path('settings/', views.settings_view, name='settings'),
    path('upload/', views.upload_view, name='upload'),
    path('ajax/delete/file/<int:pk>/', views.delete_file_ajax, name='delete-file'),
    path('ajax/delete/hook/<int:pk>/', views.delete_hook_ajax, name='delete-hook'),
    path('gen/sharex/', views.gen_sharex, name='gen-sharex'),
]
