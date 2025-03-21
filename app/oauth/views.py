import logging

import duo_universal
from decouple import config
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, JsonResponse
from django.shortcuts import HttpResponseRedirect, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from home.util.requests import CustomSchemeRedirect
from oauth.forms import LoginForm
from oauth.models import CustomUser, DiscordWebhooks
from oauth.providers.discord import DiscordOauth
from oauth.providers.github import GithubOauth
from oauth.providers.google import GoogleOauth
from oauth.providers.helpers import (
    get_login_redirect_url,
    get_next_url,
    get_or_create_user,
)
from settings.models import SiteSettings


log = logging.getLogger("app")

provider_map = {
    "github": GithubOauth,
    "discord": DiscordOauth,
    "google": GoogleOauth,
}


def route_callback(provider: str, code: str):
    return provider_map[provider](code)


@csrf_exempt
def oauth_show(request):
    """
    View  /oauth/
    """
    site_settings = SiteSettings.objects.settings()
    if request.method == "POST":
        request.session["login_redirect_url"] = get_next_url(request)
        form = LoginForm(request.POST)
        if not form.is_valid():
            log.debug(form.errors)
            return HttpResponse(status=400)
        user = authenticate(request, username=form.cleaned_data["username"], password=form.cleaned_data["password"])
        if not user or not site_settings.get_local_auth():
            return HttpResponse(status=401)

        if response := pre_login(request, user, site_settings):
            return response
        login(request, user)
        post_login(request, user)
        messages.info(request, f"Successfully logged in as {user.username}.")
        return HttpResponse()

    if request.user.is_authenticated:
        next_url = get_next_url(request)
        return HttpResponseRedirect(next_url)

    if "next" in request.GET:
        log.debug("setting login_next_url to: %s", request.GET.get("next"))
        request.session["login_next_url"] = request.GET.get("next")
    if request.META.get("HTTP_USER_AGENT", "").startswith("DjangoFiles"):
        # If a native app is redirect to login in the app web view,
        # we need to tell the app the client is no longer authenticated
        return CustomSchemeRedirect("djangofiles://logout")
    return render(request, "login.html", {"local": site_settings.get_local_auth()})


def oauth_discord(request):
    """
    View  /oauth/discord/
    """
    settings = SiteSettings.objects.settings()
    request.session["login_redirect_url"] = get_next_url(request)
    return DiscordOauth.redirect_login(request, settings)


def oauth_github(request):
    """
    View  /oauth/github/
    """
    settings = SiteSettings.objects.settings()
    request.session["login_redirect_url"] = get_next_url(request)
    return GithubOauth.redirect_login(request, settings)


def oauth_google(request):
    """
    View  /oauth/google/
    """
    settings = SiteSettings.objects.settings()
    request.session["login_redirect_url"] = get_next_url(request)
    return GoogleOauth.redirect_login(request, settings)


def oauth_callback(request, oauth_provider: str = ""):
    """
    View  /oauth/callback/
    """
    try:
        site_settings = SiteSettings.objects.settings()
        code = request.GET.get("code")
        log.debug("code: %s", code)
        if not code:
            messages.warning(request, "User aborted or no code in response...")
            return HttpResponseRedirect(get_login_redirect_url(request))

        log.debug("oauth_callback: login_next_url: %s", request.session.get("login_next_url"))
        if not (code := request.GET.get("code")):
            messages.warning(request, "User aborted or no code in response...")
            return HttpResponseRedirect(get_login_redirect_url(request))

        native_auth = request.GET.get("state") == "iOSApp"
        provider = oauth_provider if oauth_provider else request.session.get("oauth_provider")
        log.debug("oauth_callback: provider: %s", provider)
        log.debug("Native App Auth: %s", native_auth)

        try:
            oauth = route_callback(provider, code)
        except KeyError:
            messages.error(request, "Unknown Provider: %s" % provider)
            return HttpResponseRedirect(get_login_redirect_url(request))
        log.debug("oauth.id %s", oauth.id)
        log.debug("oauth.username %s", oauth.username)
        log.debug("oauth.first_name %s", oauth.first_name)
        oauth.process_login(site_settings)
        if request.session.get("webhook") and provider == "discord":
            del request.session["webhook"]
            webhook = oauth.add_webhook(request)
            messages.info(request, f"Webhook successfully added: {webhook.id}")
            return CustomSchemeRedirect(get_login_redirect_url(request, native_auth=native_auth))

        user = get_or_create_user(request, oauth.id, oauth.username, provider, first_name=oauth.first_name)
        log.debug("user: %s", user)
        if not user:
            message = "User Not Found or Already Taken."
            messages.error(request, message)
            return CustomSchemeRedirect(
                get_login_redirect_url(request, native_auth=native_auth, native_client_error=message)
            )

        oauth.update_profile(user)
        if response := pre_login(request, user, SiteSettings.objects.settings()):
            return response
        login(request, user)
        post_login(request, user)
        messages.info(request, f"Successfully logged in via oauth. {user.username} {user.first_name}.")
        return CustomSchemeRedirect(
            get_login_redirect_url(
                request, native_auth=native_auth, token=user.authorization, session_key=request.session.session_key
            )
        )

    except Exception as error:
        log.exception(error)
        messages.error(request, f"Exception during login: {error}")
        return HttpResponseRedirect(get_login_redirect_url(request))


