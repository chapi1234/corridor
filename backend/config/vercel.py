"""Vercel entrypoint (ASGI).

Vercel's Django detection reads DJANGO_SETTINGS_MODULE from manage.py, which defaults to the
dev settings. This module pins production settings regardless. Render and Docker use
config.asgi instead.
"""

import os

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.prod"

from django.core.asgi import get_asgi_application

application = get_asgi_application()
