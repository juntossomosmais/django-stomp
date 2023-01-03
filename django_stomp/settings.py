import os
from typing import Any
from typing import Callable
from typing import Optional

from django.conf import settings as django_settings

from django_stomp.exceptions import DjangoStompImproperlyConfigured
from django_stomp.helpers import eval_as_int_if_provided_value_is_not_none_otherwise_none
from django_stomp.helpers import eval_str_as_boolean


def eval_settings_otherwise_raise_exception(
    settings_name: str, evaluation_callback: Callable, default_value: Optional[Any] = None
):
    try:
        return evaluation_callback(getattr(django_settings, settings_name, default_value))
    except Exception:
        raise DjangoStompImproperlyConfigured(f"The defined {settings_name} is not valid!")


STOMP_PROCESS_MSG_WORKERS = eval_settings_otherwise_raise_exception(
    "STOMP_PROCESS_MSG_WORKERS", eval_as_int_if_provided_value_is_not_none_otherwise_none
)

STOMP_SERVER_HOST = getattr(django_settings, "STOMP_SERVER_HOST", "127.0.0.1")
STOMP_SERVER_PORT = eval_as_int_if_provided_value_is_not_none_otherwise_none(
    getattr(django_settings, "STOMP_SERVER_PORT", 61613)
)
STOMP_USE_SSL = eval_str_as_boolean(os.getenv("STOMP_USE_SSL"))
STOMP_HOST_AND_PORTS = os.getenv("STOMP_HOST_AND_PORTS", [(STOMP_SERVER_HOST, STOMP_SERVER_PORT)])
DEFAULT_SSL_VERSION = os.getenv("DEFAULT_SSL_VERSION")
DEFAULT_STOMP_KEY_FILE = os.getenv("DEFAULT_STOMP_KEY_FILE")
DEFAULT_STOMP_CERT_FILE = os.getenv("DEFAULT_STOMP_CERT_FILE")
DEFAULT_STOMP_CA_CERTS = os.getenv("DEFAULT_STOMP_CA_CERTS")
DEFAULT_STOMP_CERT_VALIDATOR = os.getenv("DEFAULT_STOMP_CERT_VALIDATOR")
DEFAULT_STOMP_SSL_VERSION = os.getenv("DEFAULT_STOMP_SSL_VERSION")
DEFAULT_STOMP_SSL_PASSWORD = os.getenv("DEFAULT_STOMP_SSL_PASSWORD")
