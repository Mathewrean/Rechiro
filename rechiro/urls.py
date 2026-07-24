import importlib.util
from pathlib import Path

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.http import FileResponse, Http404, JsonResponse
from django.urls import path, include
from django.views.generic import RedirectView

from fishing.views import mpesa_callback, mpesa_b2c_result, mpesa_b2c_timeout


def health_check(request):
    from django.conf import settings
    from django.db import connection
    db_ok = True
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
    except Exception as e:
        db_ok = False
    
    return JsonResponse({
        "status": "ok", 
        "allowed_hosts": list(settings.ALLOWED_HOSTS),
        "debug": settings.DEBUG,
        "db_ok": db_ok,
        "media_root": settings.MEDIA_ROOT,
        "static_root": settings.STATIC_ROOT,
    })


def service_worker_view(request):
    sw_path = Path(settings.BASE_DIR) / "static" / "service-worker.js"
    try:
        return FileResponse(open(sw_path, "rb"), content_type="application/javascript")
    except FileNotFoundError:
        raise Http404()

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/fishing/home/', permanent=False), name='home'),
    path('health/', health_check, name='health'),
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
# In production, whitenoise handles static files. Media files are served via white noise finders.
