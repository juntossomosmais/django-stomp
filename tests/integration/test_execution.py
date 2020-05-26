import json
import logging
import re
import threading
import uuid
from time import sleep

import pytest
import trio
from django.core.management import call_command
from django.core.serializers.json import DjangoJSONEncoder
from django_stomp.builder import build_listener
from django_stomp.builder import build_publisher
from django_stomp.execution import clean_messages_on_destination_by_acking
from django_stomp.execution import send_message_from_one_destination_to_another
from django_stomp.execution import start_processing
from django_stomp.helpers import clean_dict_with_falsy_or_strange_values
from django_stomp.helpers import create_dlq_destination_from_another_destination
from django_stomp.helpers import retry
from django_stomp.services.consumer import Payload
from pytest_mock import MockFixture
from tests.support import rabbitmq
from tests.support.activemq.connections_details import consumers_details
from tests.support.activemq.message_details import retrieve_message_published
from tests.support.activemq.queue_details import current_queue_configuration
from tests.support.activemq.subscribers_details import offline_durable_subscribers
from tests.support.activemq.topic_details import current_topic_configuration
from tests.support.helpers import is_testing_against_rabbitmq
from tests.support.helpers import wait_for_message_in_log

myself_with_test_callback_standard = "tests.integration.test_execution._test_callback_function_standard"
myself_with_test_callback_nack = "tests.integration.test_execution._test_callback_function_with_nack"
myself_with_test_callback_exception = "tests.integration.test_execution._test_callback_function_with_exception"
myself_with_test_callback_sleep_three_seconds_while_heartbeat_is_running = (
    "tests.integration.test_execution._test_callback_function_with_sleep_three_seconds_while_heartbeat_thread_is_alive"
)
myself_with_test_callback_with_log = "tests.integration.test_execution._test_callback_function_with_logging"
myself_with_test_callback_with_another_log = (
    "tests.integration.test_execution._test_callback_function_with_another_log_message"
)
myself_with_test_callback_sleep_three_seconds = (
    "tests.integration.test_execution._test_callback_function_with_sleep_three_seconds"
)

test_destination_one = "/queue/my-test-destination-one"
test_destination_two = "/queue/my-test-destination-two"
myself_with_test_callback_one = "tests.integration.test_execution._test_callback_function_one"


def test_should_consume_message_and_publish_to_another_queue_using_same_correlation_id():
    # Base environment setup
    publisher = build_publisher()
    some_correlation_id = uuid.uuid4()
    some_header = {"correlation-id": some_correlation_id}
    some_body = {"keyOne": 1, "keyTwo": 2}
    publisher.send(some_body, test_destination_one, headers=some_header, attempt=1)

    # Calling what we need to test
    start_processing(test_destination_one, myself_with_test_callback_one, is_testing=True)

    evaluation_consumer = build_listener(test_destination_two, is_testing=True)
    test_listener = evaluation_consumer._test_listener
    evaluation_consumer.start(wait_forever=False)

    test_listener.wait_for_message()
    received_message = test_listener.get_latest_message()

    assert received_message is not None
    received_header = received_message[0]
    assert received_header["correlation-id"] == str(some_correlation_id)
    received_body = json.loads(received_message[1])
    assert received_body == some_body


def _test_callback_function_one(payload: Payload):
    publisher = build_publisher()
    publisher.send(payload.body, test_destination_two, attempt=1)
    payload.ack()


test_destination_three = "/queue/my-test-destination-three"
test_destination_four = "/queue/my-test-destination-four"
myself_with_test_callback_two = "tests.integration.test_execution._test_callback_function_two"


