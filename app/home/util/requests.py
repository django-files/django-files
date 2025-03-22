from django.http import HttpResponseRedirect


class CustomSchemeRedirect(HttpResponseRedirect):
    # This allows us to redirect to ios deeplinks
    allowed_schemes = ["djangofiles"]
