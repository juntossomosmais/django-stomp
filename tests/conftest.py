import os
import uuid

from django.conf import settings


def pytest_assertrepr_compare(config, op, left, right):
    """
    More details at: https://stackoverflow.com/a/50625086/3899136
    """
    if op in ("==", "!="):
        return ["{0} {1} {2}".format(left, op, right)]


def pytest_configure():
    settings.configure(
        INSTALLED_APPS=["django_stomp", "tests.support"],
        STOMP_SERVER_HOST=os.getenv("STOMP_SERVER_HOST"),
        STOMP_SERVER_PORT=os.getenv("STOMP_SERVER_PORT"),
        STOMP_SERVER_STANDBY_HOST=os.getenv("STOMP_SERVER_STANDBY_HOST"),
        STOMP_SERVER_STANDBY_PORT=os.getenv("STOMP_SERVER_STANDBY_PORT"),
        STOMP_SERVER_USER=os.getenv("STOMP_SERVER_USER"),
        STOMP_SERVER_PASSWORD=os.getenv("STOMP_SERVER_PASSWORD"),
        STOMP_USE_SSL=os.getenv("STOMP_USE_SSL"),
        STOMP_LISTENER_CLIENT_ID=os.getenv("STOMP_LISTENER_CLIENT_ID"),
        STOMP_CORRELATION_ID_REQUIRED=os.getenv("STOMP_CORRELATION_ID_REQUIRED"),
        STOMP_PROCESS_MSG_ON_BACKGROUND=os.getenv("STOMP_PROCESS_MSG_ON_BACKGROUND"),
        STOMP_OUTGOING_HEARTBEAT=os.getenv("STOMP_OUTGOING_HEARTBEAT"),
        STOMP_INCOMING_HEARTBEAT=os.getenv("STOMP_INCOMING_HEARTBEAT"),
        DATABASES={
            "default": {
                "ENGINE": os.getenv("DB_ENGINE", "django.db.backends.sqlite3"),
                "NAME": os.getenv("DB_DATABASE", f"test_db-{uuid.uuid4()}"),
                "USER": os.getenv("DB_USER"),
                "HOST": os.getenv("DB_HOST"),
                "PORT": os.getenv("DB_PORT"),
                "PASSWORD": os.getenv("DB_PASSWORD"),
                "TEST": {"NAME": os.getenv("DB_DATABASE", f"test_db-{uuid.uuid4()}")},
            }
        },
    )
