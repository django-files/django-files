import json
import logging
# from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from typing import Optional

from home.models import Files

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
        log.debug(self.scope['client'])
        log.debug(self.scope['user'])
        if self.scope['client'][1] is None:
            return log.debug('client 1 is None')
        await self.send(text_data=event['text'])

    async def websocket_receive(self, event):
        log.debug('websocket_receive')
        log.debug(event)
        data = await self.process_message(event)
        await self.send(text_data=json.dumps(data))

    async def process_message(self, event) -> Optional[dict]:
        data = {'user_id': self.scope['user'].id}
        log.debug('process_message: user_id: %s', data['user_id'])
        log.debug(event)
        data.update(json.loads(event['text']))
        log.debug('data: %s', data)
        method_name = data.pop('method').replace('-', '_')
        log.debug('method_name: %s', method_name)
        method = getattr(self, method_name)
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
            if user_id and file[0].user.id != user_id:
                return self._error('File owned by another user.', **kwargs)
            file[0].delete()
            # return self._success('File Deleted.', **kwargs)
            return {}
        return self._error('File not found.', **kwargs)

    def toggle_private_file(self, *, user_id: int = None, pk: int = None, **kwargs) -> dict:
        """
        :param user_id: Integer - self.scope['user'].id - User ID
        :param pk: Integer - File ID
        :param expr: String - File Expire String
        :return: Dictionary - With Key: 'success': bool
        """
        log.debug('toggle_private_file')
        log.debug('user_id: %s', user_id)
        log.debug('pk: %s', pk)
        print("HITTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT")
        if file := Files.objects.filter(pk=pk):
            if user_id and file[0].user.id != user_id:
                return self._error('File owned by another user.', **kwargs)
            file[0].private = not file[0].private
            file[0].save()
            # return self._success('File Expire Updated.', **kwargs)
            return {'private': file[0].private, 'event': 'toggle-private-file', 'pk': file[0].id }
        return self._error('File not found.', **kwargs)
