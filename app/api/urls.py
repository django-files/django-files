from api import views
from django.urls import path, re_path


app_name = "api"

urlpatterns = [
    path("", views.api_view, name="status"),
    re_path(r"^upload/?$", views.upload_view, name="upload"),
    re_path(r"^shorten/?$", views.shorten_view, name="shorten"),
    path("invites/", views.invites_view, name="invites"),
    path("recent/", views.recent_view, name="recent"),
    path("files/<int:page>/", views.files_view, name="files"),
    path("files/<int:page>/<int:count>/", views.files_view, name="files-amount"),
    path("album/", views.album_view, name="album"),
    path("albums/", views.albums_view, name="albums"),
    path("albums/<int:page>/", views.albums_view, name="albums"),
    path("albums/<int:page>/<int:count>/", views.albums_view, name="albums-amount"),
    path("random/album/<str:user_album>/", views.random_album, name="random-album"),
    path("random/album/<str:user_album>/<path:idname>/", views.random_album, name="random-user-album"),
    path("remote/", views.remote_view, name="remote"),
    path("stats/", views.stats_view, name="stats"),
    path("file/<path:idname>", views.file_view, name="file"),
    path("delete/<path:idname>", views.file_view, name="delete"),
    path("token/", views.token_view, name="token"),
]
