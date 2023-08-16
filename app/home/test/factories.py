import factory
import factory.fuzzy

from .. import models
from ...oauth.models import CustomUser


class UserFactory(factory.Factory):

    class Meta:
        model = CustomUser


class FileFactory(factory.Factory):

    class Meta:
        model = models.Files

    user = factory.SubFactory(UserFactory)
