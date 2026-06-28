import base64
import json
import logging
from typing import Union
from urllib.parse import urlparse

import duo_universal
from decouple import config
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import HttpResponseRedirect, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from home.templatetags.home_tags import is_mobile
from home.util.auth import _client_ip, _infer_device_name, create_api_token, hash_token
from home.util.requests import CustomSchemeRedirect
from oauth import passkeys
from oauth.forms import LoginForm
from oauth.models import (
    ApiToken,
    CustomUser,
    DiscordWebhooks,
    PasskeyCredential,
    UserInvites,
    superuser_exists,
)
from oauth.providers.discord import DiscordOauth
from oauth.providers.github import GithubOauth
from oauth.providers.google import GoogleOauth
from oauth.providers.helpers import (
    get_login_redirect_url,
    get_next_url,
    get_or_create_user,
)
from settings.models import SiteSettings
from ua_parser import parse
from webauthn.helpers import bytes_to_base64url

log = logging.getLogger("app")

TEMPLATE_OAUTH_USERNAME = "oauth_username.html"
SETTINGS_USER_URL = "settings:user"
MODEL_BACKEND = "django.contrib.auth.backends.ModelBackend"
PASSKEYS_NOT_ENABLED = "Passkeys are not enabled."
CONTENT_TYPE_JSON = "application/json"
INVITE_INVALID = "Invite is invalid or expired."
USERNAME_NOT_AVAILABLE = "The chosen username is not available."
USERNAME_REQUIRED = "Username is required."
PASSKEY_REG_FAILED = "Passkey registration failed."
PASSKEY_ALREADY_REGISTERED = "This passkey is already registered."
SETUP_COMPLETE = "Setup has already been completed."

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
        user: Union[AbstractBaseUser, CustomUser] = authenticate(
            request, username=form.cleaned_data["username"], password=form.cleaned_data["password"]
        )
        if not user or not site_settings.get_local_auth():
            return HttpResponse(status=401)

        if response := pre_login(request, user, site_settings):
            return response
        login(request, user)
        post_login(request)
        messages.info(request, f"Successfully logged in as {user.username}.")
        return HttpResponse()

    if request.user.is_authenticated:
        next_url = get_next_url(request)
        log.debug("request.user.is_authenticated: %s", next_url)
        return HttpResponseRedirect(next_url)

    # First run: with no admin yet there is nothing to log in as, so send the
    # visitor to the setup wizard to create the initial superuser.
    if not superuser_exists():
        log.debug("oauth_show: no superuser, redirecting to first-run setup")
        return HttpResponseRedirect(reverse("settings:welcome"))

    if "next" in request.GET:
        log.debug("setting login_next_url to: %s", request.GET.get("next"))
        request.session["login_next_url"] = request.GET.get("next")
    # Persist ?state=iOSApp from a native client opening the login page in a web
    # auth session so AJAX ceremonies (passkey) can later return a native-scheme
    # redirect with a token. Cleared after consumption in those views.
    if request.GET.get("state"):
        request.session["native_auth_state"] = request.GET.get("state")
    # if request.META.get("HTTP_USER_AGENT", "").startswith("DjangoFiles iOS"):
    if is_mobile(request, "ios"):
        # If a native app is redirect to login in the app web view,
        # we need to tell the app the client is no longer authenticated
        log.debug("CustomSchemeRedirect: djangofiles://logout")
        return CustomSchemeRedirect("djangofiles://logout")
    return render(request, "login.html", {"local": site_settings.get_local_auth()})


