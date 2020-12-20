"""
Django-stomp variables extracted from the django project that's using it.
"""

import uuid

from django_stomp.helpers import build_final_client_id
from django_stomp.settings.default_values import STOMP_CORRELATION_ID_REQUIRED_DEFAULT
from django_stomp.settings.default_values import STOMP_DURABLE_TOPIC_SUBSCRIPTION_DEFAULT
from django_stomp.settings.default_values import STOMP_INCOMING_HEARTBEAT_DEFAULT
from django_stomp.settings.default_values import STOMP_LISTENER_CLIENT_ID_DEFAULT
from django_stomp.settings.default_values import STOMP_OUTGOING_HEARTBEAT_DEFAULT
from django_stomp.settings.default_values import STOMP_PROCESS_MSG_ON_BACKGROUND_DEFAULT
from django_stomp.settings.default_values import STOMP_SSL_VERSION_DEFAULT
from django_stomp.settings.default_values import STOMP_USE_SSL_DEFAULT
from django_stomp.settings.support import get_config_as_bool_or_default
from django_stomp.settings.support import get_config_or_default
from django_stomp.settings.support import get_config_or_default_any
from django_stomp.settings.support import get_config_or_exception
from django_stomp.settings.types import AcknowledgementType
from django_stomp.settings.types import BrokerType

# operation settings
DURABLE_TOPIC_SUBSCRIPTION = get_config_as_bool_or_default(
    "STOMP_DURABLE_TOPIC_SUBSCRIPTION", STOMP_DURABLE_TOPIC_SUBSCRIPTION_DEFAULT
)
LISTENER_CLIENT_ID = get_config_or_default_any("STOMP_LISTENER_CLIENT_ID", STOMP_LISTENER_CLIENT_ID_DEFAULT)
LISTENER_CLIENT_ID = build_final_client_id(LISTENER_CLIENT_ID, DURABLE_TOPIC_SUBSCRIPTION)  # this one goes ahead

IS_CORRELATION_ID_REQUIRED = get_config_as_bool_or_default(
    "STOMP_CORRELATION_ID_REQUIRED", STOMP_CORRELATION_ID_REQUIRED_DEFAULT
)
SHOULD_PROCESS_MSG_ON_BACKGROUND = get_config_as_bool_or_default(
    "STOMP_PROCESS_MSG_ON_BACKGROUND", STOMP_PROCESS_MSG_ON_BACKGROUND_DEFAULT
)
DEFAULT_PUBLISHER_NAME = get_config_or_default("STOMP_PUBLISHER_NAME_DEFAULT", "django-stomp-another-target")

BROKER_TYPE: BrokerType = get_config_or_default_any("STOMP_BROKER_TYPE", BrokerType.RABBITMQ)
ACK_TYPE = AcknowledgementType.CLIENT

# connection settings
STOMP_SERVER_USER = get_config_or_exception("STOMP_SERVER_USER")
STOMP_SERVER_PASSWORD = get_config_or_exception("STOMP_SERVER_PASSWORD")

STOMP_SERVER_HOST = get_config_or_exception("STOMP_SERVER_HOST")
STOMP_SERVER_PORT = int(get_config_or_exception("STOMP_SERVER_PORT"))

STOMP_SERVER_STANDBY_HOST: str = get_config_or_default_any("STOMP_SERVER_STANDBY_HOST", None)
STOMP_SERVER_STANDBY_PORT = get_config_or_default_any("STOMP_SERVER_STANDBY_PORT", None)

if STOMP_SERVER_STANDBY_PORT is not None:
    STOMP_SERVER_STANDBY_PORT = int(STOMP_SERVER_STANDBY_PORT)

# wait_to_connect = int(get_config_or_default("STOMP_WAIT_TO_CONNECT", STOMP_WAIT_TO_CONNECT_DEFAULT))
OUTGOING_HEARTBEAT = int(get_config_or_default("STOMP_OUTGOING_HEARTBEAT", STOMP_OUTGOING_HEARTBEAT_DEFAULT))
INCOMING_HEARTBEAT = int(get_config_or_default("STOMP_INCOMING_HEARTBEAT", STOMP_INCOMING_HEARTBEAT_DEFAULT))

# TODO: review client_id
SUBSCRIPTION_ID: str = get_config_or_default("STOMP_SUBSCRIPTION_ID", str(uuid.uuid4()))
SERVER_VHOST = get_config_or_default_any("STOMP_SERVER_VHOST", None)

USE_SSL = get_config_as_bool_or_default("STOMP_USE_SSL", STOMP_USE_SSL_DEFAULT)
SSL_VERSION = int(get_config_or_default("STOMP_SSL_VERSION", STOMP_SSL_VERSION_DEFAULT))
