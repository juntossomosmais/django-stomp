import logging
from typing import Dict
from typing import Optional

from django.conf import settings
from django_stomp.helpers import clean_dict_with_falsy_or_strange_values
from django_stomp.helpers import eval_as_int_otherwise_none
from django_stomp.helpers import eval_str_as_boolean
from django_stomp.services import consumer
from django_stomp.services import producer
from django_stomp.services.consumer import Listener
from django_stomp.services.producer import Publisher

logger = logging.getLogger("django_stomp")


def build_publisher(client_id: Optional[str] = None) -> Publisher:
    connection_params = _build_connection_parameter(client_id)

    return producer.build_publisher(**connection_params)


def build_listener(
    destination_name: str,
    durable_topic_subscription: bool = False,
    is_testing: bool = False,
    client_id: Optional[str] = None,
    routing_key: Optional[str] = None,
) -> Listener:
    connection_params = _build_connection_parameter(client_id)

    return consumer.build_listener(
        destination_name,
        durable_topic_subscription=durable_topic_subscription,
        is_testing=is_testing,
        routing_key=routing_key,
        **connection_params,
    )


def _build_connection_parameter(client_id: Optional[str] = None) -> Dict:
    stomp_server_port = eval_as_int_otherwise_none(getattr(settings, "STOMP_SERVER_PORT", None))
    stomp_server_standby_port = eval_as_int_otherwise_none(getattr(settings, "STOMP_SERVER_STANDBY_PORT", None))
    outgoing_heartbeat = eval_as_int_otherwise_none(getattr(settings, "STOMP_OUTGOING_HEARTBIT", None))
    incoming_heartbeat = eval_as_int_otherwise_none(getattr(settings, "STOMP_INCOMING_HEARTBIT", None))
    subscription_id = getattr(settings, "STOMP_SUBSCRIPTION_ID", None)

    required_params = {
        "host": getattr(settings, "STOMP_SERVER_HOST", None),
        "port": stomp_server_port,
        "hostStandby": getattr(settings, "STOMP_SERVER_STANDBY_HOST", None),
        "portStandby": stomp_server_standby_port,
        "outgoingHeartbeat": outgoing_heartbeat,
        "incomingHeartbeat": incoming_heartbeat,
        "subscriptionId": subscription_id,
        "vhost": getattr(settings, "STOMP_SERVER_VHOST", None),
    }

    logger.debug("Server details connection: %s", required_params)

    credentials = {
        "username": getattr(settings, "STOMP_SERVER_USER", None),
        "password": getattr(settings, "STOMP_SERVER_PASSWORD", None),
    }

    extra_params = {"use_ssl": eval_str_as_boolean(settings.STOMP_USE_SSL), "client_id": client_id}

    logger.debug("Extra params: %s", extra_params)

    return clean_dict_with_falsy_or_strange_values({**required_params, **extra_params, **credentials})