def test_should_consume_message_and_publish_to_another_queue_using_creating_correlation_id(mocker: MockFixture):
    # It must be called only once to generate the correlation-id
    mock_uuid = mocker.patch("django_stomp.services.producer.uuid")
    uuid_to_publisher, uuid_to_correlation_id, uuid_to_another_publisher = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    mock_uuid.uuid4.side_effect = [uuid_to_publisher, uuid_to_correlation_id, uuid_to_another_publisher]
    # Base environment setup
    publisher = build_publisher()
    some_body = {"keyOne": 1, "keyTwo": 2}
    publisher.send(some_body, test_destination_three, attempt=1)

    # Calling what we need to test
    start_processing(test_destination_three, myself_with_test_callback_two, is_testing=True)

    evaluation_consumer = build_listener(test_destination_four, is_testing=True)
    test_listener = evaluation_consumer._test_listener
    evaluation_consumer.start(wait_forever=False)

    test_listener.wait_for_message()
    received_message = test_listener.get_latest_message()

    assert received_message is not None
    received_header = received_message[0]
    assert received_header["correlation-id"] == str(uuid_to_correlation_id)
    received_body = json.loads(received_message[1])
    assert received_body == some_body


def _test_callback_function_two(payload: Payload):
    publisher = build_publisher()
    publisher.send(payload.body, test_destination_four, attempt=1)
    payload.ack()


test_destination_consumer_one = "/queue/my-test-destination-consumer-one"


def test_should_consume_message_and_dequeue_it_using_ack():
    # In order to publish sample data
    publisher = build_publisher()
    some_body = {"keyOne": 1, "keyTwo": 2}
    publisher.send(some_body, test_destination_consumer_one, attempt=1)

    start_processing(test_destination_consumer_one, myself_with_test_callback_standard, is_testing=True)

    *_, queue_name = test_destination_consumer_one.split("/")
    try:
        queue_status = current_queue_configuration(queue_name)
    except Exception:
        queue_status = rabbitmq.current_queue_configuration(queue_name)

    assert queue_status.number_of_pending_messages == 0
    assert queue_status.number_of_consumers == 0
    assert queue_status.messages_enqueued == 1
    assert queue_status.messages_dequeued == 1


test_destination_durable_consumer_one = "/topic/my-test-destination-durable-consumer-one"


def test_should_create_durable_subscriber_and_receive_standby_messages(mocker: MockFixture, settings):
    temp_uuid_listener = str(uuid.uuid4())
    mocker.patch("django_stomp.execution.get_listener_client_id", return_value=temp_uuid_listener)
    mocker.patch("django_stomp.execution.durable_topic_subscription", True)
    durable_subscription_id = str(uuid.uuid4())
    settings.STOMP_SUBSCRIPTION_ID = durable_subscription_id
    # Just to create a durable subscription
    start_processing(test_destination_durable_consumer_one, myself_with_test_callback_standard, is_testing=True)
    settings.STOMP_SUBSCRIPTION_ID = None

    # In order to publish sample data
    publisher = build_publisher()
    some_body = {"keyOne": 1, "keyTwo": 2}
    publisher.send(some_body, test_destination_durable_consumer_one, attempt=1)
    publisher.send(some_body, test_destination_durable_consumer_one, attempt=1)
    publisher.send(some_body, test_destination_durable_consumer_one, attempt=1)

    # To recreate a durable subscription
    settings.STOMP_SUBSCRIPTION_ID = durable_subscription_id
    start_processing(test_destination_durable_consumer_one, myself_with_test_callback_standard, is_testing=True)

    *_, topic_name = test_destination_durable_consumer_one.split("/")
    try:
        destination_status = current_topic_configuration(topic_name)
        assert destination_status.number_of_consumers == 1
        assert destination_status.messages_enqueued == 3
        assert destination_status.messages_dequeued == 3

        all_offline_subscribers = list(offline_durable_subscribers("localhost"))
        assert len(all_offline_subscribers) > 0
        for index, subscriber_setup in enumerate(all_offline_subscribers):
            if subscriber_setup.subscriber_id == f"{temp_uuid_listener}-listener":
                assert subscriber_setup.dispatched_counter == 3
                assert subscriber_setup.enqueue_counter == 3
                assert subscriber_setup.dequeue_counter == 3
                break
            assert all_offline_subscribers[index] != all_offline_subscribers[-1]
    except Exception:
        destination_status = rabbitmq.current_topic_configuration(topic_name)
        assert destination_status.number_of_consumers == 0
        assert destination_status.messages_enqueued == 3
        assert destination_status.messages_dequeued == 3


test_destination_prefetch_consumer_one = "/queue/my-destination-prefetch-consumer-one"


