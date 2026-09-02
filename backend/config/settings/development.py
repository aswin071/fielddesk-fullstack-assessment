from config.settings.base import *  # noqa: F403
from config.settings.base import env_bool

DEBUG = env_bool("DJANGO_DEBUG", True)

