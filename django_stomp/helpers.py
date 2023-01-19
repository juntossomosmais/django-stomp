import functools
import logging
import ssl
import time
import uuid
from typing import Callable
from typing import Dict

import tenacity
from django.conf import settings as django_settings
from stomp.connect import StompConnection11

logger = logging.getLogger("django_stomp")


def slow_down(_func=None, *args, **kwargs):
    """Sleep given amount of seconds before calling the function"""

    before = kwargs.get("before", 0.5)
    after = kwargs.get("after", 0.5)

    def decorator_slow_down(func):
        @functools.wraps(func)
        def wrapper_slow_down(*args, **kwargs):
            time.sleep(before)
            value = func(*args, **kwargs)
            time.sleep(after)
            return value

        return wrapper_slow_down

    if _func is None:
        return decorator_slow_down
    else:
        return decorator_slow_down(_func)


def eval_str_as_boolean(value: str):
    return str(value).lower() in ("true", "1", "t", "y")


def return_none_if_provided_value_is_falsy_or_strange(value):
    if value is not None and (value == "" or value == b"" or value in (".", "none")):
        return None
    return value


def clean_dict_with_falsy_or_strange_values(value: Dict) -> Dict:
    return {k: v for k, v in value.items() if return_none_if_provided_value_is_falsy_or_strange(v) or v == 0}


def eval_as_int_otherwise_none(value):
    return int(value) if value or value == 0 else None


def only_destination_name(destination: str) -> str:
    position = destination.rfind("/")
    if position > 0:
        return destination[position + 1 :]  # noqa: E203
    return destination


def create_dlq_destination_from_another_destination(destination: str) -> str:
    return f"DLQ.{only_destination_name(destination)}"


def remove_key_from_dict(dictionary, key):
    dictionary.pop(key, None)


def is_destination_from_virtual_topic(destination_name: str) -> bool:
    return ".VirtualTopic." in destination_name


def is_dlq_destination(destination_name: str) -> bool:
    return "DLQ." in destination_name


def get_subscription_destination(destination_name: str) -> str:
    """
    Given a destination name like Consumer.XPTO.VirtualTopic.topic-name, returns
    '/topic/VirtualTopic.topic-name' in order to mimic the ActiveMQ Virtual Topics
    default behaviour in RabbitMQ.

    More on: https://activemq.apache.org/virtual-destinations
    """
    if is_destination_from_virtual_topic(destination_name) and not is_dlq_destination(destination_name):
        virtual_topic_name = destination_name.split(".VirtualTopic.")[-1]
        return f"/topic/VirtualTopic.{virtual_topic_name}"
    return destination_name


def get_listener_client_id(durable_topic_subscription: bool, listener_client_id: str) -> str:
    if not durable_topic_subscription and listener_client_id:
        return f"{listener_client_id}-{uuid.uuid4().hex}"
    return listener_client_id


def retry(function: Callable, attempt=10, *args, **kwargs):
    retry_configuration = tenacity.Retrying(
        stop=tenacity.stop_after_attempt(attempt),
        wait=tenacity.wait_fixed(3) + tenacity.wait_random(0, 2),
        after=tenacity.after_log(logger, logging.WARNING) if logger else None,
        reraise=True,
    )
    return retry_configuration(function, *args, **kwargs)


def eval_as_int_if_provided_value_is_not_none_otherwise_none(value):
    return int(value) if value is not None else None


def is_heartbeat_enabled(outgoing_heartbeat: int, incoming_heartbeat: int):
    """
    Determine if STOMP heartbeat is enabled or not. Per the specification, it'll only be enabled
    if a both estabilished times is greater than zero.

    More on: https://stomp.github.io/stomp-specification-1.1.html#Heart-beating
    """
    return outgoing_heartbeat > 0 and incoming_heartbeat > 0


def set_ssl_connection(conn: StompConnection11) -> StompConnection11:
    """Sets the SSL connection params given some values and return it"""
    STOMP_SERVER_HOST = getattr(django_settings, "STOMP_SERVER_HOST", "127.0.0.1")
    STOMP_SERVER_PORT = eval_as_int_if_provided_value_is_not_none_otherwise_none(
        getattr(django_settings, "STOMP_SERVER_PORT", 61613)
    )
    STOMP_HOST_AND_PORTS = [(STOMP_SERVER_HOST, STOMP_SERVER_PORT)]

    key_file = getattr(django_settings, "DEFAULT_STOMP_KEY_FILE", None)
    cert_file = getattr(django_settings, "DEFAULT_STOMP_CERT_FILE", None)
    ca_certs = getattr(django_settings, "DEFAULT_STOMP_CA_CERTS", None)
    cert_validator = getattr(django_settings, "DEFAULT_STOMP_CERT_VALIDATOR", None)
    ssl_version = getattr(django_settings, "DEFAULT_STOMP_SSL_VERSION", ssl.PROTOCOL_TLS_CLIENT)
    password = getattr(django_settings, "DEFAULT_STOMP_SSL_PASSWORD", None)
    conn.set_ssl(
        for_hosts=STOMP_HOST_AND_PORTS,
        key_file=key_file,
        cert_file=cert_file,
        ca_certs=ca_certs,
        cert_validator=cert_validator,
        ssl_version=ssl_version,
        password=password,
    )
    return conn