async def test_should_configure_prefetch_size_as_one(mocker: MockFixture, settings):
    """
    See more details here: https://activemq.apache.org/stomp.html

    Specifies the maximum number of pending messages that will be dispatched to the client.
    Once this maximum is reached no more messages are dispatched until the client acknowledges a
    message. Set to a low value > 1 for fair distribution of messages across consumers
    when processing messages can be slow. Note: if your STOMP client is implemented using a dynamic
    scripting language like Ruby, say, then this parameter must be set to 1 as there is no notion of a
    client-side message size to be sized. STOMP does not support a value of 0.
    """
    listener_id = str(uuid.uuid4())
    # LISTENER_CLIENT_ID is used by ActiveMQ
    mocker.patch("django_stomp.execution.get_listener_client_id", return_value=listener_id)
    # SUBSCRIPTION_ID is used by RabbitMQ to identify a consumer through a tag
    subscription_id = str(uuid.uuid4())
    settings.STOMP_SUBSCRIPTION_ID = subscription_id

    async def collect_consumer_details():
        await trio.sleep(0.5)
        try:
            consumers = list(consumers_details(f"{listener_id}-listener"))
        except Exception:
            consumers = list(rabbitmq.consumers_details(f"{subscription_id}-listener"))

        assert len(consumers) > 0
        for index, consumer_status in enumerate(consumers):
            if consumer_status.destination_name in test_destination_prefetch_consumer_one:
                assert consumer_status.prefetch == 1
                assert consumer_status.max_pending == 0
                break
            assert consumers[index] != consumers[-1]

    async def execute_start_processing():
        listener = start_processing(
            test_destination_prefetch_consumer_one,
            myself_with_test_callback_standard,
            is_testing=True,
            testing_disconnect=False,
            return_listener=True,
        )
        await trio.sleep(10)
        listener.close()

    async with trio.open_nursery() as nursery:
        nursery.start_soon(execute_start_processing)
        nursery.start_soon(collect_consumer_details)


test_destination_dlq_one = f"/queue/my-destination-dql-one-{uuid.uuid4()}"


def test_should_publish_to_dql_due_to_explicit_nack():
    # In order to publish sample data
    with build_publisher().auto_open_close_connection() as publisher:
        some_body = {"keyOne": 1, "keyTwo": 2}
        publisher.send(some_body, test_destination_dlq_one, attempt=1)

    start_processing(test_destination_dlq_one, myself_with_test_callback_nack, is_testing=True)

    *_, queue_name = test_destination_dlq_one.split("/")
    dlq_queue_name = f"DLQ.{queue_name}"
    try:
        queue_status = current_queue_configuration(dlq_queue_name)

        assert queue_status.number_of_pending_messages == 1
        assert queue_status.number_of_consumers == 0
        assert queue_status.messages_enqueued == 1
        assert queue_status.messages_dequeued == 0
    except Exception:
        queue_status = rabbitmq.current_queue_configuration(dlq_queue_name)

        assert queue_status.number_of_pending_messages == 1
        assert queue_status.number_of_consumers == 0
        assert queue_status.messages_dequeued == 0


test_destination_dlq_two = f"/queue/my-destination-dql-two-{uuid.uuid4()}"


def test_should_publish_to_dql_due_to_implicit_nack_given_internal_callback_exception():
    # In order to publish sample data
    with build_publisher().auto_open_close_connection() as publisher:
        some_body = {"keyOne": 1, "keyTwo": 2}
        publisher.send(some_body, test_destination_dlq_two, attempt=1)

    start_processing(test_destination_dlq_two, myself_with_test_callback_exception, is_testing=True)

    *_, queue_name = test_destination_dlq_two.split("/")
    dlq_queue_name = f"DLQ.{queue_name}"
    try:
        queue_status = current_queue_configuration(dlq_queue_name)

        assert queue_status.number_of_pending_messages == 1
        assert queue_status.number_of_consumers == 0
        assert queue_status.messages_enqueued == 1
        assert queue_status.messages_dequeued == 0
    except Exception:
        queue_status = rabbitmq.current_queue_configuration(dlq_queue_name)

        assert queue_status.number_of_pending_messages == 1
        assert queue_status.number_of_consumers == 0
        assert queue_status.messages_dequeued == 0


