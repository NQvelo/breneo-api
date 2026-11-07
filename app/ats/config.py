"""Runtime settings for the ATS feature.

Values are read from Django settings when the project is configured, and from
the environment otherwise. This matches ``mysite.settings`` (os.getenv) and
keeps the package usable in unit tests that do not boot Django.
"""

from __future__ import annotations

import os


def get_setting(name: str, default=None):
    try:
        from django.conf import settings

        if settings.configured and hasattr(settings, name):
            value = getattr(settings, name)
            if value is not None and value != "":
                return value
    except Exception:
        pass
    env_value = os.environ.get(name)
    if env_value not in (None, ""):
        return env_value
    return default


def get_int_setting(name: str, default: int) -> int:
    raw = get_setting(name, default)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default
