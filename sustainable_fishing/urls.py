from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import RedirectView
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(url='/fishing/home/', permanent=False), name='home'),
    path('users/', include('users.urls')),
    path('fishing/', include('fishing.urls')),
    # Content app removed - e-commerce only
]

if getattr(settings, "ALLAUTH_INSTALLED", False):
    urlpatterns.append(path('accounts/', include('allauth.urls')))

# Media files
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {
        'document_root': settings.MEDIA_ROOT,
    }),
]

# Static files
urlpatterns += [
    re_path(r'^static/(?P<path>.*)$', serve, {
        'document_root': settings.STATIC_ROOT,
    }),
]