def test_should_save_tshoot_properties_on_header():
    some_destination = f"tshoot-header-{uuid.uuid4()}"

    # In order to publish sample data
    publisher = build_publisher()
    some_body = {"keyOne": 1, "keyTwo": 2}
    publisher.send(some_body, some_destination, attempt=1)

    try:
        message_status = retrieve_message_published(some_destination)
    except Exception:
        message_status = rabbitmq.retrieve_message_published(some_destination)

    assert message_status.properties.get("tshoot-destination")
    assert message_status.properties["tshoot-destination"] == some_destination


def test_should_send_to_another_destination(caplog):
    caplog.set_level(logging.DEBUG)

    some_source_destination = f"/queue/source-{uuid.uuid4()}"
    some_target_destination = f"/queue/target-{uuid.uuid4()}"

    # In order to publish sample data
    with build_publisher().auto_open_close_connection() as publisher:
        some_body = {"keyOne": 1, "keyTwo": 2}
        some_headers = {"some-header-1": 1, "some-header-2": 2}
        publisher.send(some_body, some_source_destination, some_headers, attempt=1)

    move_messages_consumer = send_message_from_one_destination_to_another(
        some_source_destination, some_target_destination, is_testing=True, return_listener=True
    )

    wait_for_message_in_log(caplog, r"The messages has been moved")
    move_messages_consumer.close()

    *_, source_queue_name = some_source_destination.split("/")
    *_, target_queue_name = some_target_destination.split("/")
    try:
        source_queue_status = current_queue_configuration(source_queue_name)
        target_queue_status = current_queue_configuration(target_queue_name)
        message_status = retrieve_message_published(target_queue_name)
    except Exception:
        source_queue_status = rabbitmq.current_queue_configuration(source_queue_name)
        target_queue_status = rabbitmq.current_queue_configuration(target_queue_name)
        message_status = rabbitmq.retrieve_message_published(target_queue_name)

    assert source_queue_status.number_of_pending_messages == 0
    assert source_queue_status.number_of_consumers == 0
    assert source_queue_status.messages_enqueued == 1
    assert source_queue_status.messages_dequeued == 1

    assert target_queue_status.number_of_pending_messages == 1
    assert target_queue_status.number_of_consumers == 0
    assert target_queue_status.messages_enqueued == 1
    assert target_queue_status.messages_dequeued == 0

    keys = list(some_headers.keys())
    assert len(keys) == 2
    assert int(message_status.properties[keys[0]]) == some_headers[keys[0]]
    assert int(message_status.properties[keys[1]]) == some_headers[keys[1]]
    assert message_status.details == some_body


def test_should_use_heartbeat_and_then_lost_connection_due_message_takes_longer_than_heartbeat(
    caplog, settings, mocker
):
    """
    The listener in this code has an, arguably broken, message handler (see
    _test_callback_function_with_sleep_three_seconds_while_heartbeat_thread_is_alive function) which awaits
    (blocking the consumer for three seconds) for a heartbeat timeout that occurs if no message is shared
    between the broker and the consumer in 1 second (1000 ms).

    Heartbeating requires an error margin due to timing inaccuracies which are usually configured
    by the receiver (such as the broker and even the client). Thus, other brokers may wait for a little bit more
    or less before considering the connection dead.
    """
    caplog.set_level(logging.DEBUG)
    some_destination = f"some-lorem-destination-{uuid.uuid4()}"

    # In order to publish sample data
    with build_publisher().auto_open_close_connection() as publisher:
        some_body = {"keyOne": 1, "keyTwo": 2}
        publisher.send(some_body, some_destination, attempt=1)

    settings.STOMP_OUTGOING_HEARTBEAT = 1000
    settings.STOMP_INCOMING_HEARTBEAT = 1000
    mocker.patch("django_stomp.execution.should_process_msg_on_background", False)

    message_consumer = start_processing(
        some_destination,
        myself_with_test_callback_sleep_three_seconds_while_heartbeat_is_running,
        is_testing=True,
        return_listener=True,
    )

    wait_for_message_in_log(caplog, r"Heartbeat loop ended", message_count_to_wait=2)
    message_consumer.close()

    assert any(
        re.compile(
            f"Received frame.+eart-beat.+{settings.STOMP_OUTGOING_HEARTBEAT},{settings.STOMP_INCOMING_HEARTBEAT}"
        ).match(m)
        for m in caplog.messages
    )
    assert any(re.compile("Sending a heartbeat message at [0-9.]+").match(message) for message in caplog.messages)
    assert any(
        re.compile("Heartbeat timeout: diff_receive=[0-9.]+, time=[0-9.]+, lastrec=[0-9.]+").match(message)
        for message in caplog.messages
    )
    assert any(re.compile("Heartbeat loop ended").match(message) for message in caplog.messages)


