import importlib.util
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.contrib.staticfiles.views import serve as static_serve
from django.urls import path, include, re_path
from django.views.generic import RedirectView
from fishing.views import mpesa_callback

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/fishing/home/', permanent=False), name='home'),
    path('choose-role/', RedirectView.as_view(url='/users/choose-role/', permanent=False), name='choose_role_root'),
    path('users/', include('users.urls')),
    path('api/mpesa/callback/', mpesa_callback, name='api_mpesa_callback'),
    path('fishing/', include('fishing.urls')),
    # Content app removed - e-commerce only
]

if getattr(settings, "ALLAUTH_INSTALLED", False):
    urlpatterns.append(path('accounts/', include('allauth.urls')))

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += staticfiles_urlpatterns()
elif importlib.util.find_spec("whitenoise") is None:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += [
        re_path(r"^static/(?P<path>.*)$", static_serve, {"insecure": True}),
    ]
