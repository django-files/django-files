import logging
import secrets
import uuid
from typing import Optional

from decouple import Csv, config
from django.db import IntegrityError, transaction
from django.urls import reverse
from oauth.models import CustomUser
from settings.models import SiteSettings

log = logging.getLogger("app")

# AbstractUser.username is max_length=150; keep headroom for a uniqueness suffix.
_USERNAME_MAX = 150
_USERNAME_BASE_MAX = 140


def _candidate_usernames(base: str):
    """Yield login-handle candidates for a new account, most-preferred first.

    The provider handle is offered as-is, then numerically suffixed, with a
    random hex fallback. The DB unique constraint is the real arbiter — these
    are only candidates fed to an atomic create-with-retry.
    """
    base = (base or "").strip()[:_USERNAME_BASE_MAX] or "user"
    yield base
    for _ in range(50):
        yield f"{base}{secrets.randbelow(9000) + 1000}"
    yield f"{base[:_USERNAME_BASE_MAX]}-{uuid.uuid4().hex[:8]}"


def create_oauth_user(base_username: str, first_name: str = "") -> Optional[CustomUser]:
    """Create a new OAuth user with a guaranteed-unique username.

    Never adopts an existing account; the provider handle becomes the login
    handle only when free, otherwise a unique variant is generated. Concurrent
    signups racing for the same handle are resolved by the unique constraint
    (``IntegrityError`` -> next candidate).
    """
    for candidate in _candidate_usernames(base_username):
        try:
            with transaction.atomic():
                return CustomUser.objects.create(username=candidate[:_USERNAME_MAX], first_name=first_name or "")
        except IntegrityError:
            continue
    log.error("create_oauth_user: exhausted username candidates for base=%s", base_username)
    return None


def get_or_create_user(
    request, _id, username, provider, first_name="", allow_invite_create=False
) -> Optional[CustomUser]:
    log.debug("_id: %s %s", _id, type(_id))
    log.debug("username %s", username)

    # get user by Oauth Provider ID (the stable identity link)
    if provider == "google":
        # google id is too long to be an in or big int field so we handle it separately
        # passing google ids to other filters throws a SQL error
        user = CustomUser.objects.filter(google__id=_id)
    else:
        user = CustomUser.objects.filter(discord__id=_id) or CustomUser.objects.filter(github__id=_id)
    if user:
        # if oauth user already exists and is trying to be claimed
        if request.session.get("oauth_claim_username"):
            del request.session["oauth_claim_username"]
            log.info("OAuth ID Already Claimed!")
            return None
        # use found by oauth provider id
        log.debug("got user by ID")
        log.debug(user)
        return user[0]

    # authenticated user explicitly linking a provider to their own account
    # (set by redirect_login when request.user.is_authenticated). This is the
    # ONLY path that attaches an OAuth identity to a pre-existing account.
    if request.session.get("oauth_claim_username"):
        claim_username = request.session["oauth_claim_username"]
        del request.session["oauth_claim_username"]
        log.info("OAuth Used oauth_claim_username: %s", claim_username)
        if user := CustomUser.objects.filter(username=claim_username):
            return user[0]
        # claim target vanished; do NOT fall through to account creation/adoption
        log.warning("oauth_claim_username target not found: %s", claim_username)
        return None

    # No account adoption by username match (that was an account-takeover vector:
    # anyone could register a matching provider handle to claim a pre-created,
    # never-logged-in local account). New signups always get a fresh account.
    if SiteSettings.objects.settings().oauth_reg or is_super_id(_id) or allow_invite_create:
        new_user = create_oauth_user(username, first_name)
        if new_user:
            # Signal oauth_callback to route the user through the username
            # interstitial so they can personalize their generated handle.
            request.session["oauth_new_user"] = True
            log.info("created OAuth user handle=%s (from=%s) for id=%s", new_user.username, username, _id)
        return new_user

    log.debug("User does not exist locally and oauth_reg is off: %s", _id)
    return None


def get_next_url(request) -> str:
    """
    Determine 'next' parameter
    """
    site_settings = SiteSettings.objects.settings()
    log.debug("get_next_url")
    if request.user.is_authenticated and site_settings.show_setup:
        return reverse("settings:welcome")
    if "next" in request.GET:
        log.debug("next in request.GET: %s", str(request.GET["next"]))
        return str(request.GET["next"])
    if "next" in request.POST:
        log.debug("next in request.POST: %s", str(request.POST["next"]))
        return str(request.POST["next"])
    if "login_next_url" in request.session:
        log.debug("login_next_url in request.session: %s", request.session["login_next_url"])
        url = request.session["login_next_url"]
        del request.session["login_next_url"]
        request.session.modified = True
        return url
    if "HTTP_REFERER" in request.META:
        log.debug("HTTP_REFERER in request.META: %s", request.META["HTTP_REFERER"])
        return request.META["HTTP_REFERER"]
    log.info("----- get_next_url FAILED -----")
    return reverse("home:index")


def get_login_redirect_url(
    request, native_auth: bool = False, token: str = "", session_key: str = "", native_client_error: str = ""
) -> str:
    """
    Determine 'login_redirect_url' parameter
    """
    log.debug("get_login_redirect_url: login_redirect_url: %s", request.session.get("login_redirect_url"))
    if native_auth:
        return f"djangofiles://oauth/callback?token={token}&session_key={session_key}&error={native_client_error}"
    if "login_redirect_url" in request.session:
        url = request.session["login_redirect_url"]
        del request.session["login_redirect_url"]
        request.session.modified = True
        return url
    return reverse("home:index")


def is_super_id(_id):
    log.debug("_id: %s", _id)
    log.debug("SUPER_USERS: %s", config("SUPER_USERS", "", Csv()))
    if _id in config("SUPER_USERS", "", Csv()):
        return True
    return False
