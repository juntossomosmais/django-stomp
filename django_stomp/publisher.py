from typing import Optional

from django.conf import settings
from django_stomp.helpers import clean_dict_with_falsy_or_strange_values
from django_stomp.helpers import eval_str_as_boolean
from django_stomp.services import producer
from django_stomp.services.producer import Publisher


def build_publisher(client_id: Optional[str] = None) -> Publisher:
    required_params = {
        "host": settings.STOMP_SERVER_HOST,
        "port": int(settings.STOMP_SERVER_PORT),
        "username": settings.STOMP_SERVER_USER,
        "password": settings.STOMP_SERVER_PASSWORD,
    }

    extra_params = {"use_ssl": eval_str_as_boolean(settings.STOMP_USE_SSL), "client_id": client_id}

    connection_params = clean_dict_with_falsy_or_strange_values({**required_params, **extra_params})

    return producer.build_publisher(**connection_params)