def test_should_create_queues_for_virtual_topic_listeners_and_consume_its_messages(caplog):
    caplog.set_level(logging.DEBUG)
    number_of_consumers = 2

    some_virtual_topic = f"VirtualTopic.{uuid.uuid4()}"
    consumers = [
        start_processing(
            f"Consumer.{uuid.uuid4()}.{some_virtual_topic}",
            myself_with_test_callback_standard,
            is_testing=True,
            return_listener=True,
        )
        for _ in range(number_of_consumers)
    ]

    with build_publisher().auto_open_close_connection() as publisher:
        some_body = {"send": 2, "Virtual": "Topic"}
        publisher.send(some_body, f"/topic/{some_virtual_topic}", attempt=1)

    wait_for_message_in_log(
        caplog, r"Received frame: 'MESSAGE'.*body='{\"send\": 2, \"Virtual\": \"Topic\"}.*'", message_count_to_wait=2
    )

    for consumer in consumers:
        consumer.close()

    received_frame_log_messages = [
        message
        for message in caplog.messages
        if re.compile(r"Received frame: 'MESSAGE'.*body='{\"send\": 2, \"Virtual\": \"Topic\"}.*'").match(message)
    ]

    sending_frame_log_messages = [
        message for message in caplog.messages if re.compile(r"Sending frame: \[b'ACK'.*").match(message)
    ]

    assert len(received_frame_log_messages) == number_of_consumers
    assert len(sending_frame_log_messages) == number_of_consumers


def test_should_create_queue_for_virtual_topic_consumer_and_process_messages_sent_when_consumer_is_disconnected(caplog):
    caplog.set_level(logging.DEBUG)

    some_virtual_topic = f"VirtualTopic.{uuid.uuid4()}"
    virtual_topic_consumer_queue = f"Consumer.{uuid.uuid4()}.{some_virtual_topic}"
    consumer = start_processing(
        virtual_topic_consumer_queue, myself_with_test_callback_with_log, is_testing=True, return_listener=True
    )

    with build_publisher().auto_open_close_connection() as publisher:
        some_body = {"send": 2, "another": "VirtualTopic"}
        publisher.send(some_body, f"/topic/{some_virtual_topic}", attempt=1)

    wait_for_message_in_log(caplog, r"I'll process the message: {'send': 2, 'another': 'VirtualTopic'}!")
    consumer.close()

    # Send message to VirtualTopic with consumers disconnected...
    with build_publisher().auto_open_close_connection() as publisher:
        some_body = {"send": "anotherMessage", "2": "VirtualTopic"}
        publisher.send(some_body, f"/topic/{some_virtual_topic}", attempt=1)

    # Start another consumer for the same queue created previously...
    another_consumer = start_processing(
        virtual_topic_consumer_queue, myself_with_test_callback_with_log, is_testing=True, return_listener=True
    )

    wait_for_message_in_log(caplog, r"I'll process the message: {'send': 'anotherMessage', '2': 'VirtualTopic'}!")
    another_consumer.close()

    received_first_frame_log_messages = [
        message
        for message in caplog.messages
        if re.compile(r"I'll process the message: {'send': 2, 'another': 'VirtualTopic'}!").match(message)
    ]
    received_second_frame_log_messages = [
        message
        for message in caplog.messages
        if re.compile(r"I'll process the message: {'send': 'anotherMessage', '2': 'VirtualTopic'}!").match(message)
    ]

    sending_frame_log_messages = [
        message for message in caplog.messages if re.compile(r"Sending frame: \[b'ACK'.*").match(message)
    ]

    assert len(received_first_frame_log_messages) == 1
    assert len(received_second_frame_log_messages) == 1
    assert len(sending_frame_log_messages) == 2


