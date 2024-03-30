from multiprocessing import process
from home.models import Files


def process_avatar(user):
    if user.user_avatar_choice == "DC":
        avatar_url = f'https://cdn.discordapp.com/avatars/' \
                f'{user.discord.id}/{user.discord.avatar}.png'
    elif user.user_avatar_choice == "GH":
        avatar_url = user.github.avatar
    elif user.user_avatar_choice == "DF":
        avatar = Files.objects.filter(user=user, avatar=True)
        avatar_url = avatar[0].get_meta_static_url()
    else:
        # we need a fallback image to return if all condtitions fail
        avatar_url = ''
    return avatar_url

def current_user_avatar_url_processor(request):
    return {"current_user_avatar_url": process_avatar(request.user)}

def current_file_avatar_url_processor(request):
    if not (filename := request.resolver_match.kwargs['filename']):
        return {}
    file_user = Files.objects.get(name=filename).user
    return {"file_avatar_url": process_avatar(file_user)}