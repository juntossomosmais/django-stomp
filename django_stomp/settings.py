import ssl
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

STOMP_USE_SSL = eval_str_as_boolean(getattr(django_settings, "STOMP_USE_SSL", "False"))
DEFAULT_STOMP_SSL_VERSION = getattr(django_settings, "DEFAULT_STOMP_SSL_VERSION", ssl.PROTOCOL_TLS_CLIENT)
