from api import views
from django.urls import path, re_path
from oauth.views import oauth_show


app_name = "api"

urlpatterns = [
    path("", views.api_view, name="status"),
    re_path(r"^version/?$", views.version_view, name="version"),
    re_path(r"^upload/?$", views.upload_view, name="upload"),
    re_path(r"^shorten/?$", views.shorten_view, name="shorten"),
    path("invites/", views.invites_view, name="invites"),
    path("recent/", views.recent_view, name="recent"),
    path("shorts/", views.shorts_view, name="shorts"),
    path("files/edit/", views.files_edit_view, name="files-edit"),
    path("files/delete/", views.files_edit_view, name="files-delete"),
    path("files/<int:page>/", views.files_view, name="files"),
    path("files/<int:page>/<int:count>/", views.files_view, name="files-amount"),
    path("album/", views.album_view, name="album"),
    path("album/<int:id>/", views.album_view, name="album-id"),
    path("albums/", views.albums_view, name="albums"),
    path("albums/<int:page>/", views.albums_view, name="albums"),
    path("albums/<int:page>/<int:count>/", views.albums_view, name="albums-amount"),
    path("random/album/<str:user_album>/", views.random_album, name="random-album"),
    path("random/album/<str:user_album>/<path:idname>/", views.random_album, name="random-user-album"),
    path("remote/", views.remote_view, name="remote"),
    path("stats/", views.stats_view, name="stats"),
    path("stats/current/", views.stats_current_view, name="stats-current"),
    path("file/<path:idname>", views.file_view, name="file"),
    path("delete/<path:idname>", views.file_view, name="delete"),
    path("token/", views.token_view, name="token"),
    path("auth/methods/", views.auth_methods, name="auth-methods"),
    path("auth/token/", views.local_auth_for_native_client, name="auth-token"),
    path("session/<path:sessionid>", views.session_view, name="session"),
    path("oauth/", oauth_show, name="oauth-show"),
]
