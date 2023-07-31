import logging
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from home.tasks import flush_template_cache

logger = logging.getLogger('app')


def health_check(request):
    return JsonResponse({'status': 'up'}, status=200)


@login_required()
@require_http_methods(['POST'])
def flush_cache_view(request):
    logger.debug('flush_cache_view')
    flush_template_cache.delay()
    messages.success(request, 'Cache flush success.')
    return HttpResponse(status=204)


def handler400_view(request, exception):
    logger.debug('handler400_view')
    logger.debug(exception)
    return render(request, 'error/400.html', status=400)


def handler403_view(request, exception):
    logger.debug('handler403_view')
    logger.debug(exception)
    return render(request, 'error/403.html', status=403)


def handler404_view(request, exception):
    logger.debug('handler404_view')
    logger.debug(exception)
    return render(request, 'error/404.html', status=404)


def handler500_view(request):
    logger.debug('handler500_view')
    return render(request, 'error/500.html', status=500)
