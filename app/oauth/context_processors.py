from oauth.util import get_user_avatar_url


def current_user_avatar_url_processor(request):
    if request.user.is_anonymous:
        return {"current_user_avatar_url": "/static/images/default_avatar.png"}
    return {"current_user_avatar_url": get_user_avatar_url(request.user)}
