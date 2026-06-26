"""WebAuthn / passkey helpers.

Thin wrapper around ``py_webauthn`` that derives the Relying Party (RP)
configuration from ``SiteSettings.site_url`` and keeps the ceremony challenge
in the session. Views in :mod:`oauth.views` stay small by delegating here.
"""

import logging
from urllib.parse import urlparse

from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

log = logging.getLogger("app")

REG_CHALLENGE_KEY = "passkey_reg_challenge"
AUTH_CHALLENGE_KEY = "passkey_auth_challenge"


class PasskeyConfigError(Exception):
    """Raised when the site is not configured for WebAuthn (no usable site_url)."""


def get_rp(site_settings):
    """Return ``(rp_id, rp_name, expected_origin)`` derived from site_url.

    WebAuthn requires a stable RP ID (the registrable domain) and an exact
    origin. Both come from ``site_url``; without it passkeys cannot work.
    """
    site_url = site_settings.site_url
    if not site_url:
        raise PasskeyConfigError("site_url must be set to use passkeys.")
    parsed = urlparse(site_url)
    if not parsed.hostname:
        raise PasskeyConfigError(f"Could not derive a hostname from site_url: {site_url}")
    rp_id = parsed.hostname
    origin = f"{parsed.scheme}://{parsed.netloc}"
    rp_name = site_settings.site_title or "Django Files"
    return rp_id, rp_name, origin


def begin_registration(session, user, site_settings, existing_credentials):
    """Generate registration options and stash the challenge in the session."""
    rp_id, rp_name, _ = get_rp(site_settings)
    exclude = [
        PublicKeyCredentialDescriptor(id=base64url_to_bytes(cred.credential_id)) for cred in existing_credentials
    ]
    options = generate_registration_options(
        rp_id=rp_id,
        rp_name=rp_name,
        user_id=str(user.pk).encode(),
        user_name=user.username,
        user_display_name=user.get_name(),
        exclude_credentials=exclude,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )
    session[REG_CHALLENGE_KEY] = bytes_to_base64url(options.challenge)
    return options_to_json(options)


def finish_registration(session, site_settings, body):
    """Verify an attestation response. Returns a ``VerifiedRegistration``."""
    rp_id, _, origin = get_rp(site_settings)
    challenge_b64 = session.pop(REG_CHALLENGE_KEY, None)
    if not challenge_b64:
        raise PasskeyConfigError("No registration challenge in session; restart the ceremony.")
    return verify_registration_response(
        credential=body,
        expected_challenge=base64url_to_bytes(challenge_b64),
        expected_origin=origin,
        expected_rp_id=rp_id,
        require_user_verification=False,
    )


def begin_authentication(session, site_settings):
    """Generate authentication options for a usernameless (discoverable) login."""
    rp_id, _, _ = get_rp(site_settings)
    options = generate_authentication_options(
        rp_id=rp_id,
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    session[AUTH_CHALLENGE_KEY] = bytes_to_base64url(options.challenge)
    return options_to_json(options)


def finish_authentication(session, site_settings, body, credential):
    """Verify an assertion against a stored credential. Returns ``VerifiedAuthentication``."""
    rp_id, _, origin = get_rp(site_settings)
    challenge_b64 = session.pop(AUTH_CHALLENGE_KEY, None)
    if not challenge_b64:
        raise PasskeyConfigError("No authentication challenge in session; restart the ceremony.")
    return verify_authentication_response(
        credential=body,
        expected_challenge=base64url_to_bytes(challenge_b64),
        expected_rp_id=rp_id,
        expected_origin=origin,
        credential_public_key=base64url_to_bytes(credential.public_key),
        credential_current_sign_count=credential.sign_count,
        require_user_verification=False,
    )
