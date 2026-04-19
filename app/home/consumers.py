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
_WS_SEND = "websocket.send"


class HomeConsumer(AsyncWebsocketConsumer):
    _stream_chat_group = None

    async def websocket_connect(self, event):
        log.debug("websocket_connect")
        log.debug(event)
        await self.channel_layer.group_add("home", self.channel_name)
        user = self.scope["user"]
        if hasattr(user, "id") and user.id:
            await self.channel_layer.group_add(f"user-{user.id}", self.channel_name)
        await self.accept()

    async def websocket_disconnect(self, event):
        log.debug("websocket_disconnect")
        if self._stream_chat_group:
            await self._leave_chat_group()
        await self.channel_layer.group_discard("home", self.channel_name)
        user = self.scope["user"]
        if hasattr(user, "id") and user.id:
            await self.channel_layer.group_discard(f"user-{user.id}", self.channel_name)

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
        data = {"user_id": self.scope["user"].id}
        log.debug("process_message: user_id: %s", data["user_id"])
        log.debug(request)
        data.update(request)
        log.debug("data: %s", data)
        method_name = data.pop("method").replace("-", "_")
        log.debug("method_name: %s", method_name)
        method = getattr(self, method_name, None)
        if not method:
            return self._error("No Method Provided!")
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

    async def set_stream_title(self, *, user_id: int = None, name: str = None, title: str = None, **kwargs):
        """
        :param user_id: Integer - self.scope['user'].id - User ID
        :param name: String - Stream Name
        :param title: String - New Stream Title
        :return: Dictionary - With Key: 'success': bool
        """
        log.debug("set_stream_title")
        log.debug("user_id: %s", user_id)
        log.debug("name: %s", name)
        log.debug("title: %s", title)
        if not name:
            return self._error(_ERR_NO_STREAM_NAME, **kwargs)
        if not title:
            return self._error("No title provided.", **kwargs)
        stream = await database_sync_to_async(Stream.objects.filter)(name=name)
        stream = await database_sync_to_async(lambda qs: qs[0] if qs else None)(stream)
        if not stream:
            return self._error(_ERR_STREAM_NOT_FOUND, **kwargs)
        stream_user_id = await database_sync_to_async(lambda s: s.user.id)(stream)
        if user_id and stream_user_id != user_id:
            return self._error("Stream owned by another user.", **kwargs)
        stream.title = title
        await database_sync_to_async(stream.save)()
        data = {
            "event": "set-stream-title",
            "name": name,
            "title": title,
        }
        await self.channel_layer.group_send("home", {"type": _WS_SEND, "text": json.dumps(data)})

    async def set_stream_description(
        self, *, user_id: int = None, name: str = None, description: str = None, **kwargs
    ):
        """
        :param user_id: Integer - self.scope['user'].id - User ID
        :param name: String - Stream Name
        :param description: String - New Stream Description
        :return: Dictionary - With Key: 'success': bool
        """
        log.debug("set_stream_description")
        log.debug("user_id: %s", user_id)
        log.debug("name: %s", name)
        log.debug("description: %s", description)
        if not name:
            return self._error(_ERR_NO_STREAM_NAME, **kwargs)
        if description is None:
            return self._error("No description provided.", **kwargs)
        stream = await database_sync_to_async(Stream.objects.filter)(name=name)
        stream = await database_sync_to_async(lambda qs: qs[0] if qs else None)(stream)
        if not stream:
            return self._error(_ERR_STREAM_NOT_FOUND, **kwargs)
        stream_user_id = await database_sync_to_async(lambda s: s.user.id)(stream)
        if user_id and stream_user_id != user_id:
            return self._error("Stream owned by another user.", **kwargs)
        stream.description = description
        await database_sync_to_async(stream.save)()
        data = {
            "event": "set-stream-description",
            "name": name,
            "description": description,
        }
        await self.channel_layer.group_send("home", {"type": _WS_SEND, "text": json.dumps(data)})

    def _get_chat_identity(self):
        user = self.scope["user"]
        if hasattr(user, "id") and user.id:
            return {
                "viewer_key": str(user.id),
                "user_id": user.id,
                "username": user.username,
            }
        session = self.scope.get("session")
        session_key = session.session_key if session else self.channel_name
        return {
            "viewer_key": f"anon-{session_key}",
            "user_id": None,
            "username": "Anonymous",
        }

    async def _get_chat_display(self):
        user = self.scope["user"]
        if hasattr(user, "id") and user.id:
            avatar_url = await database_sync_to_async(user.get_avatar_url)()
            display_name = await database_sync_to_async(user.get_name)()
            return display_name, avatar_url
        return "Anonymous", "/static/images/default_avatar.png"

    async def join_stream_chat(self, *, user_id: int = None, name: str = None, **kwargs):
        log.debug("join_stream_chat")
        log.debug("user_id: %s, name: %s", user_id, name)
        if not name:
            return self._error(_ERR_NO_STREAM_NAME, **kwargs)
        stream = await database_sync_to_async(Stream.objects.filter)(name=name)
        stream = await database_sync_to_async(lambda qs: qs[0] if qs else None)(stream)
        if not stream:
            return self._error(_ERR_STREAM_NOT_FOUND, **kwargs)
        if not stream.live_chat:
            return self._error("Chat is not enabled for this stream.", **kwargs)
        if self._stream_chat_group:
            await self._leave_chat_group()
        self._stream_chat_group = f"stream-chat-{name}"
        await self.channel_layer.group_add(self._stream_chat_group, self.channel_name)
        identity = self._get_chat_identity()
        display_name, avatar_url = await self._get_chat_display()
        redis = get_redis_connection("default")
        viewer_key = f"stream:{name}:chat_viewers"
        viewer_data = json.dumps(
            {
                "user_id": identity["user_id"],
                "username": identity["username"],
                "display_name": display_name,
                "avatar_url": avatar_url,
            }
        )
        redis.hset(viewer_key, identity["viewer_key"], viewer_data)
        redis.expire(viewer_key, 300)
        viewers = self._get_chat_viewers(redis, viewer_key)
        await self.channel_layer.group_send(
            self._stream_chat_group,
            {
                "type": _WS_SEND,
                "text": json.dumps({"event": "chat-viewers", "name": name, "viewers": viewers}),
            },
        )
        recent = self._get_recent_messages(redis, name)
        return {"event": "chat-history", "name": name, "messages": recent}

    async def set_stream_live_chat(self, *, user_id: int = None, name: str = None, enabled: bool = None, **kwargs):
        if not name:
            return self._error(_ERR_NO_STREAM_NAME, **kwargs)
        stream = await database_sync_to_async(Stream.objects.filter)(name=name)
        stream = await database_sync_to_async(lambda qs: qs[0] if qs else None)(stream)
        if not stream:
            return self._error(_ERR_STREAM_NOT_FOUND, **kwargs)
        stream_user_id = await database_sync_to_async(lambda s: s.user.id)(stream)
        if user_id and stream_user_id != user_id:
            return self._error("Stream owned by another user.", **kwargs)
        stream.live_chat = bool(enabled)
        await database_sync_to_async(stream.save)()
        anonymous_chat = await database_sync_to_async(lambda s: s.anonymous_chat)(stream)
        data = {
            "event": "chat-settings",
            "name": name,
            "live_chat": stream.live_chat,
            "anonymous_chat": anonymous_chat,
        }
        await self.channel_layer.group_send("home", {"type": _WS_SEND, "text": json.dumps(data)})

    async def set_stream_anonymous_chat(self, *, user_id: int = None, name: str = None, enabled: bool = None, **kwargs):
        if not name:
            return self._error(_ERR_NO_STREAM_NAME, **kwargs)
        stream = await database_sync_to_async(Stream.objects.filter)(name=name)
        stream = await database_sync_to_async(lambda qs: qs[0] if qs else None)(stream)
        if not stream:
            return self._error(_ERR_STREAM_NOT_FOUND, **kwargs)
        stream_user_id = await database_sync_to_async(lambda s: s.user.id)(stream)
        if user_id and stream_user_id != user_id:
            return self._error("Stream owned by another user.", **kwargs)
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
            await self._leave_chat_group()

    async def _leave_chat_group(self):
        group = self._stream_chat_group
        self._stream_chat_group = None
        name = group.replace("stream-chat-", "")
        identity = self._get_chat_identity()
        redis = get_redis_connection("default")
        viewer_key = f"stream:{name}:chat_viewers"
        redis.hdel(viewer_key, identity["viewer_key"])
        await self.channel_layer.group_discard(group, self.channel_name)
        viewers = self._get_chat_viewers(redis, viewer_key)
        await self.channel_layer.group_send(
            group,
            {
                "type": _WS_SEND,
                "text": json.dumps({"event": "chat-viewers", "name": name, "viewers": viewers}),
            },
        )

    async def send_chat_message(self, *, user_id: int = None, name: str = None, message: str = None, **kwargs):
        log.debug("send_chat_message")
        log.debug("user_id: %s, name: %s, message: %s", user_id, name, message)
        if not name:
            return self._error(_ERR_NO_STREAM_NAME, **kwargs)
        if not message or not message.strip():
            return self._error("Empty message.", **kwargs)
        message = message.strip()[:500]
        stream = await database_sync_to_async(Stream.objects.filter)(name=name)
        stream = await database_sync_to_async(lambda qs: qs[0] if qs else None)(stream)
        if not stream:
            return self._error(_ERR_STREAM_NOT_FOUND, **kwargs)
        if not stream.live_chat:
            return self._error("Chat is not enabled for this stream.", **kwargs)
        identity = self._get_chat_identity()
        if not identity["user_id"] and not stream.anonymous_chat:
            return self._error("Anonymous chat is not enabled for this stream.", **kwargs)
        display_name, avatar_url = await self._get_chat_display()
        chat_group = f"stream-chat-{name}"
        msg_data = {
            "user_id": identity["user_id"],
            "username": identity["username"],
            "display_name": display_name,
            "avatar_url": avatar_url,
            "message": message,
            "timestamp": time.time(),
        }
        redis = get_redis_connection("default")
        history_key = f"stream:{name}:chat_history"
        redis.lpush(history_key, json.dumps(msg_data))
        redis.ltrim(history_key, 0, 49)
        redis.expire(history_key, 3600)
        broadcast = {"event": "chat-message", "name": name}
        broadcast.update(msg_data)
        await self.channel_layer.group_send(
            chat_group,
            {
                "type": _WS_SEND,
                "text": json.dumps(broadcast),
            },
        )

    @staticmethod
    def _get_chat_viewers(redis, viewer_key):
        raw = redis.hgetall(viewer_key)
        viewers = []
        for v in raw.values():
            try:
                viewers.append(json.loads(v))
            except (json.JSONDecodeError, TypeError):
                pass
        return viewers

    @staticmethod
    def _get_recent_messages(redis, stream_name):
        history_key = f"stream:{stream_name}:chat_history"
        raw = redis.lrange(history_key, 0, 49)
        messages = []
        for item in reversed(raw):
            try:
                messages.append(json.loads(item))
            except (json.JSONDecodeError, TypeError):
                pass
        return messages

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
