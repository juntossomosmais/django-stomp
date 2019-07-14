from typing import Dict
from typing import Optional

from django.conf import settings
from django_stomp.helpers import clean_dict_with_falsy_or_strange_values
from django_stomp.helpers import eval_str_as_boolean
from django_stomp.services import consumer
from django_stomp.services import producer
from django_stomp.services.consumer import Listener
from django_stomp.services.producer import Publisher


def build_publisher(client_id: Optional[str] = None) -> Publisher:
    connection_params = _build_connection_parameter(client_id)

    return producer.build_publisher(**connection_params)


def build_listener(
    destination_name, client_id: Optional[str] = None, durable_topic_subscription=False, is_testing=False
) -> Listener:
    connection_params = _build_connection_parameter(client_id)

    return consumer.build_listener(
        destination_name,
        durable_topic_subscription=durable_topic_subscription,
        is_testing=is_testing,
        **connection_params,
    )


def _build_connection_parameter(client_id: Optional[str] = None) -> Dict:
    required_params = {
        "host": settings.STOMP_SERVER_HOST,
        "port": int(settings.STOMP_SERVER_PORT),
        "username": settings.STOMP_SERVER_USER,
        "password": settings.STOMP_SERVER_PASSWORD,
    }

    extra_params = {"use_ssl": eval_str_as_boolean(settings.STOMP_USE_SSL), "client_id": client_id}

    return clean_dict_with_falsy_or_strange_values({**required_params, **extra_params})
