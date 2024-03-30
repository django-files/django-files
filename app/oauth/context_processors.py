from oauth.util import process_avatar


def current_user_avatar_url_processor(request):
    return {"current_user_avatar_url": process_avatar(request.user)}
