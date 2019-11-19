import os
from logging import Formatter

from django.conf import settings


def pytest_assertrepr_compare(config, op, left, right):
    """
    More details at: https://stackoverflow.com/a/50625086/3899136
    """
    if op in ("==", "!="):
        return ["{0} {1} {2}".format(left, op, right)]


def pytest_configure():
    settings.configure(
        INSTALLED_APPS=["django_stomp"],
        STOMP_SERVER_HOST=os.getenv("STOMP_SERVER_HOST"),
        STOMP_SERVER_PORT=os.getenv("STOMP_SERVER_PORT"),
        STOMP_SERVER_STANDBY_HOST=os.getenv("STOMP_SERVER_STANDBY_HOST"),
        STOMP_SERVER_STANDBY_PORT=os.getenv("STOMP_SERVER_STANDBY_PORT"),
        STOMP_SERVER_USER=os.getenv("STOMP_SERVER_USER"),
        STOMP_SERVER_PASSWORD=os.getenv("STOMP_SERVER_PASSWORD"),
        STOMP_USE_SSL=os.getenv("STOMP_USE_SSL"),
        STOMP_LISTENER_CLIENT_ID=os.getenv("STOMP_LISTENER_CLIENT_ID"),
        LOGGING={
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {"()": Formatter, "format": "%(asctime)s - level=%(levelname)s - %(name)s - %(message)s"}
            },
            "handlers": {
                "console": {"class": "logging.StreamHandler", "formatter": os.getenv("LOG_FORMATTER", "standard")}
            },
            "loggers": {
                "": {"level": os.getenv("ROOT_LOG_LEVEL", "INFO"), "handlers": ["console"]},
                "django": {"level": os.getenv("DJANGO_LOG_LEVEL", "INFO"), "propagate": False, "handlers": ["console"]},
                "django.request": {
                    "level": os.getenv("DJANGO_REQUEST_LOG_LEVEL", "INFO"),
                    "handlers": ["console"],
                    "propagate": False,
                },
                "django.db.backends": {
                    "level": os.getenv("DJANGO_DB_BACKENDS_LOG_LEVEL", "INFO"),
                    "propagate": False,
                    "handlers": ["console"],
                },
                "stomp.py": {
                    "level": os.getenv("STOMP_LOG_LEVEL", "DEBUG"),
                    "handlers": ["console"],
                    "propagate": False,
                },
                "django_stomp": {
                    "level": os.getenv("DJANGO_STOMP_LEVEL", "DEBUG"),
                    "handlers": ["console"],
                    "propagate": False,
                },
            },
        },
    )
