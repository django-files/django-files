import os
from django.conf import settings
from django.db.models.signals import post_delete
from django.dispatch import receiver
from oauth.models import UserBackups


@receiver(post_delete, sender=UserBackups)
def delete_backup_signal(sender, instance, **kwargs):
    # instance.file.delete(True)
    return os.remove(os.path.join(settings.MEDIA_ROOT, instance.filename))