def test_should_create_queue_for_virtual_topic_and_compete_for_its_messages(caplog):
    caplog.set_level(logging.DEBUG)

    some_virtual_topic = f"VirtualTopic.{uuid.uuid4()}"
    virtual_topic_consumer_queue = f"Consumer.{uuid.uuid4()}.{some_virtual_topic}"

    consumers = [
        start_processing(
            virtual_topic_consumer_queue, myself_with_test_callback_with_log, is_testing=True, return_listener=True
        ),
        start_processing(
            virtual_topic_consumer_queue,
            myself_with_test_callback_with_another_log,
            is_testing=True,
            return_listener=True,
        ),
    ]

    with build_publisher().auto_open_close_connection() as publisher:
        with publisher.do_inside_transaction():
            some_body = {"send": 2, "some": "VirtualTopic"}
            publisher.send(some_body, f"/topic/{some_virtual_topic}", attempt=1)
            publisher.send(some_body, f"/topic/{some_virtual_topic}", attempt=1)
            publisher.send(some_body, f"/topic/{some_virtual_topic}", attempt=1)

    wait_for_message_in_log(caplog, r"Sending frame: \[b'ACK'.*", message_count_to_wait=3)

    for consumer in consumers:
        consumer.close()

    callback_logs = [
        message
        for message in caplog.messages
        if re.compile(r"I'll process the message: {'send': 2, 'some': 'VirtualTopic'}!").match(message)
    ]
    another_callback_logs = [
        message
        for message in caplog.messages
        if re.compile(r"{'send': 2, 'some': 'VirtualTopic'} is the message that I'll process!").match(message)
    ]

    sending_frame_log_messages = [
        message for message in caplog.messages if re.compile(r"Sending frame: \[b'ACK'.*").match(message)
    ]

    assert 1 <= len(callback_logs) <= 2
    assert 1 <= len(another_callback_logs) <= 2
    assert len(callback_logs + another_callback_logs) == 3
    assert len(sending_frame_log_messages) == 3


def test_shouldnt_process_message_from_virtual_topic_older_than_the_consumer_queue_creation():
    some_virtual_topic = f"VirtualTopic.{uuid.uuid4()}"
    virtual_topic_consumer_queue = f"Consumer.{uuid.uuid4()}.{some_virtual_topic}"

    with build_publisher().auto_open_close_connection() as publisher:
        some_body = {"send": 2, "topicThat": "isVirtual"}
        publisher.send(some_body, f"/topic/{some_virtual_topic}", attempt=1)

    start_processing(virtual_topic_consumer_queue, myself_with_test_callback_with_log, is_testing=True)

    try:
        queue_status = current_queue_configuration(virtual_topic_consumer_queue)

        assert queue_status.number_of_pending_messages == 0
        assert queue_status.number_of_consumers == 0
        assert queue_status.messages_enqueued == 0
        assert queue_status.messages_dequeued == 0
    except Exception:
        queue_status = rabbitmq.current_queue_configuration(virtual_topic_consumer_queue)

        assert queue_status.number_of_pending_messages == 0
        assert queue_status.number_of_consumers == 0
        assert queue_status.messages_dequeued == 0


def test_should_raise_exception_when_correlation_id_is_required_but_not_received(settings):
    settings.STOMP_CORRELATION_ID_REQUIRED = True

    some_body = {"keyOne": 1, "keyTwo": 2}
    _test_send_message_without_correlation_id_header(some_body, test_destination_one)

    with pytest.raises(Exception):
        assert start_processing(test_destination_one, myself_with_test_callback_one, is_testing=True)


def test_should_consume_message_without_correlation_id_when_it_is_not_required(settings):
    settings.STOMP_CORRELATION_ID_REQUIRED = False

    some_body = {"keyOne": 1, "keyTwo": 2}
    _test_send_message_without_correlation_id_header(some_body, test_destination_one)

    # Calling what we need to test
    start_processing(test_destination_one, myself_with_test_callback_one, is_testing=True)

    evaluation_consumer = build_listener(test_destination_two, is_testing=True)
    test_listener = evaluation_consumer._test_listener
    evaluation_consumer.start(wait_forever=False)

    test_listener.wait_for_message()
    received_message = test_listener.get_latest_message()

    assert received_message is not None
    received_header = received_message[0]
    assert "correlation-id" in received_header
    received_body = json.loads(received_message[1])
    assert received_body == some_body


