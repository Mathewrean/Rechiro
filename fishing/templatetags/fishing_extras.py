from django import template
from django.conf import settings
from django.templatetags.static import static
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name='star_rating')
def star_rating(value):
    """Render a numeric rating as HTML stars (e.g. 4 -> ★★★★☆)."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 0
    full = int(round(value))
    full = max(0, min(5, full))
    empty = 5 - full
    return mark_safe(('★' * full) + ('☆' * empty))


@register.simple_tag
def absolute_static(path):
    """Build an absolute URL for a static asset using SITE_URL."""
    site = getattr(settings, 'SITE_URL', 'https://rechiro.onrender.com').rstrip('/')
    return mark_safe(site + static(path))


@register.simple_tag
def fish_image_url(fish):
    """Return an absolute URL for a fish listing image, falling back to a placeholder."""
    if fish and fish.has_image_file and getattr(fish, 'image', None):
        site = getattr(settings, 'SITE_URL', 'https://rechiro.onrender.com').rstrip('/')
        try:
            return mark_safe(site + fish.image.url)
        except Exception:
            pass
    return absolute_static('branding/rechiro-512.png')


@register.simple_tag
def star_widget(rating=0):
    """Render a read-only star widget for a given rating (0-5)."""
    try:
        rating = float(rating)
    except (TypeError, ValueError):
        rating = 0
    rating = max(0, min(5, rating))
    filled = int(round(rating))
    stars_html = []
    for i in range(1, 6):
        if i <= filled:
            stars_html.append('<i class="fas fa-star text-yellow-400"></i>')
        else:
            stars_html.append('<i class="far fa-star text-yellow-300"></i>')
    return mark_safe(''.join(stars_html))
