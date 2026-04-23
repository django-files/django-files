import hashlib
import inspect
import json
import logging
import time
from io import BytesIO
from typing import List, Optional

from asgiref.sync import async_to_sync, sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.forms.models import model_to_dict
from django_redis import get_redis_connection
from home.models import Albums, Files, Stream
from home.tasks import version_check
from home.util.file import process_file
from home.util.storage import file_rename
from oauth.models import CustomUser
from pytimeparse2 import parse
from settings.models import SiteSettings

log = logging.getLogger("app")

_ERR_NO_STREAM_NAME = "No stream name provided."
_ERR_STREAM_NOT_FOUND = "Stream not found."
_ERR_STREAM_OWNED_BY_OTHER = "Stream owned by another user."
_ERR_SESSION_NOT_READY = "Session not ready."
_WS_SEND = "websocket.send"

# Explicit allowlist of methods callable via WebSocket.
# Any name not in this set is rejected before getattr is called.
_ALLOWED_METHODS = frozenset(
    {
        "authorize",
        "paste_text",
        "delete_files",
        "delete_album",
        "toggle_private_file",
        "private_files",
        "set_expr_files",
        "set_password_file",
        "set_file_name",
        "set_stream_title",
        "set_stream_description",
        "set_stream_live_chat",
        "set_stream_anonymous_chat",
        "join_stream_chat",
        "leave_stream_chat",
        "send_chat_message",
        "set_chat_name",
        "ban_chat_user",
        "ban_message_cleanup",
        "set_file_albums",
        "remove_file_album",
        "add_file_album",
        "check_for_update",
    }
)


