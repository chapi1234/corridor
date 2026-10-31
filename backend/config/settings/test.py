from .base import *

SECRET_KEY = "test-secret-key"
TOMTOM_API_KEY = "test-key"
REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_THROTTLE_CLASSES": []}
