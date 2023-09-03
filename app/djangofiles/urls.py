from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls import include
from django.contrib import admin
from django.urls import path

from djangofiles import views

handler400 = 'djangofiles.views.handler400_view'
handler403 = 'djangofiles.views.handler403_view'
handler404 = 'djangofiles.views.handler404_view'
handler500 = 'djangofiles.views.handler500_view'

urlpatterns = [
    path('', include('home.urls')),
    path('api/', include('api.urls')),
    path('oauth/', include('oauth.urls')),
    path('admin/', admin.site.urls),
    path('flush-cache/', views.flush_cache_view, name='flush_cache'),
    path('app-health-check/', views.health_check, name='health_check'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [path('debug/', include(debug_toolbar.urls))] + urlpatterns
