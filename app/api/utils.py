from typing import Any, Dict, List, Mapping

from django.db.models import QuerySet
from django.forms.models import model_to_dict
from home.models import Albums, Files, Stream
from home.util.tags import tag_names
from oauth.models import CustomUser
from settings.context_processors import site_settings_processor
from webpush.models import PushInformation


def _parse_ordering(spec: str, allowed: Mapping[str, str]) -> list:
    out = []
    for raw in spec.split(","):
        raw = raw.strip()
        if not raw:
            continue
        desc = raw.startswith("-")
        key = raw[1:] if desc else raw
        if key not in allowed:
            continue
        field = allowed[key]
        out.append(f"-{field}" if desc else field)
    return out


def apply_ordering(
    queryset: QuerySet,
    request,
    allowed: Mapping[str, str],
    default: str,
    tiebreaker: str = "-pk",
) -> QuerySet:
    """
    Order a queryset from ?ordering= (DRF's OrderingFilter convention).

    `allowed` maps public ordering keys to model field names (or annotation
    aliases). `ordering` accepts a comma-separated list; each key may be
    prefixed with `-` for descending (Django's order_by convention).
    Unknown keys are dropped; if nothing valid remains, `default` is used.
    A stable tiebreaker is always appended so pagination is deterministic.
    """
    ordering_param = (request.GET.get("ordering") or "").strip()
    fields = _parse_ordering(ordering_param, allowed) or _parse_ordering(default, allowed)
    if tiebreaker and tiebreaker not in fields and tiebreaker.lstrip("-") not in fields:
        fields.append(tiebreaker)
    return queryset.order_by(*fields)


def serialize_user(user: CustomUser) -> Dict[str, Any]:
    """
    Serialize a user instance into a dictionary with consistent exclusions and additions.

    Args:
        user: CustomUser instance to serialize

    Returns:
        Dict containing user data with password and authorization excluded, and avatar_url added
    """
    user_dict = model_to_dict(user, exclude=["password", "authorization"])
    user_dict["avatar_url"] = user.get_avatar_url()
    user_dict["storage_quota_human_read"] = user.get_storage_quota_human_read()
    providers = []
    for provider in ("discord", "github", "google"):
        if getattr(user, provider, None) is not None:
            providers.append(provider)
    user_dict["oauth_providers"] = providers
    return user_dict


def serialize_users(users: List[CustomUser]) -> List[Dict[str, Any]]:
    """
    Serialize a list of user instances into a list of dictionaries.

    Args:
        users: List of CustomUser instances to serialize

    Returns:
        List of dictionaries containing user data
    """
    return [serialize_user(user) for user in users]


def extract_files(q: Files.objects):
    site_settings = site_settings_processor(None)["site_settings"]
    files = []
    for file in q:
        data = model_to_dict(file, exclude=["file", "thumb", "albums"])
        data["user_name"] = file.user.get_name()
        data["user_username"] = file.user.username

        data["url"] = site_settings["site_url"] + file.preview_uri()
        data["thumb"] = site_settings["site_url"] + file.thumb_path
        data["raw"] = site_settings["site_url"] + file.raw_path
        data["date"] = file.date
        albums = list(file.albums.all())
        data["albums"] = [a.id for a in albums]
        data["albums_details"] = [{"id": a.id, "name": a.name} for a in albums]
        data["tags"] = tag_names(file)
        files.append(data)
    return files


def extract_albums(q: Albums.objects, user_id: int = None):
    # user_id=None preserves the legacy signal-path behavior (broadcast to the
    # owner-scoped group), where every recipient is implicitly the owner.
    site_settings = site_settings_processor(None)["site_settings"]
    albums = []
    for album in q:
        is_owner = user_id is None or album.user_id == user_id
        data = model_to_dict(album)
        data["date"] = album.date
        data["url"] = site_settings["site_url"] + "/files/?view=gallery&album=" + str(album.id)
        data["user_name"] = album.user.get_name()
        data["file_count"] = getattr(album, "file_count", 0)
        data["tags"] = tag_names(album)
        data["is_owner"] = is_owner
        if not is_owner:
            # Don't leak the raw password value to e.g. superusers browsing
            # someone else's albums.
            data["has_password"] = bool(data.pop("password", ""))
        albums.append(data)
    return albums


def _apply_owner_fields(data, stream, rtmp_host, rtmp_port):
    # Don't ship the raw playback_token in row payloads; the VLC URL is
    # fetched on demand via /api/stream/<name>/vlc-url/. Expose only the
    # enabled bit so the menu can render the right action.
    data["playback_enabled"] = bool(data.pop("playback_token", ""))
    if rtmp_host:
        authority = f"{rtmp_host}:{rtmp_port}" if rtmp_port and rtmp_port != 1935 else rtmp_host
        data["rtmp_url"] = f"rtmp://{authority}/live?stream_token={stream.stream_token}"


def _strip_owner_fields(data):
    # Non-owners (e.g. superusers browsing all streams) should not see the raw
    # password value either. The boolean state is enough for UI.
    data.pop("stream_token", None)
    data.pop("playback_token", None)
    data["has_password"] = bool(data.pop("password", ""))


def _resolve_subscriber_count(name: str, subscriber_counts):
    if subscriber_counts is not None:
        return subscriber_counts.get(name, 0)
    return PushInformation.objects.filter(group__name=name).count()


def extract_streams(
    q: Stream.objects,
    user_id: int = None,
    rtmp_host: str = None,
    rtmp_port: int = None,
    subscriber_counts: dict = None,
):
    site_settings = site_settings_processor(None)["site_settings"]
    streams = []
    for stream in q:
        is_owner = user_id is not None and stream.user_id == user_id
        data = model_to_dict(stream, exclude=["user"])
        data["user_name"] = stream.user.get_name()
        data["user_username"] = stream.user.username
        data["started_at"] = stream.started_at
        data["ended_at"] = stream.ended_at
        data["url"] = site_settings["site_url"] + f"/live/{stream.name}/"
        data["is_owner"] = is_owner
        data["tags"] = tag_names(stream)
        data["subscriber_count"] = _resolve_subscriber_count(stream.name, subscriber_counts)
        if is_owner:
            _apply_owner_fields(data, stream, rtmp_host, rtmp_port)
        else:
            _strip_owner_fields(data)
        streams.append(data)
    return streams
