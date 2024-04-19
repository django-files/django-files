from django.urls import path, re_path

from api import views

app_name = 'api'

urlpatterns = [
    path('', views.api_view, name='status'),
    re_path(r'^upload/?$', views.upload_view, name='upload'),
    re_path(r'^shorten/?$', views.shorten_view, name='shorten'),
    path('invites/', views.invites_view, name='invites'),
    path('recent/', views.recent_view, name='recent'),
    path('pages/<int:page>/', views.pages_view, name='pages'),
    path('pages/<int:page>/<int:amount>/', views.pages_view, name='pages-amount'),
    path('remote/', views.remote_view, name='remote'),
    path('stats/', views.stats_view, name='stats'),
    path('file/<path:idname>', views.file_view, name='file'),
    path('delete/<path:idname>', views.file_view, name='delete'),
]
