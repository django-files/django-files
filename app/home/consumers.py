import inspect
import json
import logging
from asgiref.sync import async_to_sync, sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.forms.models import model_to_dict
from io import BytesIO
from pytimeparse2 import parse
from typing import Optional, List
from django.core.cache import cache


from home.models import Files, Albums
from home.tasks import version_check
from home.util.file import process_file
from home.util.storage import file_rename
from oauth.models import CustomUser
from settings.models import SiteSettings

log = logging.getLogger('app')


class HomeConsumer(AsyncWebsocketConsumer):
    async def websocket_connect(self, event):
        log.debug('websocket_connect')
        log.debug(event)
        await self.channel_layer.group_add('home', self.channel_name)
        await self.channel_layer.group_add(f"user-{self.scope['user'].id}", self.channel_name)
        await self.accept()

    async def websocket_send(self, event):
        log.debug('websocket_send')
        log.debug(event)
        log.debug('client: %s', self.scope['client'])
        log.debug('user: %s', self.scope['user'])
        if self.scope['client'][1] is None:
            return log.debug('client 1 is None')
        await self.send(text_data=event['text'])

    async def websocket_receive(self, event):
        log.debug('websocket_receive')
        log.debug(event)
        log.debug('client: %s', self.scope['client'])
        log.debug('user: %s', self.scope['user'])

        # handle text messages
        if 'ping' == event['text']:
            log.debug('ping->pong')
            return await self.send(text_data='pong')

        # handle json messages
        try:
            request = json.loads(event['text'])
        except Exception as error:
            log.debug(error)
            return self._error(f'Error: {error}')
        if 'method' not in request:
            return self._error('Unknown Request.')
        data = await self.process_message(request)
        if data:
            await self.send(text_data=json.dumps(data))

    async def process_message(self, request: dict) -> Optional[dict]:
        # require authenticated user
        if not self.scope['user']:
            return self._error('Authentication Required!')
        data = {'user_id': self.scope['user'].id}
        log.debug('process_message: user_id: %s', data['user_id'])
        log.debug(request)
        data.update(request)
        log.debug('data: %s', data)
        method_name = data.pop('method').replace('-', '_')
        log.debug('method_name: %s', method_name)
        method = getattr(self, method_name, None)
        if not method:
            return self._error('No Method Provided!')
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
            'success': False,
            'bsClass': 'danger',
            'event': 'message',
            'message': message,
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
        log.debug('authorize')
        log.debug('authorization: %s', authorization)
        user = CustomUser.objects.filter(authorization=authorization)
        if not user:
            return self._error('Invalid Authorization.')
        self.scope['user'] = user[0]
        async_to_sync(self.channel_layer.group_add)(f"user-{self.scope['user'].id}", self.channel_name)
        return {'username': user[0].username, 'first_name': user[0].first_name}

    def paste_text(self, *, user_id: int = None, text_data: str = None, **kwargs):
        log.debug('paste_text')
        log.debug('user_id: %s', user_id)
        log.debug('text_data: %s', text_data)
        log.debug('kwargs: %s', kwargs)
        if not text_data:
            return self._error('Text Data is Required.', **kwargs)
        name = kwargs.pop('name', None)
        log.debug('name: %s', name)
        if name:
            kwargs.pop('format', None)
        else:
            name = 'text.txt'
        f = BytesIO(bytes(text_data, 'utf-8'))
        file = process_file(name, f, user_id, **kwargs)
        log.debug('file.name: %s', file.name)

    def delete_files(self, *, user_id: int = None, pks: List[int] = [], **kwargs) -> dict:
        """
        :param user_id: Integer - self.scope['user'].id - User ID
        :param pk: List of Integers - File IDs
        :return: Dictionary - With Key: 'success': bool
        """
        log.debug('delete_files')
        log.debug('user_id: %s', user_id)
        log.debug('pks: %s', pks)
        pks = pks[0]
        files = Files.objects.filter(**filter_kwargs(pks, user_id))
        if len(files) > 0:
            files.delete()
        else:
            return self._error('File not found.', **kwargs)

    def delete_album(self, *, user_id: int = None, pk: int = None, **kwargs) -> dict:
        """
        :param user_id: Integer - self.scope['user'].id - User ID
        :param pk: Integer - File ID
        :return: Dictionary - With Key: 'success': bool
        """
        log.debug('delete_albums')
        log.debug('user_id: %s', user_id)
        log.debug('pk: %s', pk)
        if album := Albums.objects.filter(pk=pk):
            if album[0].user.id != user_id:
                return self._error('File owned by another user.', **kwargs)
            album[0].delete()
        else:
            return self._error('Album not found.', **kwargs)

    def toggle_private_file(self, *, user_id: int = None, pk: int = None, **kwargs) -> dict:
        """
        :param user_id: Integer - self.scope['user'].id - User ID
        :param pk: Integer - File ID
        :return: Dictionary - With Key: 'success': bool
        """
        log.debug('toggle_private_file')
        log.debug('user_id: %s', user_id)
        log.debug('pk: %s', pk)
        if file := Files.objects.filter(pk=pk):
            if user_id and file[0].user.id != user_id:
                return self._error('File owned by another user.', **kwargs)
            file[0].private = not file[0].private
            file[0].save(update_fields=['private'])
            response = model_to_dict(file[0], exclude=['file', 'thumb', 'albums'])
            response.update({'event': 'toggle-private-file'})
            log.debug('response: %s', response)
            return response
        return self._error('File not found.', **kwargs)

    def private_files(self, *, user_id: int = None, pks: List[int] = [], private: bool, **kwargs) -> dict:
        """
        :param user_id: Integer - self.scope['user'].id - User ID
        :param pk: List of Integers - File IDs
        :param private: Bool, False Make Public, True Make Private
        :return: Dictionary - With Key: 'success': bool
        """
        log.debug('private_files')
        log.debug('user_id: %s', user_id)
        log.info('pks: %s', pks)
        files = Files.objects.filter(**filter_kwargs(pks, user_id))
        files.update(private=private)
        if len(files) > 0:
            response = {}
            response['objects'] = []
            for file in files:
                response['objects'].append(model_to_dict(file, exclude=['file', 'thumb', 'albums']))
            response.update({'event': 'toggle-private-file'})
            return response
        return self._error('File(s) not found.', **kwargs)

    def set_expr_files(self, *, user_id: int = None, pks: List[int] = [], expr: str = None, **kwargs) -> dict:
        """
        :param user_id: Integer - self.scope['user'].id - User ID
        :param pks: List of Integer - File ID
        :param expr: String - File Expire String
        :return: Dictionary - With Key: 'success': bool
        """
        log.debug('set_expr_file')
        log.debug('user_id: %s', user_id)
        log.debug('pks: %s', pks)
        log.debug('expr: %s', expr)
        log.debug('kwargs: %s', kwargs)
        if expr and not parse(expr):
            return self._error(f'Invalid Expire: {expr}', **kwargs)
        files = Files.objects.filter(**filter_kwargs(pks, user_id))
        for file in files:
            file.expr = expr or ""
        Files.objects.bulk_update(files, ['expr'])
        if len(files) > 0:
            response = {}
            response['objects'] = []
            for file in files:
                response['objects'].append(model_to_dict(file, exclude=['file', 'thumb', 'albums']))
            response.update({'event': 'set-expr-file'})
            log.debug('response: %s', response)
            return response
        return self._error('File(s) not found.', **kwargs)

    def set_password_file(self, *, user_id: int = None, pk: int = None, password: str = None, **kwargs) -> dict:
        """
        :param user_id: Integer - self.scope['user'].id - User ID
        :param pk: Integer - File ID
        :param password: String - File Password String
        :return: Dictionary - With Key: 'success': bool
        """
        log.debug('set_password_file')
        log.debug('user_id: %s', user_id)
        log.debug('pk: %s', pk)
        if file := Files.objects.filter(pk=pk):
            if user_id and file[0].user.id != user_id:
                return self._error('File owned by another user.', **kwargs)
            log.debug('password: %s', password)
            file[0].password = password or ""
            file[0].save(update_fields=['password'])
            response = model_to_dict(file[0], exclude=['file', 'thumb', 'albums'])
            response.update({'event': 'set-password-file'})
            log.debug('response: %s', response)
            return response
        return self._error('File not found.', **kwargs)

    def set_file_name(self, *, user_id: int = None, pk: int = None, name: str = None, **kwargs) -> dict:
        """
        :param user_id: Integer - self.scope['user'].id - User ID
        :param pk: Integer - File ID
        :param name: String - File Name String
        :return: Dictionary - With Key: 'success': bool
        """
        log.debug('set_file_name')
        log.debug('user_id: %s', user_id)
        log.debug('pk: %s', pk)
        if not name:
            return self._error('No filename provided.', **kwargs)
        if len(Files.objects.filter(name=name)) != 0:
            return self._error('Filename already taken!', **kwargs)
        if file := Files.objects.filter(pk=pk):
            file = file[0]
            if user_id and file.user.id != user_id:
                return self._error('File owned by another user.', **kwargs)
            if file_rename(file.file.name, name, True if file.thumb else False):
                old_name = file.name
                file.name = name
                file.file.name = name  # this will rename on OS and cloud
                if file.thumb:
                    file.thumb.name = 'thumbs/' + name  # renames thumbnail
                file[0].save(update_fields=['name'])
                response = model_to_dict(file, exclude=['file', 'thumb', 'albums'])
                response.update({'event': 'set-file-name',
                                 'uri': file.preview_uri(),
                                 'raw_uri': file.raw_path,
                                 'old_name': old_name})
                cache.delete(f'file.urlcache.gallery.{file.pk}')
                return response
        return self._error('File not found.', **kwargs)

    def set_file_albums(self, *, user_id: int = None, pk: int = None, albums: List[int] = None, **kwargs) -> dict:
        """
        :param user_id: Integer - self.scope['user'].id - User ID
        :param pk: Integer - File ID
        :param albums: List - List of Album IDs
        :return: Dictionary - With Key: 'success': bool
        """
        log.debug('set_file_albums')
        log.debug('user_id: %s', user_id)
        log.debug('pk: %s', pk)
        log.debug('albums: %s', albums)
        added = {}
        file_albums = {}
        if file := Files.objects.filter(pk=pk):
            if len(file) == 0:
                return self._error('File not found.', **kwargs)
            if user_id and file[0].user.id != user_id and not file[0].user.is_superuser:
                return self._error('File owned by another user.', **kwargs)
            file_albums = dict(Albums.objects.filter(files__id=pk).values_list('id', 'name'))
        if not albums:
            albums = []
        if not isinstance(albums, list):
            albums = [albums]
        albums = [int(album) for album in albums]
        log.debug(f'Sent albums: {albums}')
        log.debug(f'Current Albums: {file_albums}')
        for album in albums:
            if album not in file_albums.keys():
                # if the file is not linked to an album in the list, link it
                album = Albums.objects.filter(id=album)[0]
                file[0].albums.add(album)
                added[album.id] = album.name
                log.debug(f'Adding file {pk} to album {album.name}')
            else:
                # if the album is linked and still in the new album list, remove it from our list
                del file_albums[album]
                log.debug(f'Keeping file {pk} in album {album}')
        for album in file_albums.keys():
            # if a file was linked to an album that we removed unlink it
            log.debug(f'removing {pk} from {album}')
            file[0].albums.remove(Albums.objects.get(id=album))
        return {'event': 'set-file-albums', 'file_id': pk, 'added_to': added, 'removed_from': file_albums}

    def remove_file_album(self, *, user_id: int = None, pk: int = None, album: int = None, **kwargs) -> dict:
        """
        :param user_id: Integer - self.scope['user'].id - User ID
        :param pk: Integer - File ID
        :param album: Integer = Album ID
        :return: Dictionary - With Key: 'success': bool
        """
        log.debug('remove_file_album')
        log.debug('user_id: %s', user_id)
        log.debug('pk: %s', pk)
        if not album:
            return self._error('No album specified.', **kwargs)
        if file := Files.objects.filter(pk=pk):
            if len(file) == 0:
                return self._error('File not found.', **kwargs)
            if user_id and file[0].user.id != user_id and not file[0].user.is_superuser:
                return self._error('File owned by another user.', **kwargs)
        album = Albums.objects.get(id=album)
        file[0].albums.remove(album)
        return {'event': 'set-file-albums', 'file_id': pk, 'removed_from': {album.id: album.name}}

    async def check_for_update(self, *args, **kwargs) -> dict:
        log.debug('async - check_for_update')
        data = {'event': 'message', 'bsclass': 'info', 'delay': '2000', 'message': 'Checking for Update...'}
        await self.send(text_data=json.dumps(data))
        result = await sync_to_async(version_check)()
        log.debug('result: %s', result)
        site_settings = await database_sync_to_async(SiteSettings.objects.settings)()
        if site_settings.latest_version:
            message = f'Update Available: {site_settings.latest_version}'
            bsclass, delay = 'warning', '6000'
        else:
            message = f'{site_settings.site_title} is Up-to-Date.'
            bsclass, delay = 'success', '6000'
        return {'event': 'message', 'bsclass': bsclass, 'delay': delay, 'message': message}


def filter_kwargs(pks: List[int], user_id: int) -> dict:
    # generates kwargs for filter object, filters to user for non admin api requests
    # accepts list of pks, user id int
    # returns kwargs for django model filter()
    kwargs = {'pk__in': pks}
    if not ((user := CustomUser.objects.get(pk=user_id)).is_superuser):
        kwargs['user'] = user
    return kwargs
