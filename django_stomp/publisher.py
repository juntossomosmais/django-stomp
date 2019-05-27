import uuid
from typing import Optional

from django.conf import settings
from django_stomp.services import producer
from django_stomp.services.producer import Publisher


def build_publisher(client_id: Optional[str] = None) -> Publisher:
    connection_params = {
        "use_ssl": settings.STOMP_USE_SSL,
        "host": settings.STOMP_SERVER_HOST,
        "port": int(settings.STOMP_SERVER_PORT),
        "username": settings.STOMP_SERVER_USER,
        "password": settings.STOMP_SERVER_PASSWORD,
        "client_id": client_id if client_id else uuid.uuid4().hex,
    }

    return producer.build_publisher(**connection_params)