def test_should_use_heartbeat_and_dont_lose_connection_when_using_background_processing(caplog, settings, mocker):
    """
    The listener in this code has a message handler that takes a long time to process a message (see
    _test_callback_function_with_sleep_three_seconds function). Using a background process to process
    the message, the heartbeat functionality should still work, maintaining the connection
    estabilished between broker and consumer.
    """
    caplog.set_level(logging.DEBUG)
    some_destination = f"some-lorem-destination-{uuid.uuid4()}"

    # In order to publish sample data
    with build_publisher().auto_open_close_connection() as publisher:
        some_body = {"keyOne": 1, "keyTwo": 2}
        publisher.send(some_body, some_destination, attempt=1)

    settings.STOMP_OUTGOING_HEARTBEAT = 1000
    settings.STOMP_INCOMING_HEARTBEAT = 1000

    message_consumer = start_processing(
        some_destination, myself_with_test_callback_sleep_three_seconds, is_testing=True, return_listener=True
    )

    wait_for_message_in_log(caplog, f"{some_body} sucessfully processed!", message_count_to_wait=1)
    message_consumer.close()

    received_heartbeat_frame_regex = re.compile(
        f"Received frame.+heart-beat.+{settings.STOMP_OUTGOING_HEARTBEAT},{settings.STOMP_INCOMING_HEARTBEAT}"
    )
    sending_heartbeat_message_regex = re.compile("Sending a heartbeat message at [0-9.]+")
    sending_ack_frame_regex = re.compile(f"Sending frame: .+ACK.+subscription:{message_consumer._subscription_id}.+")
    heartbeat_timeout_regex = re.compile("Heartbeat timeout: diff_receive=[0-9.]+, time=[0-9.]+, lastrec=[0-9.]+")

    assert any(received_heartbeat_frame_regex.match(m) for m in caplog.messages)
    assert any(sending_heartbeat_message_regex.match(m) for m in caplog.messages)
    assert any(sending_ack_frame_regex.match(m) for m in caplog.messages)
    assert not any(heartbeat_timeout_regex.match(m) for m in caplog.messages)


@pytest.mark.skipif(is_testing_against_rabbitmq(), reason="RabbitMQ doesn't holds the concept of a durable subscriber")
def test_shouldnt_create_a_durable_subscriber_when_dealing_with_virtual_topics():
    all_offline_subscribers_before_the_virtual_topic_connection = list(offline_durable_subscribers("localhost"))

    some_virtual_topic = f"VirtualTopic.{uuid.uuid4()}"
    virtual_topic_consumer_queue = f"Consumer.{uuid.uuid4()}.{some_virtual_topic}"
    start_processing(virtual_topic_consumer_queue, myself_with_test_callback_one, is_testing=True)

    all_offline_subscribers_after_the_virtual_topic_connection = list(offline_durable_subscribers("localhost"))

    assert sorted(all_offline_subscribers_before_the_virtual_topic_connection) == sorted(
        all_offline_subscribers_after_the_virtual_topic_connection
    )


def test_should_connect_with_a_queue_created_without_the_durable_header(caplog):
    caplog.set_level(logging.DEBUG)

    some_destination = f"/queue/some-queue-{uuid.uuid4()}"
    listener = build_listener(some_destination)
    listener._subscription_configuration.pop("durable")
    listener.start(wait_forever=False)
    listener.close()

    send_frames_with_durable_true_regex = re.compile(r"^Sending frame:.*durable:true.*")

    assert all(not send_frames_with_durable_true_regex.match(m) for m in caplog.messages)

    publisher = build_publisher()
    some_correlation_id = uuid.uuid4()
    some_header = {"correlation-id": some_correlation_id}
    some_body = {"keyOne": 1, "keyTwo": 2}
    publisher.send(some_body, some_destination, headers=some_header, attempt=1)

    # Calling what we need to test
    message_consumer = start_processing(
        some_destination, myself_with_test_callback_with_log, is_testing=True, return_listener=True
    )

    wait_for_message_in_log(caplog, r"Sending frame: \[b'ACK'.*", message_count_to_wait=1)
    message_consumer.close()

    consumer_log_message_regex = re.compile(f"I'll process the message: {some_body}!")

    assert any(send_frames_with_durable_true_regex.match(m) for m in caplog.messages)
    assert any(consumer_log_message_regex.match(m) for m in caplog.messages)


