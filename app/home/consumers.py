import json
import logging
from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from io import BytesIO
from typing import Optional

from home.models import Files
from home.util.file import process_file
from oauth.models import CustomUser

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
            # return await self.send(text_data='pong')
            return log.debug('ping->pong')

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
        response = await database_sync_to_async(method)(**data)
        log.debug(response)
        return response or {}

    @staticmethod
    def _error(message, **kwargs) -> dict:
        response = {'success': False, 'bsClass': 'danger', 'message': message}
        response.update(**kwargs)
        return response

    # @staticmethod
    # def _success(data: Optional[Union[str, dict]] = None, **kwargs) -> dict:
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
        return {'user': user[0].username}

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
        # return self._error('Not Implemented.', **kwargs)
        # return self._success(f'File Created: {file.pk}')

    def delete_file(self, *, user_id: int = None, pk: int = None, **kwargs) -> dict:
        """
        :param user_id: Integer - self.scope['user'].id - User ID
        :param pk: Integer - File ID
        :return: Dictionary - With Key: 'success': bool
        """
        log.debug('delete_file')
        log.debug('user_id: %s', user_id)
        log.debug('pk: %s', pk)
        if file := Files.objects.filter(pk=pk):
            if file[0].user.id != user_id:
                return self._error('File owned by another user.', **kwargs)
            file[0].delete()
        return self._error('File not found.', **kwargs)

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
            file[0].save()
            # return self._success('File Expire Updated.', **kwargs)
            return {'private': file[0].private, 'event': 'toggle-private-file', 'pk': file[0].id,
                    'file_name': file[0].name}
        return self._error('File not found.', **kwargs)

    def set_expr_file(self, *, user_id: int = None, pk: int = None, expr: str = None, **kwargs) -> dict:
        """
        :param user_id: Integer - self.scope['user'].id - User ID
        :param pk: Integer - File ID
        :param expr: String - File Expire String
        :return: Dictionary - With Key: 'success': bool
        """
        log.debug('set_expr_file')
        log.debug('user_id: %s', user_id)
        log.debug('pk: %s', pk)
        if file := Files.objects.filter(pk=pk):
            if user_id and file[0].user.id != user_id:
                return self._error('File owned by another user.', **kwargs)
            file[0].expr = expr or ""
            file[0].save()
            # return self._success('File Expire Updated.', **kwargs)
            return {'expr': file[0].expr, 'event': 'set-expr-file', 'pk': file[0].id,
                    'file_name': file[0].name}
        return self._error('File not found.', **kwargs)

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
            print(password)
            file[0].password = password or ""
            file[0].save()
            # return self._success('File Expire Updated.', **kwargs)
            return {'password': bool(file[0].password), 'event': 'set-password-file', 'pk': file[0].id,
                    'file_name': file[0].name}
        return self._error('File not found.', **kwargs)