def pre_login(request, user, site_settings):
    log.debug("username: %s", user.username)
    if site_settings.duo_auth:
        request.session["username"] = user.username
        url = duo_redirect(request, user.username)
        log.debug("url: %s", url)
        return JsonResponse({"redirect": url})


def post_login(request, user):
    # TODO: Explain why this method is empty
    pass


def duo_callback(request):
    """
    View  /oauth/duo/
    """
    log.debug("%s - duo_callback", request.method)
    try:
        duo_client = get_duo_client(request)
        state = request.GET.get("state")
        log.debug("state: %s", state)
        code = request.GET.get("duo_code")
        log.debug("code: %s", code)
        if state != request.session["state"]:
            messages.warning(request, "State Check Failed. Try Again!")
            return HttpResponseRedirect(get_login_redirect_url(request))
        username = request.session["username"]
        log.debug("username: %s", username)
        decoded_token = duo_client.exchange_authorization_code_for_2fa_result(code, username)
        log.debug("decoded_token: %s", decoded_token)
        user = CustomUser.objects.get(username=username)
        login(request, user)

        # if 'profile' in request.session:
        #     log.debug('profile in session, updating oauth profile')
        #     update_profile(user, json.loads(request.session['profile']))
        #     del request.session['profile']

        log.debug("duo_callback: login_next_url: %s", request.session.get("login_next_url"))
        messages.success(request, f"Congrats, You Authenticated Twice, {username}!")
        return HttpResponseRedirect(get_login_redirect_url(request))

    except Exception as error:
        log.exception(error)
        return HttpResponse(status=401)


def duo_redirect(request, username):
    log.debug("duo_redirect: username: %s", username)
    duo_client = get_duo_client(request)
    try:
        duo_client.health_check()
    except duo_universal.DuoException as error:
        log.exception(error)
        raise ValueError("Duo Health Check Failed: %s", error) from error

    state = duo_client.generate_state()
    log.debug("state: %s", state)
    request.session["state"] = state

    prompt_uri = duo_client.create_auth_url(username, state)
    log.debug("prompt_uri: %s", prompt_uri)
    return prompt_uri


def get_duo_client(request):
    log.debug("request.build_absolute_uri: %s", request.build_absolute_uri())
    site_url = SiteSettings.objects.get(pk=1).site_url
    log.debug("site_url: %s", site_url)
    redirect_uri = site_url.rstrip("/") + reverse("oauth:duo")
    log.debug("redirect_uri: %s", redirect_uri)
    return duo_universal.Client(
        config("DUO_CLIENT_ID"),
        config("DUO_CLIENT_SECRET"),
        config("DUO_API_HOST"),
        redirect_uri,
    )


@csrf_exempt
@require_http_methods(["POST"])
def oauth_logout(request):
    """
    View  /oauth/logout/
    """
    next_url = get_next_url(request)
    log.debug("oauth_logout: next_url: %s", next_url)
    logout(request)
    request.session["login_next_url"] = next_url
    messages.info(request, "Successfully logged out.")
    log.debug("oauth_logout: login_next_url: %s", request.session.get("login_next_url"))
    if request.META.get("HTTP_USER_AGENT", "").startswith("DjangoFiles"):
        return CustomSchemeRedirect("djangofiles://logout")
    return redirect(next_url)


def oauth_webhook(request):
    """
    View  /oauth/webhook/
    """
    site_settings = SiteSettings.objects.settings()
    return DiscordOauth.redirect_webhook(request, site_settings)


def add_webhook(request, profile):
    """
    Add webhook
    """
    log.debug("add_webhook")
    webhook = DiscordWebhooks(
        hook_id=profile["webhook"]["id"],
        guild_id=profile["webhook"]["guild_id"],
        channel_id=profile["webhook"]["channel_id"],
        url=profile["webhook"]["url"],
        owner=request.user,
    )
    webhook.save()
    return webhook