class HomeConsumer(AsyncWebsocketConsumer):
    _stream_chat_group = None

    async def websocket_connect(self, event):
        log.debug("websocket_connect")
        log.debug(event)
        await self.channel_layer.group_add("home", self.channel_name)
        user = self.scope["user"]
        if hasattr(user, "id") and user.id:
            await self.channel_layer.group_add(f"user-{user.id}", self.channel_name)
        session = self.scope.get("session")
        if session and not session.session_key:
            await database_sync_to_async(session.save)()
        await self.accept()

    async def websocket_disconnect(self, event):
        log.debug("websocket_disconnect")
        if self._stream_chat_group:
            await self._leave_chat_group(hard=False)
        await self.channel_layer.group_discard("home", self.channel_name)
        user = self.scope["user"]
        if hasattr(user, "id") and user.id:
            await self.channel_layer.group_discard(f"user-{user.id}", self.channel_name)
        await super().websocket_disconnect(event)

    async def websocket_send(self, event):
        log.debug("websocket_send")
        log.debug(event)
        log.debug("client: %s", self.scope["client"])
        log.debug("user: %s", self.scope["user"])
        if self.scope["client"][1] is None:
            return log.debug("client 1 is None")
        await self.send(text_data=event["text"])

    async def websocket_receive(self, event):
        log.debug("websocket_receive")
        log.debug(event)
        log.debug("client: %s", self.scope["client"])
        log.debug("user: %s", self.scope["user"])

        # handle text messages
        if "ping" == event["text"]:
            log.debug("ping->pong")
            if self._stream_chat_group:
                name = self._stream_chat_group.replace("stream-chat-", "")
                identity = self._get_chat_identity()
                if identity:
                    await sync_to_async(self._redis_ping_presence)(name, identity)
            return await self.send(text_data="pong")

        # handle json messages
        try:
            request = json.loads(event["text"])
        except Exception as error:
            log.debug(error)
            return self._error(f"Error: {error}")
        if "method" not in request:
            return self._error("Unknown Request.")
        data = await self.process_message(request)
        if data:
            await self.send(text_data=json.dumps(data))

    async def process_message(self, request: dict) -> Optional[dict]:
        # require authenticated user
        if not self.scope["user"]:
            return self._error("Authentication Required!")

        # Validate method against allowlist before calling getattr
        method_name = request.get("method", "").replace("-", "_")
        if method_name not in _ALLOWED_METHODS:
            return self._error("No Method Provided!")

        # Merge client params, then overwrite user_id with the server-side value
        # so the client cannot impersonate another user.
        data = {k: v for k, v in request.items() if k != "method"}
        data["user_id"] = self.scope["user"].id

        log.debug("process_message: user_id: %s", data["user_id"])
        log.debug(data)

        method = getattr(self, method_name)
        if inspect.iscoroutinefunction(method):
            response = await method(**data)
        else:
            response = await database_sync_to_async(method)(**data)
        log.debug(response)
        return response

    @staticmethod
    def _error(message, **kwargs) -> dict:
        # TODO: Look Into This Functionality
        response = {
            "success": False,
            "bsClass": "danger",
            "event": "message",
            "message": message,
        }
        response.update(**kwargs)
        log.debug(response)
        return response

    # @staticmethod
    # def _success(data: Optional[Union[str, dict]] = None, **kwargs) -> dict:
    #     # TODO: Look Into This Functionality
    #     response = {'success': True, 'bsClass': 'success'}
    #     if isinstance(data, str):
    #         response['message'] = data
    #     if isinstance(data, dict):
    #         response.update(data)
    #     response.update(**kwargs)
    #     return response

    def authorize(self, *, authorization: str = None, **kwargs):
        log.debug("authorize")
        log.debug("authorization: %s", authorization)
        user = CustomUser.objects.filter(authorization=authorization)
        if not user:
            return self._error("Invalid Authorization.")
        self.scope["user"] = user[0]
        async_to_sync(self.channel_layer.group_add)(f"user-{self.scope['user'].id}", self.channel_name)
        return {"username": user[0].username, "first_name": user[0].first_name}

    def paste_text(self, *, user_id: int = None, text_data: str = None, **kwargs):
        log.debug("paste_text")
        log.debug("user_id: %s", user_id)
        log.debug("text_data: %s", text_data)
        log.debug("kwargs: %s", kwargs)
        if not text_data:
            return self._error("Text Data is Required.", **kwargs)
        name = kwargs.pop("name", None)
        log.debug("name: %s", name)
        if name:
            kwargs.pop("format", None)
        else:
            name = "text.txt"
        f = BytesIO(bytes(text_data, "utf-8"))
        file = process_file(name, f, user_id, **kwargs)
        log.debug("file.name: %s", file.name)

    def delete_files(self, *, user_id: int = None, pks: List[List[int]] = None, **kwargs) -> Optional[dict]:
        """
        :param user_id: Integer - self.scope['user'].id - User ID
        :param pks: List of Integers - File IDs
        :return: Dictionary - With Key: 'success': bool
        """
        log.debug("delete_files")
        log.debug("user_id: %s", user_id)
        log.debug("pks: %s", pks)
        pks = pks[0]
        files = Files.objects.filter(**filter_kwargs(pks, user_id))
        if len(files) > 0:
            files.delete()
        else:
            return self._error("File not found.", **kwargs)

    def delete_album(self, *, user_id: int = None, pk: int = None, **kwargs) -> Optional[dict]:
        """
        :param user_id: Integer - self.scope['user'].id - User ID
        :param pk: Integer - File ID
        :return: Dictionary - With Key: 'success': bool
        """
        log.debug("delete_albums")
        log.debug("user_id: %s", user_id)
        log.debug("pk: %s", pk)
        if album := Albums.objects.filter(pk=pk):
            if album[0].user.id != user_id:
                return self._error("File owned by another user.", **kwargs)
            album[0].delete()
        else:
            return self._error("Album not found.", **kwargs)

    def toggle_private_file(self, *, user_id: int = None, pk: int = None, **kwargs) -> dict:
        """
        :param user_id: Integer - self.scope['user'].id - User ID
        :param pk: Integer - File ID
        :return: Dictionary - With Key: 'success': bool
        """
        log.debug("toggle_private_file")
        log.debug("user_id: %s", user_id)
        log.debug("pk: %s", pk)
        if file := Files.objects.filter(pk=pk):
            if user_id and file[0].user.id != user_id:
                return self._error("File owned by another user.", **kwargs)
            file[0].private = not file[0].private
            file[0].save(update_fields=["private"])
            response = model_to_dict(file[0], exclude=["file", "thumb", "albums"])
            response.update({"event": "toggle-private-file"})
            log.debug("response: %s", response)
            return response
        return self._error("File not found.", **kwargs)

    def private_files(self, *, user_id: int = None, pks: List[int] = None, private: bool, **kwargs) -> dict:
        """
        :param user_id: Integer - self.scope['user'].id - User ID
        :param pks: List of Integers - File IDs
        :param private: Bool, False Make Public, True Make Private
        :return: Dictionary - With Key: 'success': bool
        """
        log.debug("private_files")
        log.debug("user_id: %s", user_id)
        log.info("pks: %s", pks)
        files = Files.objects.filter(**filter_kwargs(pks, user_id))
        files.update(private=private)
        if len(files) > 0:
            response = {"objects": []}
            for file in files:
                response["objects"].append(model_to_dict(file, exclude=["file", "thumb", "albums"]))
            response.update({"event": "toggle-private-file"})
            return response
        return self._error("File(s) not found.", **kwargs)

    def set_expr_files(self, *, user_id: int = None, pks: List[int] = None, expr: str = None, **kwargs) -> dict:
        """
        :param user_id: Integer - self.scope['user'].id - User ID
        :param pks: List of Integer - File ID
        :param expr: String - File Expire String
        :return: Dictionary - With Key: 'success': bool
        """
        log.debug("set_expr_file")
        log.debug("user_id: %s", user_id)
        log.debug("pks: %s", pks)
        log.debug("expr: %s", expr)
        log.debug("kwargs: %s", kwargs)
        if expr and not parse(expr):
            return self._error(f"Invalid Expire: {expr}", **kwargs)
        files = Files.objects.filter(**filter_kwargs(pks, user_id))
        for file in files:
            file.expr = expr or ""
        Files.objects.bulk_update(files, ["expr"])
        if len(files) > 0:
            response = {"objects": []}
            for file in files:
                response["objects"].append(model_to_dict(file, exclude=["file", "thumb", "albums"]))
            response.update({"event": "set-expr-file"})
            log.debug("response: %s", response)
            return response
        return self._error("File(s) not found.", **kwargs)

    def set_password_file(self, *, user_id: int = None, pk: int = None, password: str = None, **kwargs) -> dict:
        """
        :param user_id: Integer - self.scope['user'].id - User ID
        :param pk: Integer - File ID
        :param password: String - File Password String
        :return: Dictionary - With Key: 'success': bool
        """
        log.debug("set_password_file")
        log.debug("user_id: %s", user_id)
        log.debug("pk: %s", pk)
        if file := Files.objects.filter(pk=pk):
            if user_id and file[0].user.id != user_id:
                return self._error("File owned by another user.", **kwargs)
            log.debug("password: %s", password)
            file[0].password = password or ""
            file[0].save(update_fields=["password"])
            response = model_to_dict(file[0], exclude=["file", "thumb", "albums"])
            response.update({"event": "set-password-file"})
            log.debug("response: %s", response)
            return response
        return self._error("File not found.", **kwargs)

    def set_file_name(self, *, user_id: int = None, pk: int = None, name: str = None, **kwargs) -> dict:
        """
        :param user_id: Integer - self.scope['user'].id - User ID
        :param pk: Integer - File ID
        :param name: String - File Name String
        :return: Dictionary - With Key: 'success': bool
        """
        log.debug("set_file_name")
        log.debug("user_id: %s", user_id)
        log.debug("pk: %s", pk)
        if not name:
            return self._error("No filename provided.", **kwargs)
        if len(Files.objects.filter(name=name)) != 0:
            return self._error("Filename already taken!", **kwargs)
        if file := Files.objects.filter(pk=pk):
            file = file[0]
            if user_id and file.user.id != user_id:
                return self._error("File owned by another user.", **kwargs)
            old_name = file.name
            if file := file_rename(file, name):
                response = model_to_dict(file, exclude=["file", "thumb", "albums"])
                response.update(
                    {
                        "event": "set-file-name",
                        "uri": file.preview_uri(),
                        "raw_uri": file.raw_path,
                        "old_name": old_name,
                    }
                )
                return response
        return self._error("File not found.", **kwargs)

    # -------------------------------------------------------------------------
    # Stream metadata — title & description
    # -------------------------------------------------------------------------

    async def set_stream_title(self, *, user_id: int = None, name: str = None, title: str = None, **kwargs):
        log.debug("set_stream_title: user_id=%s, name=%s", user_id, name)
        if not name:
            return self._error(_ERR_NO_STREAM_NAME, **kwargs)
        if not title:
            return self._error("No title provided.", **kwargs)
        stream = await self._fetch_stream(name)
        if not stream:
            return self._error(_ERR_STREAM_NOT_FOUND, **kwargs)
        err = await self._check_stream_owner_permission(stream, user_id, _ERR_STREAM_OWNED_BY_OTHER, **kwargs)
        if err:
            return err
        stream.title = title
        await database_sync_to_async(stream.save)()
        data = {"event": "set-stream-title", "name": name, "title": title}
        await self.channel_layer.group_send("home", {"type": _WS_SEND, "text": json.dumps(data)})

    async def set_stream_description(
        self, *, user_id: int = None, name: str = None, description: str = None, **kwargs
    ):
        log.debug("set_stream_description: user_id=%s, name=%s", user_id, name)
        if not name:
            return self._error(_ERR_NO_STREAM_NAME, **kwargs)
        if description is None:
            return self._error("No description provided.", **kwargs)
        stream = await self._fetch_stream(name)
        if not stream:
            return self._error(_ERR_STREAM_NOT_FOUND, **kwargs)
        err = await self._check_stream_owner_permission(stream, user_id, _ERR_STREAM_OWNED_BY_OTHER, **kwargs)
        if err:
            return err
        stream.description = description
        await database_sync_to_async(stream.save)()
        data = {"event": "set-stream-description", "name": name, "description": description}
        await self.channel_layer.group_send("home", {"type": _WS_SEND, "text": json.dumps(data)})

    # -------------------------------------------------------------------------
    # Chat identity helpers (no I/O — safe to call in async context)
    # -------------------------------------------------------------------------

    def _anon_name(self, session_key: str) -> str:
        number = int(hashlib.sha256(session_key.encode()).hexdigest(), 16) % 100000
        return f"Anonymous#{number:05d}"

    def _get_chat_identity(self):
        user = self.scope["user"]
        if hasattr(user, "id") and user.id:
            return {
                "viewer_key": str(user.id),
                "user_id": user.id,
                "username": user.username,
            }
        session = self.scope.get("session")
        session_key = session.session_key if session else None
        if not session_key:
            return None
        return {
            "viewer_key": f"anon-{session_key}",
            "user_id": None,
            "username": self._anon_name(session_key),
        }

    async def _get_chat_display(self):
        user = self.scope["user"]
        session = self.scope.get("session")
        custom_name = session.get("chat_custom_name") if session else None
        if hasattr(user, "id") and user.id:
            avatar_url = await database_sync_to_async(user.get_avatar_url)()
            display_name = custom_name if custom_name else await database_sync_to_async(user.get_name)()
            return display_name, avatar_url
        session_key = session.session_key if session else None
        if not session_key:
            return None, None
        if custom_name:
            number = int(hashlib.sha256(session_key.encode()).hexdigest(), 16) % 100000
            display_name = f"{custom_name}#{number:05d}"
        else:
            display_name = self._anon_name(session_key)
        return display_name, "/static/images/default_avatar.png"

    # -------------------------------------------------------------------------
    # Chat — join / leave
    # -------------------------------------------------------------------------

    async def join_stream_chat(self, *, user_id: int = None, name: str = None, **kwargs):
        log.debug("join_stream_chat: user_id=%s, name=%s", user_id, name)
        if not name:
            return self._error(_ERR_NO_STREAM_NAME, **kwargs)
        stream = await self._fetch_stream(name)
        if not stream or not stream.live_chat:
            return self._error("Chat is not available.", **kwargs)
        identity = self._get_chat_identity()
        if identity is None:
            if self._stream_chat_group:
                await self._leave_chat_group()
            return {"event": "chat-retry", "name": name}

        display_name, avatar_url = await self._get_chat_display()
        viewer_data_dict = {
            "viewer_id": identity["viewer_key"],
            "user_id": identity["user_id"],
            "username": identity["username"],
            "display_name": display_name,
            "avatar_url": avatar_url,
        }

        # All Redis I/O in one sync call to avoid blocking the event loop
        banned, reconnecting, stale, viewers, recent = await sync_to_async(self._redis_join_chat)(
            name, identity, viewer_data_dict
        )

        if banned:
            if self._stream_chat_group:
                await self._leave_chat_group()
            return {"event": "chat-banned", "name": name}

        if self._stream_chat_group:
            if reconnecting:
                old_group = self._stream_chat_group
                self._stream_chat_group = None
                await self.channel_layer.group_discard(old_group, self.channel_name)
            else:
                await self._leave_chat_group()

        if stale:
            chat_group = f"stream-chat-{name}"
            for stale_viewer_id in stale:
                await self.channel_layer.group_send(
                    chat_group,
                    {
                        "type": _WS_SEND,
                        "text": json.dumps({"event": "chat-viewer-left", "name": name, "viewer_id": stale_viewer_id}),
                    },
                )

        self._stream_chat_group = f"stream-chat-{name}"
        await self.channel_layer.group_add(self._stream_chat_group, self.channel_name)

        if not reconnecting:
            await self.channel_layer.group_send(
                self._stream_chat_group,
                {
                    "type": _WS_SEND,
                    "text": json.dumps({"event": "chat-viewer-joined", "name": name, "viewer": viewer_data_dict}),
                },
            )

        return {
            "event": "chat-history",
            "name": name,
            "messages": recent,
            "viewers": viewers,
            "viewer_id": identity["viewer_key"],
        }

    async def set_stream_live_chat(self, *, user_id: int = None, name: str = None, enabled: bool = None, **kwargs):
        if not name:
            return self._error(_ERR_NO_STREAM_NAME, **kwargs)
        stream = await self._fetch_stream(name)
        if not stream:
            return self._error(_ERR_STREAM_NOT_FOUND, **kwargs)
        err = await self._check_stream_owner_permission(stream, user_id, _ERR_STREAM_OWNED_BY_OTHER, **kwargs)
        if err:
            return err
        stream.live_chat = bool(enabled)
        await database_sync_to_async(stream.save)()
        data = {
            "event": "chat-settings",
            "name": name,
            "live_chat": stream.live_chat,
            "anonymous_chat": stream.anonymous_chat,
        }
        await self.channel_layer.group_send("home", {"type": _WS_SEND, "text": json.dumps(data)})

    async def set_stream_anonymous_chat(
        self, *, user_id: int = None, name: str = None, enabled: bool = None, **kwargs
    ):
        if not name:
            return self._error(_ERR_NO_STREAM_NAME, **kwargs)
        stream = await self._fetch_stream(name)
        if not stream:
            return self._error(_ERR_STREAM_NOT_FOUND, **kwargs)
        err = await self._check_stream_owner_permission(stream, user_id, _ERR_STREAM_OWNED_BY_OTHER, **kwargs)
        if err:
            return err
        stream.anonymous_chat = bool(enabled)
        await database_sync_to_async(stream.save)()
        data = {
            "event": "chat-settings",
            "name": name,
            "live_chat": stream.live_chat,
            "anonymous_chat": stream.anonymous_chat,
        }
        await self.channel_layer.group_send("home", {"type": _WS_SEND, "text": json.dumps(data)})

    async def leave_stream_chat(self, *, user_id: int = None, name: str = None, **kwargs):
        log.debug("leave_stream_chat")
        if self._stream_chat_group:
            await self._leave_chat_group(hard=True)

    async def _leave_chat_group(self, hard: bool = True):
        group = self._stream_chat_group
        self._stream_chat_group = None
        name = group.replace("stream-chat-", "")
        identity = self._get_chat_identity()
        await self.channel_layer.group_discard(group, self.channel_name)
        if hard and identity:
            await sync_to_async(self._redis_leave_chat)(name, identity)
            await self.channel_layer.group_send(
                group,
                {
                    "type": _WS_SEND,
                    "text": json.dumps(
                        {"event": "chat-viewer-left", "name": name, "viewer_id": identity["viewer_key"]}
                    ),
                },
            )
        # Soft disconnect: just leave the channel group. The presence key expires on its
        # own TTL; _prune_stale_viewers cleans up the hash on the next join.

    # -------------------------------------------------------------------------
    # Chat — messaging
    # -------------------------------------------------------------------------

    async def send_chat_message(self, *, user_id: int = None, name: str = None, message: str = None, **kwargs):
        log.debug("send_chat_message: user_id=%s, name=%s", user_id, name)
        if not name:
            return self._error(_ERR_NO_STREAM_NAME, **kwargs)
        if not message or not message.strip():
            return self._error("Empty message.", **kwargs)
        message = message.strip()[:500]

        stream = await self._fetch_stream(name)
        if not stream:
            return self._error(_ERR_STREAM_NOT_FOUND, **kwargs)
        if not stream.live_chat:
            return self._error("Chat is not enabled for this stream.", **kwargs)

        identity = self._get_chat_identity()
        if identity is None:
            return self._error(_ERR_SESSION_NOT_READY, **kwargs)
        if not identity["user_id"] and not stream.anonymous_chat:
            return self._error("Anonymous chat is not enabled for this stream.", **kwargs)

        display_name, avatar_url = await self._get_chat_display()
        msg_data = {
            "user_id": identity["user_id"],
            "username": identity["username"],
            "display_name": display_name,
            "avatar_url": avatar_url,
            "message": message,
            "timestamp": time.time(),
        }

        # Rate limit, ban check, and history push in one sync call
        error = await sync_to_async(self._redis_send_message)(name, identity, msg_data)
        if error == "rate_limited":
            return self._error("Slow down. Too many messages.", **kwargs)
        if error == "banned":
            return self._error("You are banned from this chat.", **kwargs)

        broadcast = {"event": "chat-message", "name": name}
        broadcast.update(msg_data)
        await self.channel_layer.group_send(
            f"stream-chat-{name}",
            {"type": _WS_SEND, "text": json.dumps(broadcast)},
        )

    # -------------------------------------------------------------------------
    # Chat — name change
    # -------------------------------------------------------------------------

    async def set_chat_name(self, *, user_id: int = None, name: str = None, custom_name: str = None, **kwargs):
        log.debug("set_chat_name: user_id=%s, name=%s, custom_name=%s", user_id, name, custom_name)
        if not name:
            return self._error(_ERR_NO_STREAM_NAME, **kwargs)
        identity = self._get_chat_identity()
        if identity is None:
            return self._error(_ERR_SESSION_NOT_READY, **kwargs)
        if not custom_name or not custom_name.strip():
            return self._error("Name cannot be empty.", **kwargs)
        custom_name = custom_name.strip()[:32].replace("#", "")
        if not custom_name:
            return self._error("Invalid name.", **kwargs)

        user = self.scope["user"]
        is_admin = getattr(user, "is_superuser", False)

        if not is_admin:
            rate_key = f"chat:name_change:{identity['viewer_key']}"
            ttl = await sync_to_async(self._redis_check_name_rate)(rate_key)
            if ttl > 0:
                mins, secs = divmod(ttl, 60)
                wait = f"{mins}m {secs}s" if mins else f"{secs}s"
                return self._error(f"Name change on cooldown. Try again in {wait}.", **kwargs)

        # Block names that match any registered username or display name to prevent impersonation.
        name_lower = custom_name.lower()
        user_name_matches = hasattr(user, "username") and user.username.lower() == name_lower
        first_name_matches = bool(user.first_name) and user.first_name.lower() == name_lower
        is_own_name = identity["user_id"] is not None and (user_name_matches or first_name_matches)
        if not is_own_name and await self._is_name_taken(custom_name):
            return self._error("That name is already used by a registered user.", **kwargs)

        session = self.scope.get("session")
        display_name = custom_name
        if identity["user_id"] is None:
            display_name, err = await self._build_anonymous_display_name(custom_name, session)
            if err:
                return self._error(err, **kwargs)

        if session:
            session["chat_custom_name"] = custom_name
            await database_sync_to_async(session.save)()

        rate_key = f"chat:name_change:{identity['viewer_key']}" if not is_admin else None
        viewers = await sync_to_async(self._redis_apply_name_change)(name, identity, display_name, rate_key)
        if viewers is not None:
            await self.channel_layer.group_send(
                self._stream_chat_group,
                {"type": _WS_SEND, "text": json.dumps({"event": "chat-viewers", "name": name, "viewers": viewers})},
            )

        return {"event": "chat-name-set", "name": name, "display_name": display_name}

    # -------------------------------------------------------------------------
    # Chat — moderation
    # -------------------------------------------------------------------------

    async def ban_chat_user(self, *, user_id: int = None, name: str = None, target: str = None, **kwargs):
        log.debug("ban_chat_user: user_id=%s, name=%s, target=%s", user_id, name, target)
        if not name:
            return self._error(_ERR_NO_STREAM_NAME, **kwargs)
        if not target or not target.strip():
            return self._error("No ban target provided.", **kwargs)
        stream = await self._fetch_stream(name)
        if not stream:
            return self._error(_ERR_STREAM_NOT_FOUND, **kwargs)
        err = await self._check_stream_owner_permission(
            stream, user_id, "Only the stream owner can ban users.", **kwargs
        )
        if err:
            return err

        identity = self._get_chat_identity()
        error, target_viewer_key, viewers = await sync_to_async(self._redis_ban_user)(name, identity, target.strip())
        if error:
            return self._error(error, **kwargs)

        chat_group = f"stream-chat-{name}"
        await self.channel_layer.group_send(
            chat_group,
            {
                "type": _WS_SEND,
                "text": json.dumps({"event": "chat-banned", "name": name, "viewer_id": target_viewer_key}),
            },
        )
        await self.channel_layer.group_send(
            chat_group,
            {
                "type": _WS_SEND,
                "text": json.dumps({"event": "chat-viewers", "name": name, "viewers": viewers}),
            },
        )
        return None

    async def ban_message_cleanup(self, *, user_id: int = None, name: str = None, target: str = None, **kwargs):
        log.debug("ban_message_cleanup: user_id=%s, name=%s, target=%s", user_id, name, target)
        if not name:
            return self._error(_ERR_NO_STREAM_NAME, **kwargs)
        if not target or not target.strip():
            return self._error("No target provided.", **kwargs)
        stream = await self._fetch_stream(name)
        if not stream:
            return self._error(_ERR_STREAM_NOT_FOUND, **kwargs)
        err = await self._check_stream_owner_permission(
            stream, user_id, "Only the stream owner can clean up messages.", **kwargs
        )
        if err:
            return err

        target_username, target_user_id = await sync_to_async(self._redis_cleanup_history)(
            name, target.strip().lower()
        )
        if target_username is None:
            return self._error(f"No messages found from '{target.strip()}'.", **kwargs)

        await self.channel_layer.group_send(
            f"stream-chat-{name}",
            {
                "type": _WS_SEND,
                "text": json.dumps(
                    {
                        "event": "chat-message-cleanup",
                        "name": name,
                        "username": target_username,
                        "user_id": target_user_id,
                    }
                ),
            },
        )
        return None

    # -------------------------------------------------------------------------
    # Async helper methods (DB access)
    # -------------------------------------------------------------------------

    async def _fetch_stream(self, name: str):
        """Fetch a Stream by name, or return None."""
        return await Stream.objects.filter(name=name).afirst()

    async def _check_stream_owner_permission(self, stream, user_id: int, error_msg: str, **kwargs):
        """Return an error dict if the caller is not a superuser or the stream owner, else None."""
        stream_user_id = await database_sync_to_async(lambda s: s.user.id)(stream)
        requester = self.scope["user"]
        is_superuser = await database_sync_to_async(lambda u: getattr(u, "is_superuser", False))(requester)
        if not is_superuser and (not user_id or stream_user_id != user_id):
            return self._error(error_msg, **kwargs)
        return None

    async def _is_name_taken(self, custom_name: str) -> bool:
        """Return True if custom_name conflicts with any registered username or first name."""
        if await database_sync_to_async(CustomUser.objects.filter(username__iexact=custom_name).exists)():
            return True
        return await database_sync_to_async(CustomUser.objects.filter(first_name__iexact=custom_name).exists)()

    async def _build_anonymous_display_name(self, custom_name: str, session):
        """Build a discriminated display name for an anonymous user. Returns (name, error) tuple."""
        session_key = session.session_key if session else None
        if not session_key:
            return None, _ERR_SESSION_NOT_READY
        number = int(hashlib.sha256(session_key.encode()).hexdigest(), 16) % 100000
        return f"{custom_name}#{number:05d}", None

    # -------------------------------------------------------------------------
    # Sync Redis helpers — called via sync_to_async to avoid blocking the loop
    # -------------------------------------------------------------------------

    def _redis_ping_presence(self, name: str, identity: dict) -> None:
        """Refresh presence key and extend the viewer hash TTL on each heartbeat ping."""
        redis = get_redis_connection("default")
        viewer_key = f"stream:{name}:chat_viewers"
        pipe = redis.pipeline()
        pipe.set(f"stream:{name}:chat_presence:{identity['viewer_key']}", 1, ex=60)
        pipe.expire(viewer_key, 3600)
        pipe.execute()

    def _redis_join_chat(self, name: str, identity: dict, viewer_data_dict: dict) -> tuple:
        """
        Ban check, presence detection, stale-viewer pruning, viewer registration,
        and history + viewer-list fetch — all in one sync call.

        Returns (banned, reconnecting, stale_ids, viewers, recent_messages).
        """
        redis = get_redis_connection("default")

        ban_key = f"stream:{name}:chat_banned"
        if redis.sismember(ban_key, identity["viewer_key"]):
            return True, False, [], [], []

        viewer_key = f"stream:{name}:chat_viewers"
        presence_key = f"stream:{name}:chat_presence:{identity['viewer_key']}"

        in_hash = redis.hexists(viewer_key, identity["viewer_key"])
        # Reconnecting = already in hash AND presence key still alive
        reconnecting = in_hash and bool(redis.exists(presence_key))

        stale = self._prune_stale_viewers(redis, name, viewer_key)

        # Register/refresh presence and viewer data in a single pipeline
        pipe = redis.pipeline()
        pipe.set(presence_key, 1, ex=60)
        pipe.hset(viewer_key, identity["viewer_key"], json.dumps(viewer_data_dict))
        pipe.expire(viewer_key, 3600)  # long TTL; refreshed on every ping
        pipe.execute()

        viewers = self._get_chat_viewers(redis, viewer_key)
        recent = self._get_recent_messages(redis, name)
        return False, reconnecting, stale, viewers, recent

    def _redis_leave_chat(self, name: str, identity: dict) -> None:
        """Hard-leave: remove viewer from hash and delete presence key atomically."""
        redis = get_redis_connection("default")
        pipe = redis.pipeline()
        pipe.hdel(f"stream:{name}:chat_viewers", identity["viewer_key"])
        pipe.delete(f"stream:{name}:chat_presence:{identity['viewer_key']}")
        pipe.execute()

    def _redis_send_message(self, name: str, identity: dict, msg_data: dict) -> Optional[str]:
        """
        Fixed-window rate limit (max 3 msgs/s), ban check, and history push.

        Returns 'rate_limited', 'banned', or None on success.
        The rate-limit window TTL is set only on window creation (SET NX EX),
        so sending multiple messages does not reset the 1-second window.
        """
        redis = get_redis_connection("default")

        rate_key = f"stream:{name}:rate:{identity['viewer_key']}"
        pipe = redis.pipeline()
        pipe.set(rate_key, 0, nx=True, ex=1)  # initialize window only if key is new
        pipe.incr(rate_key)
        _, count = pipe.execute()
        if count > 3:
            return "rate_limited"

        ban_key = f"stream:{name}:chat_banned"
        if redis.sismember(ban_key, identity["viewer_key"]):
            return "banned"

        history_key = f"stream:{name}:chat_history"
        pipe = redis.pipeline()
        pipe.lpush(history_key, json.dumps(msg_data))
        pipe.ltrim(history_key, 0, 49)
        pipe.expire(history_key, 3600)
        pipe.execute()

        return None

    def _redis_check_name_rate(self, rate_key: str) -> int:
        """Return the TTL (seconds) of the name-change rate-limit key, or -2 if unset."""
        redis = get_redis_connection("default")
        return redis.ttl(rate_key)

    def _redis_apply_name_change(
        self, name: str, identity: dict, display_name: str, rate_key: Optional[str]
    ) -> Optional[list]:
        """
        Set the name-change rate limit (if rate_key given) and update the viewer's
        display_name in the hash. Returns the refreshed viewer list, or None if
        the viewer is not currently in the hash.
        """
        redis = get_redis_connection("default")
        if rate_key:
            redis.set(rate_key, 1, ex=300)
        if not self._stream_chat_group:
            return None
        viewer_key = f"stream:{name}:chat_viewers"
        raw = redis.hget(viewer_key, identity["viewer_key"])
        if not raw:
            return None
        try:
            viewer_data = json.loads(raw)
            viewer_data["display_name"] = display_name
            redis.hset(viewer_key, identity["viewer_key"], json.dumps(viewer_data))
            return self._get_chat_viewers(redis, viewer_key)
        except (json.JSONDecodeError, TypeError):
            return None

    def _redis_ban_user(self, name: str, identity: Optional[dict], target: str) -> tuple:
        """
        Find target viewer by display name or username, add to the ban set,
        and remove from the viewer hash.

        Returns (error_str, target_viewer_key, viewers).
        On failure error_str is set and the other two are None.
        """
        redis = get_redis_connection("default")
        viewer_key = f"stream:{name}:chat_viewers"
        target_viewer_key = self._find_viewer_by_name(redis, viewer_key, target.lower())
        if not target_viewer_key:
            return f"No viewer found matching '{target}'.", None, None
        if identity and target_viewer_key == identity["viewer_key"]:
            return "You cannot ban yourself.", None, None

        ban_key = f"stream:{name}:chat_banned"
        pipe = redis.pipeline()
        pipe.sadd(ban_key, target_viewer_key)
        pipe.expire(ban_key, 86400)
        pipe.hdel(viewer_key, target_viewer_key)
        pipe.execute()

        viewers = self._get_chat_viewers(redis, viewer_key)
        return None, target_viewer_key, viewers

    def _redis_cleanup_history(self, name: str, target_lower: str) -> tuple:
        """
        Remove messages from target user from the history list.

        Returns (target_username, target_user_id), or (None, None) if no messages found.
        """
        redis = get_redis_connection("default")
        history_key = f"stream:{name}:chat_history"
        raw_history = redis.lrange(history_key, 0, -1)
        kept, target_username, target_user_id = self._filter_chat_history(raw_history, target_lower)
        if target_username is None:
            return None, None
        pipe = redis.pipeline()
        pipe.delete(history_key)
        if kept:
            pipe.rpush(history_key, *kept)
            pipe.expire(history_key, 3600)
        pipe.execute()
        return target_username, target_user_id

    # -------------------------------------------------------------------------
    # Static Redis utility methods
    # -------------------------------------------------------------------------

    @staticmethod
    def _prune_stale_viewers(redis, name: str, viewer_key: str) -> list:
        """
        Remove viewers whose presence key has expired (closed browser / missed two
        30s heartbeats). Uses a single pipelined batch of EXISTS calls instead of
        one round-trip per viewer.

        Returns list of pruned viewer_ids for leave broadcasts.
        """
        fields = [f.decode() if isinstance(f, bytes) else f for f in redis.hkeys(viewer_key)]
        if not fields:
            return []
        pipe = redis.pipeline()
        for field in fields:
            pipe.exists(f"stream:{name}:chat_presence:{field}")
        results = pipe.execute()
        stale = [f for f, alive in zip(fields, results, strict=True) if not alive]
        if stale:
            redis.hdel(viewer_key, *stale)
        return stale

    @staticmethod
    def _find_viewer_by_name(redis, viewer_key: str, target_lower: str) -> Optional[str]:
        """Return the viewer key matching target display_name or username (case-insensitive), or None."""
        raw_viewers = redis.hgetall(viewer_key)
        for vk, vraw in raw_viewers.items():
            try:
                v = json.loads(vraw)
            except (json.JSONDecodeError, TypeError):
                continue
            vk_str = vk.decode() if isinstance(vk, bytes) else vk
            if v.get("display_name", "").lower() == target_lower or v.get("username", "").lower() == target_lower:
                return vk_str
        return None

    @staticmethod
    def _filter_chat_history(raw_history, target_lower: str):
        """Filter history entries removing messages from target. Returns (kept, username, user_id)."""
        kept = []
        target_username = None
        target_user_id = None
        for raw in raw_history:
            try:
                msg = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                kept.append(raw)
                continue
            if msg.get("display_name", "").lower() == target_lower or msg.get("username", "").lower() == target_lower:
                target_username = target_username or msg.get("username")
                target_user_id = target_user_id or msg.get("user_id")
            else:
                kept.append(raw)
        return kept, target_username, target_user_id

    @staticmethod
    def _get_chat_viewers(redis, viewer_key: str) -> list:
        raw = redis.hgetall(viewer_key)
        viewers = []
        for v in raw.values():
            try:
                viewers.append(json.loads(v))
            except (json.JSONDecodeError, TypeError):
                pass
        return viewers

    @staticmethod
    def _get_recent_messages(redis, stream_name: str) -> list:
        history_key = f"stream:{stream_name}:chat_history"
        raw = redis.lrange(history_key, 0, 49)
        messages = []
        for item in reversed(raw):
            try:
                messages.append(json.loads(item))
            except (json.JSONDecodeError, TypeError):
                pass
        return messages

    # -------------------------------------------------------------------------
    # File / album management (unchanged)
    # -------------------------------------------------------------------------

    def set_file_albums(self, *, user_id: int = None, pk: int = None, albums: List[int] = None, **kwargs) -> dict:
        """
        :param user_id: Integer - self.scope['user'].id - User ID
        :param pk: Integer - File ID
        :param albums: List - List of Album IDs
        :return: Dictionary - With Key: 'success': bool
        """
        log.debug("set_file_albums")
        log.debug("user_id: %s", user_id)
        log.debug("pk: %s", pk)
        log.debug("albums: %s", albums)
        added = {}
        file_albums = {}
        if file := Files.objects.filter(pk=pk):
            if len(file) == 0:
                return self._error("File not found.", **kwargs)
            if user_id and file[0].user.id != user_id and not file[0].user.is_superuser:
                return self._error("File owned by another user.", **kwargs)
            file_albums = dict(Albums.objects.filter(files__id=pk).values_list("id", "name"))
        if not albums:
            albums = []
        if not isinstance(albums, list):
            albums = [albums]
        albums = [int(album) for album in albums]
        log.debug(f"Sent albums: {albums}")
        log.debug(f"Current Albums: {file_albums}")
        for album in albums:
            if album not in file_albums.keys():
                # if the file is not linked to an album in the list, link it
                album = Albums.objects.filter(id=album)[0]
                file[0].albums.add(album)
                added[album.id] = album.name
                log.debug(f"Adding file {pk} to album {album.name}")
            else:
                # if the album is linked and still in the new album list, remove it from our list
                del file_albums[album]
                log.debug(f"Keeping file {pk} in album {album}")
        for album in file_albums.keys():
            # if a file was linked to an album that we removed unlink it
            log.debug(f"removing {pk} from {album}")
            file[0].albums.remove(Albums.objects.get(id=album))
        return {"event": "set-file-albums", "file_id": pk, "added_to": added, "removed_from": file_albums}

    def remove_file_album(self, *, user_id: int = None, pk: int = None, album: int = None, **kwargs) -> dict:
        """
        :param user_id: Integer - self.scope['user'].id - User ID
        :param pk: Integer - File ID
        :param album: Integer = Album ID
        :return: Dictionary - With Key: 'success': bool
        """
        log.debug("remove_file_album")
        log.debug("user_id: %s", user_id)
        log.debug("pk: %s", pk)
        if not album:
            return self._error("No album specified.", **kwargs)
        if file := Files.objects.filter(pk=pk):
            if len(file) == 0:
                return self._error("File not found.", **kwargs)
            if user_id and file[0].user.id != user_id and not file[0].user.is_superuser:
                return self._error("File owned by another user.", **kwargs)
        album = Albums.objects.get(id=album)
        file[0].albums.remove(album)
        return {"event": "set-file-albums", "file_id": pk, "removed_from": {album.id: album.name}}

    def add_file_album(
        self,
        *,
        user_id: int = None,
        pk: int = None,
        album: int = None,
        album_name: str = None,
        create_if_absent: bool = True,
        **kwargs,
    ) -> dict:
        """
        :param user_id: Integer - self.scope['user'].id - User ID
        :param pk: Integer - File ID
        :param album: Integer = Album ID
        :param album_name: String = Name of Album
        :param create_if_absent: Bool = Bool if to create album if cannot find matching album with name.
        :return: Dictionary - With Key: 'success': bool
        """
        log.debug("remove_file_album")
        log.debug("user_id: %s", user_id)
        log.debug("pk: %s", pk)
        log.debug("name: %s", album_name)
        log.debug("create: %s", create_if_absent)
        if not album and not album_name:
            return self._error("No album specified.", **kwargs)
        if file := Files.objects.filter(pk=pk):
            if len(file) == 0:
                return self._error("File not found.", **kwargs)
            if user_id and file[0].user.id != user_id and not file[0].user.is_superuser:
                return self._error("File owned by another user.", **kwargs)
        qalbum, selected_album = [], None
        if album:
            # find by album id
            qalbum = Albums.objects.filter(pk=album, user_id=user_id)
        elif album_name:
            # find by album name
            qalbum = Albums.objects.filter(name=album_name, user_id=user_id)
        if len(qalbum) > 0:
            selected_album = qalbum[0]
        elif create_if_absent and album_name:
            selected_album = Albums.objects.create(user_id=user_id, name=album_name)
        else:
            return self._error("Album not found.", **kwargs)
        file[0].albums.add(selected_album)
        return {"event": "set-file-albums", "file_id": pk, "added_to": {selected_album.id: selected_album.name}}

    async def check_for_update(self, *args, **kwargs) -> dict:
        log.debug("async - check_for_update")
        data = {"event": "message", "bsclass": "info", "delay": "2000", "message": "Checking for Update..."}
        await self.send(text_data=json.dumps(data))
        result = await sync_to_async(version_check)()
        log.debug("result: %s", result)
        site_settings = await database_sync_to_async(SiteSettings.objects.settings)()
        if site_settings.latest_version:
            message = f"Update Available: {site_settings.latest_version}"
            bsclass, delay = "warning", "6000"
        else:
            message = f"{site_settings.site_title} is Up-to-Date."
            bsclass, delay = "success", "6000"
        return {"event": "message", "bsclass": bsclass, "delay": delay, "message": message}


def filter_kwargs(pks: List[int], user_id: int) -> dict:
    # generates kwargs for filter object, filters to user for non admin api requests
    # accepts list of pks, user id int
    # returns kwargs for django model filter()
    kwargs = {"pk__in": pks}
    if not ((user := CustomUser.objects.get(pk=user_id)).is_superuser):
        kwargs["user"] = user
    return kwargs
