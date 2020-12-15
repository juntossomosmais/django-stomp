"""
Module for subscribing to destinations.
"""
import logging

from typing import Optional

from django.conf import settings
from django.utils.module_loading import import_string
from django_stomp.builder import build_listener
from django_stomp.callbacks import callback_factory
from django_stomp.helpers import eval_str_as_boolean
from django_stomp.helpers import get_listener_client_id
from django_stomp.services.consumer import Listener
from django_stomp.subscriptions import create_dlq_queue, subscribe_for_testing, subscribe_forever
from django_stomp.subscriptions import create_routing_key_bindings

logger = logging.getLogger("django_stomp")

wait_to_connect = int(getattr(settings, "STOMP_WAIT_TO_CONNECT", 10))
durable_topic_subscription = eval_str_as_boolean(getattr(settings, "STOMP_DURABLE_TOPIC_SUBSCRIPTION", False))
listener_client_id = getattr(settings, "STOMP_LISTENER_CLIENT_ID", None)
is_correlation_id_required = eval_str_as_boolean(getattr(settings, "STOMP_CORRELATION_ID_REQUIRED", True))
should_process_msg_on_background = eval_str_as_boolean(getattr(settings, "STOMP_PROCESS_MSG_ON_BACKGROUND", True))
publisher_name = "django-stomp-another-target"


def start_processing(
    destination_name: str,
    callback_str: str,
    is_testing: bool = False,
    testing_disconnect: bool = True,
    param_to_callback: bool = None,
    return_listener: bool = False,
    execute_workaround_to_deal_with_rabbit_mq: bool = True,
    broker_host_to_consume_messages: Optional[str] = None,
    broker_port_to_consume_messages: Optional[int] = None,
):
    """
    Starts processing messages from a STOMP subscription.
    """
    callback_function = import_string(callback_str)
    client_id = get_listener_client_id(durable_topic_subscription, listener_client_id)

    if execute_workaround_to_deal_with_rabbit_mq:
        create_dlq_queue(destination_name, listener_client_id)
        create_routing_key_bindings(destination_name, listener_client_id)

    listener = build_listener(
        destination_name,
        durable_topic_subscription,
        client_id=client_id,
        should_process_msg_on_background=should_process_msg_on_background,
        custom_stomp_server_host=broker_host_to_consume_messages,
        custom_stomp_server_port=broker_port_to_consume_messages,
    )

    wrapped_callback = callback_factory(listener, callback_function, param_to_callback, is_correlation_id_required)

    if is_testing:
        subscribe_for_testing(listener, wrapped_callback, disconnect_after_tests=testing_disconnect)
        return listener

    subscribe_forever(listener, wrapped_callback)


def send_message_from_one_destination_to_another(
    source_destination: str,
    target_destination: str,
    is_testing: bool = False,
    testing_disconnect: bool = True,
    return_listener: bool = False,
    custom_stomp_server_host: Optional[str] = None,
    custom_stomp_server_port: Optional[int] = None,
) -> Optional[Listener]:
    callback_function = "django_stomp.callbacks.callback_send_to_another_destination"

    return start_processing(
        source_destination,
        callback_function,
        is_testing=is_testing,
        testing_disconnect=testing_disconnect,
        param_to_callback=target_destination,  # type: ignore
        return_listener=return_listener,
        execute_workaround_to_deal_with_rabbit_mq=False,
        broker_host_to_consume_messages=custom_stomp_server_host,
        broker_port_to_consume_messages=custom_stomp_server_port,
    )


def clean_messages_on_destination_by_acking(
    source_destination: str, is_testing: bool = False, testing_disconnect: bool = True, return_listener: bool = False,
) -> Optional[Listener]:
    """
    Cleans a queue by acking all messages on it (no queue purging or deleting).
    """
    ack_only_callback_path = "django_stomp.callbacks.callback_for_cleaning_queues"

    return start_processing(
        source_destination,
        ack_only_callback_path,
        is_testing=is_testing,
        testing_disconnect=testing_disconnect,
        return_listener=return_listener,
        execute_workaround_to_deal_with_rabbit_mq=False,
    )
