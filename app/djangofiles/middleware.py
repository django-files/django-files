import time


class SessionRefreshMiddleware:
    """Refresh the session (resetting its Redis TTL) only after half its lifetime has elapsed.

    Replaces SESSION_SAVE_EVERY_REQUEST=True to provide sliding-expiry sessions
    without a Redis write on every request.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.session.session_key and not request.session.modified:
            max_age = request.session.get_expiry_age()
            last_refresh = request.session.get("_session_refresh", 0)
            if time.time() - last_refresh > max_age / 2:
                request.session["_session_refresh"] = time.time()
        return response
