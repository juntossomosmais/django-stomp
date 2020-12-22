"""
Module with all the settings used to run django-stomp.
"""

import logging
import ssl
from typing import Any
from typing import Callable
from typing import Optional

from django.conf import settings as django_settings

from django_stomp.exceptions import DjangoStompImproperlyConfigured
from django_stomp.helpers import eval_as_int_if_provided_value_is_not_none_otherwise_none

logger = logging.getLogger(__name__)


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

# stomp default settings
STOMP_DURABLE_TOPIC_SUBSCRIPTION_DEFAULT = "False"
STOMP_LISTENER_CLIENT_ID_DEFAULT = None
STOMP_CORRELATION_ID_REQUIRED_DEFAULT = "True"
STOMP_PROCESS_MSG_ON_BACKGROUND_DEFAULT = "True"
STOMP_PUBLISHER_NAME_DEFAULT = "django-stomp-another-target"

# connection default settings
STOMP_WAIT_TO_CONNECT_DEFAULT = "10"
STOMP_OUTGOING_HEARTBEAT_DEFAULT = "10000"
STOMP_INCOMING_HEARTBEAT_DEFAULT = "10000"
STOMP_USE_SSL_DEFAULT = "False"
STOMP_SSL_VERSION_DEFAULT = int(ssl.PROTOCOL_TLS)
