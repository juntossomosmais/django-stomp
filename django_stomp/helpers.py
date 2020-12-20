import functools
import logging
import time
import uuid
from typing import Callable
from typing import Dict
from typing import Optional

import tenacity

from django_stomp.settings.django_stomp import DjangoStompSettings

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
        return destination[position + 1 :]
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
        after=tenacity.after_log(logger, logger.level) if logger else None,
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


def display_heartbeat_warning_if_necessary(settings: DjangoStompSettings):
    """
    Displays heartbeat warning if the user has a possible misconfigured settings.
    """
    if (
        is_heartbeat_enabled(settings.outgoing_heartbeat, settings.incoming_heartbeat)
        and not settings.should_process_msg_on_background
    ):
        logger.warning(
            "STOMP heartbeat enabled while message processing on background is disable! "
            "This could potentially lead to a false positive heartbeat timeout!"
        )


def build_final_client_id(listener_client_id: Optional[str], is_durable_topic_subscription: bool) -> str:
    """
    Generates a new client id for listener when needed. If a client_id is supplied, then it's respected, unless
    it's not for a durable topic subscription where a final uuid is appended.
    """
    # not durable and exists client_id -> append uuid to avoid problems
    if not is_durable_topic_subscription and listener_client_id is not None:
        return f"{listener_client_id}-{uuid.uuid4().hex}"

    # durable or not-durable without client_id
    if listener_client_id is None:
        listener_client_id = str(uuid.uuid4())

    return listener_client_id
