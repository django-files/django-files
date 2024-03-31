from django.core.exceptions import ObjectDoesNotExist

from home.models import Files


def process_avatar(user):
    avatar_url = None
    if user.user_avatar_choice == "DC" and user.discord:
        avatar_url = f'https://cdn.discordapp.com/avatars/' \
                f'{user.discord.id}/{user.discord.avatar}.png'
    elif user.user_avatar_choice == "GH" and user.github:
        avatar_url = user.github.avatar
    elif user.user_avatar_choice == "DF":
        try:
            avatar = Files.objects.get(user=user, avatar=True)
            avatar_url = avatar.get_meta_static_url()
        except ObjectDoesNotExist:
            pass
    if not avatar_url or avatar_url == "":
        # if avatar_url fails to be set for any reason fallback to a safe default
        avatar_url = '/static/images/default_avatar.png'
    return avatar_url
