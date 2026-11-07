from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def breneo_logo_dark_url():
    return getattr(settings, "BRENEO_LOGO_DARK_URL", "")
