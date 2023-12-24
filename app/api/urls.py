from django.urls import path, re_path

from api import views

app_name = 'api'

urlpatterns = [
    path('', views.api_view, name='status'),
    re_path(r'^upload/?$', views.upload_view, name='upload'),
    re_path(r'^shorten/?$', views.shorten_view, name='shorten'),
    path('invites/', views.invites_view, name='invites'),
    path('recent/', views.recent_view, name='recent'),
    path('remote/', views.remote_view, name='remote'),
    path('stats/', views.stats_view, name='stats'),
    path('delete/<path:idname>', views.delete_view, name='delete'),
    path('edit/<path:idname>', views.edit_view, name='edit'),
]
