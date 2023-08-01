import httpx
import logging
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, reverse
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from oauth.models import CustomUser
from .models import Files, Webhooks
from .tasks import process_file_upload

logger = logging.getLogger('app')


@login_required
def home_view(request):
    """
    View  /
    """
    logger.debug('%s - home_view: is_secure: %s', request.method, request.is_secure())
    context = {'files': Files.objects.get_request(request)}
    return render(request, 'home.html', context)


@login_required
def settings_view(request):
    """
    View  /settings/
    """
    logger.debug('settings_view')
    context = {'webhooks': Webhooks.objects.filter(owner=request.user)}
    return render(request, 'settings.html', context)


@login_required
@csrf_exempt
def files_view(request):
    """
    View  /files/
    """
    if request.method in ['GET', 'HEAD']:
        return render(request, 'files.html')
    logger.debug(request.headers)
    logger.debug(request.POST)
    logger.debug(request.FILES)
    file = Files.objects.create(
        file=request.FILES.get('file'),
        user=request.user,
        info=request.POST.get('info', ''),
    )
    if not file:
        return HttpResponse(status=400)
    process_file_upload.delay(file.pk)
    return HttpResponse()


@csrf_exempt
@require_http_methods(['POST'])
def upload_view(request):
    """
    View  /upload/ and /api/upload
    """
    logger.debug(request.headers)
    logger.debug(request.POST)
    logger.debug(request.FILES)
    try:
        authorization = request.headers.get('Authorization') or request.headers.get('Token')
        if not authorization:
            return JsonResponse({'error': 'Missing Authorization'}, status=401)

        user = CustomUser.objects.get(authorization=authorization)
        if not user:
            return JsonResponse({'error': 'Invalid Authorization'}, status=401)

        file = Files.objects.create(
            file=request.FILES.get('file'),
            user=user,
            info=request.POST.get('info', ''),
        )
        if not file:
            return JsonResponse({'error': 'File Not Created'}, status=400)
        process_file_upload.delay(file.pk)
        data = {
            'files': [file.get_url()],
            'url': file.get_url(),
            'name': file.name,
            'size': file.size,
        }
        return JsonResponse(data)
    except Exception as error:
        logger.exception(error)
        return JsonResponse({'error': str(error)}, status=500)


@login_required
@csrf_exempt
@require_http_methods(['POST'])
def delete_file_ajax(request, pk):
    """
    View  /ajax/delete/file/<int:pk>/
    TODO: Implement into /files/ using DELETE method
    """
    logger.debug('del_hook_view_a: %s', pk)
    file = Files.objects.get(pk=pk)
    if file.user != request.user:
        return HttpResponse(status=401)
    logger.debug(file)
    file.delete()
    return HttpResponse(status=204)


@login_required
@csrf_exempt
@require_http_methods(['POST'])
def delete_hook_ajax(request, pk):
    """
    View  /ajax/delete/hook/<int:pk>/
    """
    logger.debug('delete_hook_ajax: %s', pk)
    webhook = Webhooks.objects.get(pk=pk)
    if webhook.owner != request.user:
        return HttpResponse(status=401)
    logger.debug(webhook)
    webhook.delete()
    return HttpResponse(status=204)


@login_required
@require_http_methods(['GET'])
def gen_sharex(request):
    """
    View  /gen/sharex/
    """
    logger.debug('gen_sharex')
    data = {
        'Version': '14.1.0',
        'Name': f'Django Files - {request.get_host()} - File',
        'DestinationType': 'ImageUploader, FileUploader',
        'RequestMethod': 'POST',
        'RequestURL': request.build_absolute_uri(reverse('home:upload')),
        'Headers': {
            'Authorization': request.user.authorization,
        },
        'Body': 'MultipartFormData',
        'FileFormName': 'file',
        'URL': '{json:url}',
        'ErrorMessage': '{json:error}'
    }
    # Create the HttpResponse object with the appropriate headers.
    filename = f'{request.get_host()} - Files.sxcu'
    response = JsonResponse(data, json_dumps_params={'indent': 4})
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_http_methods(['GET'])
def gen_flameshot(request):
    """
    View  /gen/flameshot/
    """
    context = {'site_url': settings.SITE_URL, 'token': request.user.authorization}
    message = render_to_string('scripts/flameshot.sh', context)
    logger.debug(message)
    response = HttpResponse(message)
    response['Content-Disposition'] = f'attachment; filename="flameshot.sh"'
    return response


def google_verify(request: HttpRequest) -> bool:
    if 'g_verified' in request.session and request.session['g_verified']:
        return True
    try:
        url = 'https://www.google.com/recaptcha/api/siteverify'
        data = {
            'secret': settings.GOOGLE_SITE_SECRET,
            'response': request.POST['g-recaptcha-response']
        }
        r = httpx.post(url, data=data, timeout=10)
        if r.is_success:
            if r.json()['success']:
                request.session['g_verified'] = True
                return True
        return False
    except Exception as error:
        logger.exception(error)
        return False