def _safe_redirect_target(request, candidate):
    """Return candidate if it points at this host, else the home page."""
    if candidate and url_has_allowed_host_and_scheme(
        candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return candidate
    return reverse("home:index")


def _username_taken(username, user):
    return CustomUser.objects.filter(username=username).exclude(pk=user.pk).exists()


@login_required
@require_http_methods(["GET", "POST"])
def oauth_username(request):
    """
    View  /oauth/username/
    Interstitial shown after first OAuth signup so the user can personalize the
    auto-generated login handle (and display name). Decoupled from display name:
    leaving things as-is keeps the generated username. Safe to revisit later.
    """
    default_next = _safe_redirect_target(request, request.session.get("login_redirect_url"))
    if request.method == "GET":
        return render(
            request,
            TEMPLATE_OAUTH_USERNAME,
            {"next": default_next, "username": request.user.username, "first_name": request.user.first_name},
        )

    next_url = _safe_redirect_target(request, request.POST.get("next") or default_next)
    request.session.pop("login_redirect_url", None)
    if request.POST.get("skip"):
        return redirect(next_url)

    username = (request.POST.get("username") or "").strip()
    display_name = (request.POST.get("first_name") or "").strip()
    error = None
    if not username:
        error = USERNAME_REQUIRED
    elif len(username) > 150:
        error = "Username is too long."
    elif _username_taken(username, request.user):
        error = "That username is already taken."
    if error:
        return render(
            request,
            TEMPLATE_OAUTH_USERNAME,
            {"next": next_url, "username": username, "first_name": display_name, "error": error},
        )

    try:
        request.user.username = username
        request.user.first_name = display_name
        request.user.save(update_fields=["username", "first_name"])
    except IntegrityError:
        return render(
            request,
            TEMPLATE_OAUTH_USERNAME,
            {
                "next": next_url,
                "username": username,
                "first_name": display_name,
                "error": "That username is already taken.",
            },
        )
    messages.info(request, "Username saved.")
    return redirect(next_url)


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


def _maybe_native_redirect(url):
    if url.startswith("djangofiles://"):
        return CustomSchemeRedirect(url)
    return HttpResponseRedirect(url)


def _apply_invite(request, user, invite):
    if not (invite and invite.is_valid() and not user.last_login):
        return
    if invite.super_user:
        user.is_staff = True
        user.is_superuser = True
    if invite.storage_quota is not None:
        user.storage_quota = invite.storage_quota
    user.save()
    invite.use_invite(user.id)
    request.session["login_redirect_url"] = reverse(SETTINGS_USER_URL)
    log.info("oauth_callback: invite used by user: %s", user)


def oauth_callback(request, oauth_provider: str = ""):
    """
    View  /oauth/callback/
    """
    try:
        site_settings = SiteSettings.objects.settings()
        code = request.GET.get("code")
        log.debug("code: %s", code)
        log.debug("oauth_callback: login_next_url: %s", request.session.get("login_next_url"))
        if not code:
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
        log.debug("oauth.id: %s - %s", oauth.id, oauth.username)
        oauth.process_login(site_settings)
        if request.session.get("webhook") and provider == "discord":
            del request.session["webhook"]
            webhook = oauth.add_webhook(request)
            messages.info(request, f"Webhook successfully added: {webhook.id}")
            url = get_login_redirect_url(request, native_auth=native_auth)
            return _maybe_native_redirect(url)

        invite_code = request.session.pop("oauth_invite", None)
        invite = UserInvites.objects.get_invite(invite_code) if invite_code else None
        log.debug("oauth_callback: invite: %s", invite)

        user = get_or_create_user(
            request,
            oauth.id,
            oauth.username,
            provider,
            first_name=oauth.first_name,
            allow_invite_create=bool(invite and invite.is_valid()),
        )
        log.debug("user: %s", user)
        if not user:
            message = "User Not Found or Already Taken."
            messages.error(request, message)
            url = get_login_redirect_url(request, native_auth=native_auth, native_client_error=message)
            return _maybe_native_redirect(url)

        _apply_invite(request, user, invite)

        oauth.update_profile(user)
        if response := pre_login(request, user, site_settings):
            return response
        login(request, user, backend=MODEL_BACKEND)
        post_login(request)
        messages.info(request, f"Successfully logged in via oauth. {user.username} {user.get_name()}.")
        log.debug("OAuth Login Success: %s", user)
        # New web signups land on an interstitial to personalize their generated
        # username; the originally intended destination stays in login_redirect_url.
        if not native_auth and request.session.pop("oauth_new_user", False):
            return HttpResponseRedirect(reverse("oauth:username"))
        request.session.pop("oauth_new_user", None)
        token = create_api_token(user, request) if native_auth else ""
        url = get_login_redirect_url(
            request,
            native_auth=native_auth,
            token=token,
            session_key=request.session.session_key,
        )
        log.debug("url: %s", url)
        return _maybe_native_redirect(url)

    except Exception:
        logging.exception("Exception during login")
        return HttpResponseRedirect(get_login_redirect_url(request))


def pre_login(request, user: Union[AbstractBaseUser, CustomUser], site_settings):
    log.debug("pre_login: user.username: %s", user.username)
    if site_settings.duo_auth:
        request.session["username"] = user.username
        url = duo_redirect(request, user.username)
        log.debug("pre_login: url: %s", url)
        return JsonResponse({"redirect": url})


def post_login(request):
    log.debug("post_login: %s", request.user.username)
    try:
        agent = request.META.get("HTTP_USER_AGENT", "")
        log.debug("agent: %s", agent)
        ua = parse(agent or "")
        log.debug("ua: %s", ua)
        state = request.GET.get("state")
        mobile = is_mobile(request)
        if state or mobile:
            client = mobile.get("name", state) if mobile else state
            log.debug("client: %s", client)
            request.session["user_agent"] = f"{client} Application"
        else:
            agent_list = []
            if ua.os:
                agent_list.append(ua.os.family)
            if ua.user_agent:
                if ua.user_agent.family:
                    agent_list.append(ua.user_agent.family)
                if ua.user_agent.major:
                    agent_list.append(ua.user_agent.major)
            if agent_list:
                request.session["user_agent"] = " ".join(agent_list)
        if not request.session["user_agent"]:
            request.session["user_agent"] = "Unknown User Agent"
        user_agent = request.session["user_agent"]
        if user_agent.isprintable():
            log.info("User Agent: %s", user_agent)
        else:
            log.info("User Agent: %s", base64.b64encode(user_agent.encode("UTF-8")))

        if state or is_mobile(request):
            log.debug("Set Mobile Session Age: %s", settings.SESSION_MOBILE_AGE)
            request.session.set_expiry(settings.SESSION_MOBILE_AGE)
    except Exception as error:
        log.warning("Error Parsing User Agent: %s", error)


# ---------------------------------------------------------------------------
# Passkeys (WebAuthn)
# ---------------------------------------------------------------------------


def _passkeys_enabled(site_settings):
    return bool(site_settings.passkey_auth and site_settings.site_url)


def _setup_origin(request, client_origin):
    """Resolve the WebAuthn origin for first-run setup.

    A reverse proxy (e.g. nginx mapping a custom host port to :80) hides the real
    port from ``request.get_host()``, so trust the browser-supplied origin -- but
    only when its hostname matches the request host, to avoid an attacker pinning
    the RP to a foreign domain.
    """
    server_origin = f"{request.scheme}://{request.get_host()}"
    request_host = request.get_host().split(":")[0]
    if client_origin:
        try:
            parsed = urlparse(client_origin)
        except ValueError:
            parsed = None
        if parsed and parsed.hostname == request_host and parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    return server_origin


@login_required
@require_http_methods(["POST"])
def passkey_register_begin(request):
    """
    View  /oauth/passkey/register/begin
    """
    site_settings = SiteSettings.objects.settings()
    if not _passkeys_enabled(site_settings):
        return JsonResponse({"error": PASSKEYS_NOT_ENABLED}, status=400)
    try:
        options = passkeys.begin_registration(
            request.session, request.user, site_settings, request.user.passkeys.all()
        )
    except passkeys.PasskeyConfigError as error:
        return JsonResponse({"error": str(error)}, status=400)
    return HttpResponse(options, content_type=CONTENT_TYPE_JSON)


@login_required
@require_http_methods(["POST"])
def passkey_register_complete(request):
    """
    View  /oauth/passkey/register/complete
    """
    site_settings = SiteSettings.objects.settings()
    if not _passkeys_enabled(site_settings):
        return JsonResponse({"error": PASSKEYS_NOT_ENABLED}, status=400)
    body = json.loads(request.body.decode() or "{}")
    name = (body.pop("name", "") or "").strip()
    try:
        verification = passkeys.finish_registration(request.session, site_settings, body)
    except Exception:
        log.exception("passkey_register_complete: verification failed")
        return JsonResponse({"error": PASSKEY_REG_FAILED}, status=400)
    credential_id = bytes_to_base64url(verification.credential_id)
    if PasskeyCredential.objects.filter(credential_id=credential_id).exists():
        return JsonResponse({"error": PASSKEY_ALREADY_REGISTERED}, status=400)
    ua = request.META.get("HTTP_USER_AGENT", "")[:500]
    passkey = PasskeyCredential.objects.create(
        user=request.user,
        credential_id=credential_id,
        public_key=bytes_to_base64url(verification.credential_public_key),
        sign_count=verification.sign_count,
        name=name or _infer_device_name(ua),
        transports=body.get("response", {}).get("transports") or [],
        created_ip=_client_ip(request),
        user_agent=ua,
    )
    log.info("passkey registered for user=%s id=%s", request.user.username, passkey.id)
    return JsonResponse({"id": passkey.id, "name": passkey.name}, status=200)


@login_required
@require_http_methods(["GET"])
def passkey_list(request):
    """
    View  /oauth/passkey/list
    """
    data = [
        {
            "id": p.id,
            "name": p.name,
            "created_at": p.created_at.isoformat(),
            "last_used_at": p.last_used_at.isoformat() if p.last_used_at else None,
            "created_ip": p.created_ip,
            "user_agent": p.user_agent,
        }
        for p in request.user.passkeys.all()
    ]
    return JsonResponse({"passkeys": data})


@login_required
@require_http_methods(["POST", "DELETE"])
def passkey_delete(request, pk):
    """
    View  /oauth/passkey/<pk>/delete
    """
    deleted, _ = PasskeyCredential.objects.filter(user=request.user, pk=pk).delete()
    if not deleted:
        return JsonResponse({"error": "Passkey not found."}, status=404)
    log.info("passkey deleted for user=%s id=%s", request.user.username, pk)
    return JsonResponse({"deleted": True})


@csrf_exempt
@require_http_methods(["POST"])
def passkey_auth_begin(request):
    """
    View  /oauth/passkey/auth/begin
    """
    site_settings = SiteSettings.objects.settings()
    if not _passkeys_enabled(site_settings):
        return JsonResponse({"error": PASSKEYS_NOT_ENABLED}, status=400)
    try:
        options = passkeys.begin_authentication(request.session, site_settings)
    except passkeys.PasskeyConfigError as error:
        return JsonResponse({"error": str(error)}, status=400)
    return HttpResponse(options, content_type=CONTENT_TYPE_JSON)


@csrf_exempt
@require_http_methods(["POST"])
def passkey_auth_complete(request):
    """
    View  /oauth/passkey/auth/complete
    """
    site_settings = SiteSettings.objects.settings()
    if not _passkeys_enabled(site_settings):
        return JsonResponse({"error": PASSKEYS_NOT_ENABLED}, status=400)
    body = json.loads(request.body.decode() or "{}")
    credential = PasskeyCredential.objects.filter(credential_id=body.get("id")).select_related("user").first()
    if not credential:
        log.warning("passkey_auth_complete: unknown credential id")
        return JsonResponse({"error": "Unknown passkey."}, status=401)
    user = credential.user
    # login() does not enforce is_active (only authenticate() does); enforce it
    # here so a disabled account cannot authenticate via passkey.
    if not user.is_active:
        log.warning("passkey_auth_complete: rejected inactive user=%s", user.username)
        return JsonResponse({"error": "This account is disabled."}, status=403)
    try:
        verification = passkeys.finish_authentication(request.session, site_settings, body, credential)
    except Exception:
        log.exception("passkey_auth_complete: verification failed")
        return JsonResponse({"error": "Passkey authentication failed."}, status=401)
    credential.sign_count = verification.new_sign_count
    credential.last_used_at = timezone.now()
    credential.save(update_fields=["sign_count", "last_used_at"])
    request.session["login_redirect_url"] = get_next_url(request)
    if response := pre_login(request, user, site_settings):
        return response
    login(request, user, backend=MODEL_BACKEND)
    post_login(request)
    messages.info(request, f"Successfully logged in as {user.username}.")
    # Native client (e.g. iOS web auth session): hand off via the djangofiles://
    # scheme with a freshly minted token so the app can store it directly,
    # mirroring oauth_callback's native-auth handoff.
    native_state = request.session.pop("native_auth_state", None)
    if native_state == "iOSApp":
        token = create_api_token(user, request)
        return JsonResponse(
            {
                "redirect": get_login_redirect_url(
                    request,
                    native_auth=True,
                    token=token,
                    session_key=request.session.session_key or "",
                )
            }
        )
    return JsonResponse({"redirect": get_login_redirect_url(request)})


def _valid_invite_or_none(invite_code):
    invite = UserInvites.objects.get_invite(invite_code)
    if not invite or not invite.is_valid():
        return None
    return invite


@csrf_exempt
@require_http_methods(["POST"])
def passkey_invite_begin(request, invite):
    """
    View  /oauth/passkey/invite/<invite>/begin
    Start passkey registration for a new account created via an invite.
    """
    site_settings = SiteSettings.objects.settings()
    if not _passkeys_enabled(site_settings):
        return JsonResponse({"error": PASSKEYS_NOT_ENABLED}, status=400)
    if request.user.is_authenticated:
        return JsonResponse({"error": "Already authenticated."}, status=400)
    if not _valid_invite_or_none(invite):
        return JsonResponse({"error": INVITE_INVALID}, status=400)
    body = json.loads(request.body.decode() or "{}")
    username = (body.get("username") or "").strip()
    if not username:
        return JsonResponse({"error": USERNAME_REQUIRED}, status=400)
    if CustomUser.objects.filter(username=username).exists():
        return JsonResponse({"error": USERNAME_NOT_AVAILABLE}, status=400)
    try:
        options = passkeys.begin_invite_registration(request.session, username, site_settings)
    except passkeys.PasskeyConfigError as error:
        return JsonResponse({"error": str(error)}, status=400)
    request.session["passkey_invite_username"] = username
    request.session["passkey_invite_code"] = invite
    return HttpResponse(options, content_type=CONTENT_TYPE_JSON)


def _passkey_invite_complete_preflight(request, invite, site_settings):
    """Validate the invite/session state. Returns (error_response, invite_obj, username)."""
    if not _passkeys_enabled(site_settings):
        return JsonResponse({"error": PASSKEYS_NOT_ENABLED}, status=400), None, None
    if request.user.is_authenticated:
        return JsonResponse({"error": "Already authenticated."}, status=400), None, None
    invite_obj = _valid_invite_or_none(invite)
    if not invite_obj:
        return JsonResponse({"error": INVITE_INVALID}, status=400), None, None
    username = request.session.get("passkey_invite_username")
    if not username or request.session.get("passkey_invite_code") != invite:
        return JsonResponse({"error": "Registration session expired. Please try again."}, status=400), None, None
    if CustomUser.objects.filter(username=username).exists():
        return JsonResponse({"error": USERNAME_NOT_AVAILABLE}, status=400), None, None
    return None, invite_obj, username


@csrf_exempt
@require_http_methods(["POST"])
def passkey_invite_complete(request, invite):
    """
    View  /oauth/passkey/invite/<invite>/complete
    Verify the attestation, then create the account, consume the invite, and log in.
    """
    site_settings = SiteSettings.objects.settings()
    error, invite_obj, username = _passkey_invite_complete_preflight(request, invite, site_settings)
    if error:
        return error

    body = json.loads(request.body.decode() or "{}")
    name = (body.pop("name", "") or "").strip()
    try:
        verification = passkeys.finish_invite_registration(request.session, site_settings, body)
    except Exception:
        log.exception("passkey_invite_complete: verification failed")
        return JsonResponse({"error": PASSKEY_REG_FAILED}, status=400)
    credential_id = bytes_to_base64url(verification.credential_id)
    if PasskeyCredential.objects.filter(credential_id=credential_id).exists():
        return JsonResponse({"error": PASSKEY_ALREADY_REGISTERED}, status=400)

    ua = request.META.get("HTTP_USER_AGENT", "")[:500]
    try:
        with transaction.atomic():
            # Lock the invite row so concurrent completes cannot both consume a
            # single-use (or super_user) invite and mint multiple accounts.
            # select_for_update is a no-op on SQLite but enforced on Postgres/MySQL.
            invite_locked = UserInvites.objects.select_for_update().filter(pk=invite_obj.pk).first()
            if not invite_locked or not invite_locked.is_valid():
                return JsonResponse({"error": INVITE_INVALID}, status=400)
            if CustomUser.objects.filter(username=username).exists():
                return JsonResponse({"error": USERNAME_NOT_AVAILABLE}, status=400)

            create_user = (
                CustomUser.objects.create_superuser if invite_locked.super_user else CustomUser.objects.create_user
            )
            user = create_user(username=username, password=None, storage_quota=invite_locked.storage_quota)
            invite_locked.use_invite(user.id)
            PasskeyCredential.objects.create(
                user=user,
                credential_id=credential_id,
                public_key=bytes_to_base64url(verification.credential_public_key),
                sign_count=verification.sign_count,
                name=name or _infer_device_name(ua),
                transports=body.get("response", {}).get("transports") or [],
                created_ip=_client_ip(request),
                user_agent=ua,
            )
    except IntegrityError:
        # Username/credential uniqueness lost a race; the whole txn rolled back.
        log.exception("passkey_invite_complete: integrity error creating account")
        return JsonResponse({"error": USERNAME_NOT_AVAILABLE}, status=400)

    request.session.pop("passkey_invite_username", None)
    request.session.pop("passkey_invite_code", None)
    login(request, user, backend=MODEL_BACKEND)
    post_login(request)
    request.session["login_redirect_url"] = reverse(SETTINGS_USER_URL)
    messages.info(request, f"Welcome to Django Files {user.get_name()}.")
    log.info("passkey invite signup: created user=%s (super=%s)", user.username, invite_obj.super_user)
    return JsonResponse({"redirect": reverse(SETTINGS_USER_URL)})


@csrf_exempt
@require_http_methods(["POST"])
def passkey_setup_begin(request):
    """
    View  /oauth/passkey/setup/begin
    First-run setup: start passkey registration for the initial admin account.
    """
    site_settings = SiteSettings.objects.settings()
    # site_url is not configured yet on first run, so gate on passkey_auth alone
    # and derive the RP from the origin the admin is visiting (incl. custom port).
    if not site_settings.passkey_auth:
        return JsonResponse({"error": PASSKEYS_NOT_ENABLED}, status=400)
    if superuser_exists():
        return JsonResponse({"error": SETUP_COMPLETE}, status=400)
    body = json.loads(request.body.decode() or "{}")
    username = (body.get("username") or "").strip()
    if not username:
        return JsonResponse({"error": USERNAME_REQUIRED}, status=400)
    if CustomUser.objects.filter(username=username).exists():
        return JsonResponse({"error": USERNAME_NOT_AVAILABLE}, status=400)
    origin = _setup_origin(request, (body.get("origin") or "").strip())
    try:
        options = passkeys.begin_setup_registration(request.session, username, origin, site_settings.site_title)
    except passkeys.PasskeyConfigError as error:
        return JsonResponse({"error": str(error)}, status=400)
    request.session["passkey_setup_username"] = username
    request.session["passkey_setup_timezone"] = (body.get("timezone") or "").strip()
    request.session["passkey_setup_origin"] = origin
    return HttpResponse(options, content_type=CONTENT_TYPE_JSON)


def _passkey_setup_preflight(request, site_settings):
    """Validate first-run passkey setup state. Returns (error_response, username)."""
    if not site_settings.passkey_auth:
        return JsonResponse({"error": PASSKEYS_NOT_ENABLED}, status=400), None
    if superuser_exists():
        return JsonResponse({"error": SETUP_COMPLETE}, status=400), None
    username = request.session.get("passkey_setup_username")
    if not username:
        return JsonResponse({"error": "Registration session expired. Please try again."}, status=400), None
    if CustomUser.objects.filter(username=username).exists():
        return JsonResponse({"error": USERNAME_NOT_AVAILABLE}, status=400), None
    return None, username


@csrf_exempt
@require_http_methods(["POST"])
def passkey_setup_complete(request):
    """
    View  /oauth/passkey/setup/complete
    First-run setup: verify the attestation, create the initial superuser, log in.
    """
    site_settings = SiteSettings.objects.settings()
    error, username = _passkey_setup_preflight(request, site_settings)
    if error:
        return error

    body = json.loads(request.body.decode() or "{}")
    name = (body.pop("name", "") or "").strip()
    # Persist site_url to the origin the passkey was bound to (incl. custom port)
    # so future passkey logins derive the same RP ID.
    origin = request.session.pop("passkey_setup_origin", "") or f"{request.scheme}://{request.get_host()}"
    try:
        verification = passkeys.finish_setup_registration(request.session, origin, site_settings.site_title, body)
    except Exception:
        log.exception("passkey_setup_complete: verification failed")
        return JsonResponse({"error": PASSKEY_REG_FAILED}, status=400)
    credential_id = bytes_to_base64url(verification.credential_id)
    if PasskeyCredential.objects.filter(credential_id=credential_id).exists():
        return JsonResponse({"error": PASSKEY_ALREADY_REGISTERED}, status=400)

    ua = request.META.get("HTTP_USER_AGENT", "")[:500]
    tz = request.session.pop("passkey_setup_timezone", "")
    try:
        with transaction.atomic():
            # Re-check inside the transaction so two concurrent setups cannot both
            # pass the gate and create separate admin accounts.
            if superuser_exists():
                return JsonResponse({"error": SETUP_COMPLETE}, status=409)
            if CustomUser.objects.filter(username=username).exists():
                return JsonResponse({"error": USERNAME_NOT_AVAILABLE}, status=400)
            user = CustomUser.objects.create_superuser(username=username, password=None)
            if tz:
                user.timezone = tz
                user.save(update_fields=["timezone"])
            PasskeyCredential.objects.create(
                user=user,
                credential_id=credential_id,
                public_key=bytes_to_base64url(verification.credential_public_key),
                sign_count=verification.sign_count,
                name=name or _infer_device_name(ua),
                transports=body.get("response", {}).get("transports") or [],
                created_ip=_client_ip(request),
                user_agent=ua,
            )
            site_settings.show_setup = False
            if tz:
                site_settings.timezone = tz
            # Bind site_url to the origin the passkey was registered against.
            site_settings.site_url = origin
            site_settings.save()
    except IntegrityError:
        log.exception("passkey_setup_complete: integrity error creating admin")
        return JsonResponse({"error": USERNAME_NOT_AVAILABLE}, status=400)

    request.session.pop("passkey_setup_username", None)
    login(request, user, backend=MODEL_BACKEND)
    post_login(request)
    request.session["login_redirect_url"] = reverse("settings:site")
    messages.info(request, f"Welcome to Django Files {user.get_name()}.")
    log.info("first-run passkey setup: created initial superuser=%s", user.username)
    return JsonResponse({"redirect": reverse("settings:site")})


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
        duo_client.exchange_authorization_code_for_2fa_result(code, username)

        if request.session.pop("pending_account_delete", False):
            user = CustomUser.objects.get(username=username)
            log.warning("duo_callback: account deletion confirmed via Duo for user %s (id=%s)", user.username, user.pk)
            logout(request)
            user.delete()
            messages.info(request, "Your account has been permanently deleted.")
            return HttpResponseRedirect(reverse("oauth:login"))

        user = CustomUser.objects.get(username=username)
        login(request, user, backend=MODEL_BACKEND)

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

    Optional POST params for native-app logouts:
    - ``token`` (plaintext): identifies the ApiToken to clean up.
    - ``delete_token`` (any truthy value): when present alongside ``token``,
      the row is hard-deleted; otherwise it is soft-disabled (is_active=False).
    """
    user = request.user
    if user.is_authenticated:
        plaintext = request.POST.get("token", "").strip()
        if plaintext:
            qs = ApiToken.objects.filter(user=user, token_hash=hash_token(plaintext))
            if request.POST.get("delete_token"):
                qs.delete()
                log.info("oauth_logout: deleted api token for user=%s", user.username)
            else:
                qs.filter(is_active=True).update(is_active=False)
                log.info("oauth_logout: revoked api token for user=%s", user.username)

    next_url = get_next_url(request)
    log.debug("oauth_logout: next_url: %s", next_url)
    logout(request)
    request.session["login_next_url"] = next_url
    log.debug("oauth_logout: login_next_url: %s", request.session.get("login_next_url"))
    if is_mobile(request):
        return CustomSchemeRedirect("djangofiles://logout")
    messages.info(request, "Successfully logged out.")
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
