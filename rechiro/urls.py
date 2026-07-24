import importlib.util
from pathlib import Path

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.contrib.staticfiles.views import serve as static_serve
from django.http import FileResponse, Http404
from django.views.static import serve as media_serve
from django.urls import path, include, re_path
from django.views.generic import RedirectView

from fishing.views import mpesa_callback, mpesa_b2c_result, mpesa_b2c_timeout


def service_worker_view(request):
    sw_path = Path(settings.BASE_DIR) / "static" / "service-worker.js"
    try:
        return FileResponse(open(sw_path, "rb"), content_type="application/javascript")
    except FileNotFoundError:
        raise Http404()

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/fishing/home/', permanent=False), name='home'),
    path('service-worker.js', service_worker_view),
    path('choose-role/', RedirectView.as_view(url='/users/choose-role/', permanent=False), name='choose_role_root'),
    path('users/', include('users.urls')),
    path('api/mpesa/callback/', mpesa_callback, name='api_mpesa_callback'),
    path('api/mpesa/b2c/result/', mpesa_b2c_result, name='api_mpesa_b2c_result'),
    path('api/mpesa/b2c/timeout/', mpesa_b2c_timeout, name='api_mpesa_b2c_timeout'),
    path('fishing/', include('fishing.urls')),
    # Content app removed - e-commerce only
]

if getattr(settings, "ALLAUTH_INSTALLED", False):
    urlpatterns.append(path('accounts/', include('allauth.urls')))

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += staticfiles_urlpatterns()
else:
    if importlib.util.find_spec("whitenoise") is None:
        urlpatterns += [
            re_path(r"^static/(?P<path>.*)$", static_serve, {"insecure": True}),
        ]
    media_url_prefix = settings.MEDIA_URL or ""
    media_url_prefix = media_url_prefix.lstrip("/")
    media_url_prefix = media_url_prefix.rstrip("/")
    if media_url_prefix:
        media_pattern = rf"^{media_url_prefix}/(?P<path>.*)$"
    else:
        media_pattern = r"^(?P<path>.*)$"
    urlpatterns += [
        re_path(media_pattern, media_serve, {"document_root": settings.MEDIA_ROOT}),
    ]