def _test_callback_function_standard(payload: Payload):
    # Should dequeue the message
    payload.ack()


def _test_callback_function_with_nack(payload: Payload):
    payload.nack()


def _test_callback_function_with_exception(payload: Payload):
    raise Exception("Lambe Sal")


def _test_callback_function_with_sleep_three_seconds_while_heartbeat_thread_is_alive(payload: Payload):
    heartbeat_threads = [thread for thread in threading.enumerate() if "StompHeartbeatThread" in thread.name]
    while True:
        sleep(3)
        heartbeat_threads = filter(lambda thread: "StompHeartbeatThread" in thread.name, threading.enumerate())
        if all(not thread.is_alive() for thread in heartbeat_threads):
            break


def _test_callback_function_with_logging(payload: Payload):
    logger = logging.getLogger(__name__)
    logger.info("I'll process the message: %s!", payload.body)
    payload.ack()


def _test_callback_function_with_another_log_message(payload: Payload):
    logger = logging.getLogger(__name__)
    logger.info("%s is the message that I'll process!", payload.body)
    payload.ack()


def _test_send_message_without_correlation_id_header(body: str, queue: str, attempt=1):
    publisher = build_publisher()
    standard_header = {
        "tshoot-destination": queue,
        # RabbitMQ
        # These two parameters must be set on consumer side as well, otherwise you'll get precondition_failed
        "x-dead-letter-routing-key": create_dlq_destination_from_another_destination(queue),
        "x-dead-letter-exchange": "",
    }

    send_params = {
        "destination": queue,
        "body": json.dumps(body, cls=DjangoJSONEncoder),
        "headers": standard_header,
        "content_type": "application/json;charset=utf-8",
        "transaction": getattr(publisher, "_tmp_transaction_id", None),
    }
    send_params = clean_dict_with_falsy_or_strange_values(send_params)

    def _internal_send_logic():
        publisher.start_if_not_open()
        publisher.connection.send(**send_params)

    retry(_internal_send_logic, attempt=attempt)


def _test_callback_function_with_sleep_three_seconds(payload: Payload):
    sleep(3)
    payload.ack()
    logger = logging.getLogger(__name__)
    logger.info("%s sucessfully processed!", payload.body)


def test_should_clean_all_messages_on_a_destination(caplog):
    caplog.set_level(logging.DEBUG)

    some_source_destination = f"/queue/flood-this-queue-with-trash"
    trash_msgs_count = 10

    # publishes trash to a destination
    with build_publisher().auto_open_close_connection() as publisher:
        some_body = {"some": "trash"}
        some_headers = {"some": "header"}

        for i in range(0, trash_msgs_count):
            publisher.send(some_body, some_source_destination, some_headers, attempt=1)

    # # command invocation
    consumer = clean_messages_on_destination_by_acking(some_source_destination, is_testing=True, return_listener=True)
    wait_for_message_in_log(caplog, r"Message has been removed!", message_count_to_wait=trash_msgs_count)
    consumer.close()

    # removing /queue/
    *_, source_queue_name = some_source_destination.split("/")

    try:
        # if activemq broker is running
        source_queue_status = current_queue_configuration(source_queue_name)
    except Exception:
        # if rabbitmq broker is running
        source_queue_status = rabbitmq.current_queue_configuration(source_queue_name)

    assert source_queue_status.number_of_pending_messages == 0
    assert source_queue_status.number_of_consumers == 0
    assert source_queue_status.messages_enqueued == trash_msgs_count  # enqueued the queue with trash!
    assert source_queue_status.messages_dequeued == trash_msgs_count  # cleaned all the trash on the queue!
