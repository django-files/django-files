from django.db import models


class DiscordWebhooksManager(models.Manager):
    def get_request(self, request, **kwargs):
        return self.filter(owner=request.user, **kwargs)


class UserInvitesManager(models.Manager):
    def get_invite(self, invite, **kwargs):
        if invite:
            if invite := self.filter(invite=invite, **kwargs):
                return invite[0]
        return None
