import json
import logging
import re
import threading
import uuid
from time import sleep
from unittest import mock
from uuid import uuid4

import pytest
import trio
from django.db.backends.signals import connection_created
from pytest_mock import MockFixture
from stomp.exception import NotConnectedException

from django_stomp.builder import build_listener
from django_stomp.builder import build_publisher
from django_stomp.execution import clean_messages_on_destination_by_acking
from django_stomp.execution import send_message_from_one_destination_to_another
from django_stomp.execution import start_processing
from django_stomp.services.producer import do_inside_transaction
from tests.support import rabbitmq
from tests.support.activemq.connections_details import consumers_details
from tests.support.activemq.message_details import retrieve_message_published
from tests.support.activemq.queue_details import current_queue_configuration
from tests.support.activemq.subscribers_details import offline_durable_subscribers
from tests.support.activemq.topic_details import current_topic_configuration
from tests.support.callbacks_for_tests import callback_move_and_ack_path
from tests.support.callbacks_for_tests import callback_standard_path
from tests.support.callbacks_for_tests import callback_with_another_log_message_path
from tests.support.callbacks_for_tests import callback_with_exception_path
from tests.support.callbacks_for_tests import callback_with_explicit_db_connection_path
from tests.support.callbacks_for_tests import callback_with_logging_path
from tests.support.callbacks_for_tests import callback_with_nack_path
from tests.support.callbacks_for_tests import callback_with_sleep_three_seconds_path
from tests.support.callbacks_for_tests import callback_with_sleep_three_seconds_while_heartbeat_thread_is_alive_path
from tests.support.helpers import get_destination_metrics_from_broker
from tests.support.helpers import get_latest_message_from_destination_using_test_listener
from tests.support.helpers import is_testing_against_rabbitmq
from tests.support.helpers import publish_to_destination
from tests.support.helpers import publish_without_correlation_id_header
from tests.support.helpers import wait_for_message_in_log


NO_ERRORS_DICT = {"please": "no errors"}


@pytest.fixture()
def sending_frame_pattern() -> re.Pattern:
    return re.compile(r"Sending frame: \[b'ACK'.*")


def test_should_consume_message_and_publish_to_another_queue_using_same_correlation_id():
    # Base environment setup
    destination_one = f"/queue/my-test-destination-one-{uuid4()}"
    destination_two = f"/queue/my-test-destination-two-{uuid4()}"
    destination_three = f"/queue/my-test-destination-three-{uuid4()}"

    some_correlation_id = uuid.uuid4()
    some_header = {"correlation-id": some_correlation_id}
    some_body = {"keyOne": 1, "keyTwo": 2}

    # publishes to destination one
    publish_to_destination(destination_one, some_body, some_header)

    # return_listener=True is required to avoid testing_listener.close() on the test's main thread which prematurely closes
    # the connection to the broker which can compromise the callback's ACK (runs on another thread)
    # consumes from destination_one and publishes to destination_two
    start_processing(
        destination_one,
        callback_move_and_ack_path,
        param_to_callback=destination_two,
        is_testing=True,
        return_listener=True,
    )

    # consumes from destination_two and publishes to destination_three
    start_processing(
        destination_two,
        callback_move_and_ack_path,
        param_to_callback=destination_three,
        is_testing=True,
        return_listener=True,
    )

    # asserts that the msg is received on destination three WITH THE SAME correlation-id of destination_one
    received_message = get_latest_message_from_destination_using_test_listener(destination_three)

    assert received_message is not None
    received_header = received_message[0]

    assert received_header["correlation-id"] == str(some_correlation_id)
    received_body = json.loads(received_message[1])

    assert received_body == some_body


def test_should_consume_message_and_publish_to_another_queue_using_creating_correlation_id(mocker: MockFixture):
    # Base environment setup
    some_body = {"keyOne": 1, "keyTwo": 2}

    destination_three = f"/queue/my-test-destination-again-three-{uuid4()}"
    destination_four = f"/queue/my-test-destination-again-four-{uuid4()}"

    # mocks: It must be called only once to generate the correlation-id
    mock_uuid = mocker.patch("django_stomp.services.producer.uuid")

    uuid_to_publisher, uuid_to_correlation_id, uuid_to_another_publisher, uuid_publisher_mover = (
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
    )

    mock_uuid.uuid4.side_effect = [
        uuid_to_publisher,
        uuid_to_correlation_id,
        uuid_to_another_publisher,
        uuid_publisher_mover,
    ]

    # publishes to destination three
    publish_to_destination(destination_three, some_body)

    # consumes from destination three and publishes to destination four
    start_processing(
        destination_three,
        callback_move_and_ack_path,
        param_to_callback=destination_four,
        is_testing=True,
        return_listener=True,
    )

    # asserts that the msg is received on destination four WITH THE SAME correlation-id of destination_three
    received_message = get_latest_message_from_destination_using_test_listener(destination_four)

    assert received_message is not None
    received_header = received_message[0]

    assert received_header["correlation-id"] == str(uuid_to_correlation_id)
    received_body = json.loads(received_message[1])

    assert received_body == some_body


def test_should_consume_message_and_dequeue_it_using_ack():
    # In order to publish sample data
    some_body = {"keyOne": 1, "keyTwo": 2}
    test_destination_consumer_one = f"/queue/my-test-destination-consumer-one-{uuid4()}"
    *_, queue_name = test_destination_consumer_one.split("/")

    publish_to_destination(test_destination_consumer_one, some_body)
    start_processing(test_destination_consumer_one, callback_standard_path, is_testing=True)
    queue_status = get_destination_metrics_from_broker(queue_name)

    assert queue_status.number_of_pending_messages == 0
    assert queue_status.number_of_consumers == 0
    assert queue_status.messages_enqueued == 1
    assert queue_status.messages_dequeued == 1


def test_should_create_durable_subscriber_and_receive_standby_messages(mocker: MockFixture, settings):
    test_destination_durable_consumer_one = f"/topic/my-test-destination-durable-consumer-one-{uuid4()}"
    temp_uuid_listener = str(uuid.uuid4())

    mocker.patch("django_stomp.execution.get_listener_client_id", return_value=temp_uuid_listener)
    mocker.patch("django_stomp.execution.durable_topic_subscription", True)
    durable_subscription_id = str(uuid.uuid4())
    settings.STOMP_SUBSCRIPTION_ID = durable_subscription_id
    # Just to create a durable subscription
    start_processing(test_destination_durable_consumer_one, callback_standard_path, is_testing=True)
    settings.STOMP_SUBSCRIPTION_ID = None

    # In order to publish sample data
    some_body = {"keyOne": 1, "keyTwo": 2}

    publish_to_destination(test_destination_durable_consumer_one, some_body)
    publish_to_destination(test_destination_durable_consumer_one, some_body)
    publish_to_destination(test_destination_durable_consumer_one, some_body)

    # To recreate a durable subscription
    settings.STOMP_SUBSCRIPTION_ID = durable_subscription_id
    start_processing(test_destination_durable_consumer_one, callback_standard_path, is_testing=True)

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
        destination_status = rabbitmq.current_topic_configuration(topic_name)  # type: ignore
        assert destination_status.number_of_consumers == 0
        assert destination_status.messages_enqueued == 3
        assert destination_status.messages_dequeued == 3


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
    test_destination_prefetch_consumer_one = f"/queue/my-destination-prefetch-consumer-one-{uuid4()}"

    listener_id = str(uuid.uuid4())
    # LISTENER_CLIENT_ID is used by ActiveMQ
    mocker.patch("django_stomp.execution.get_listener_client_id", return_value=listener_id)
    # SUBSCRIPTION_ID is used by RabbitMQ to identify a consumer through a tag
    subscription_id = str(uuid.uuid4())
    settings.STOMP_SUBSCRIPTION_ID = subscription_id

    async def collect_consumer_details():
        await trio.sleep(2)
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
            callback_standard_path,
            is_testing=True,
            testing_disconnect=False,
            return_listener=True,
        )
        await trio.sleep(10)
        listener.close()

    async with trio.open_nursery() as nursery:
        nursery.start_soon(execute_start_processing)
        nursery.start_soon(collect_consumer_details)


def test_should_publish_to_dql_due_to_explicit_nack():
    test_destination_dlq_one = f"/queue/my-destination-dql-one-{uuid.uuid4()}"
    *_, queue_name = test_destination_dlq_one.split("/")
    dlq_queue_name = f"DLQ.{queue_name}"

    # In order to publish sample data
    some_body = {"keyOne": 1, "keyTwo": 2}
    publish_to_destination(test_destination_dlq_one, some_body)

    start_processing(test_destination_dlq_one, callback_with_nack_path, is_testing=True)

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


def test_should_publish_to_dql_due_to_implicit_nack_given_internal_callback_exception():
    test_destination_dlq_two = f"/queue/my-destination-dql-two-{uuid.uuid4()}"
    *_, queue_name = test_destination_dlq_two.split("/")
    dlq_queue_name = f"DLQ.{queue_name}"

    # In order to publish sample data
    some_body = {"keyOne": 1, "keyTwo": 2}
    publish_to_destination(test_destination_dlq_two, some_body)

    start_processing(test_destination_dlq_two, callback_with_exception_path, is_testing=True)

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
    some_body = {"keyOne": 1, "keyTwo": 2}
    publish_to_destination(some_destination, some_body)

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


@mock.patch("django_stomp.execution.should_process_msg_on_background", False)
def test_should_use_heartbeat_and_then_lost_connection_due_message_takes_longer_than_heartbeat_no_background_processing(
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
    some_body = {"keyOne": 1, "keyTwo": 2}
    publish_to_destination(some_destination, some_body)

    settings.STOMP_OUTGOING_HEARTBEAT = 1000
    settings.STOMP_INCOMING_HEARTBEAT = 1000

    message_consumer = start_processing(
        some_destination,
        callback_with_sleep_three_seconds_while_heartbeat_thread_is_alive_path,
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


def test_should_create_queues_for_virtual_topic_listeners_and_consume_its_messages(
    caplog: pytest.LogCaptureFixture, sending_frame_pattern: re.Pattern
):
    caplog.set_level(logging.DEBUG)
    number_of_consumers = 2

    some_virtual_topic = f"VirtualTopic.{uuid.uuid4()}"
    consumers = [
        start_processing(
            f"Consumer.{uuid.uuid4()}.{some_virtual_topic}",
            callback_standard_path,
            is_testing=True,
            return_listener=True,
        )
        for _ in range(number_of_consumers)
    ]

    some_body = {"send": 2, "Virtual": "Topic"}
    publish_to_destination(f"/topic/{some_virtual_topic}", some_body)

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

    sending_frame_log_messages = [message for message in caplog.messages if sending_frame_pattern.match(message)]

    assert len(received_frame_log_messages) == number_of_consumers
    assert len(sending_frame_log_messages) == number_of_consumers


def test_should_create_queue_for_virtual_topic_consumer_and_process_messages_sent_when_consumer_is_disconnected(
    caplog: pytest.LogCaptureFixture, sending_frame_pattern: re.Pattern
):
    caplog.set_level(logging.DEBUG)

    some_virtual_topic = f"VirtualTopic.{uuid.uuid4()}"
    virtual_topic_consumer_queue = f"Consumer.{uuid.uuid4()}.{some_virtual_topic}"
    consumer = start_processing(
        virtual_topic_consumer_queue, callback_with_logging_path, is_testing=True, return_listener=True
    )

    some_body = {"send": 2, "another": "VirtualTopic"}
    publish_to_destination(f"/topic/{some_virtual_topic}", some_body)

    wait_for_message_in_log(caplog, r"I'll process the message: {'send': 2, 'another': 'VirtualTopic'}!")
    consumer.close()

    # Send message to VirtualTopic with consumers disconnected...
    some_body = {"send": "anotherMessage", "2": "VirtualTopic"}
    publish_to_destination(f"/topic/{some_virtual_topic}", some_body)

    # Start another consumer for the same queue created previously...
    another_consumer = start_processing(
        virtual_topic_consumer_queue, callback_with_logging_path, is_testing=True, return_listener=True
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

    sending_frame_log_messages = [message for message in caplog.messages if sending_frame_pattern.match(message)]

    assert len(received_first_frame_log_messages) == 1
    assert len(received_second_frame_log_messages) == 1
    assert len(sending_frame_log_messages) == 2


def test_should_create_queue_for_virtual_topic_and_compete_for_its_messages(
    caplog: pytest.LogCaptureFixture, sending_frame_pattern: re.Pattern
):
    caplog.set_level(logging.DEBUG)

    some_virtual_topic = f"VirtualTopic.{uuid.uuid4()}"
    virtual_topic_consumer_queue = f"Consumer.{uuid.uuid4()}.{some_virtual_topic}"

    consumers = [
        start_processing(
            virtual_topic_consumer_queue, callback_with_logging_path, is_testing=True, return_listener=True
        ),
        start_processing(
            virtual_topic_consumer_queue, callback_with_another_log_message_path, is_testing=True, return_listener=True
        ),
    ]

    with build_publisher().auto_open_close_connection() as publisher:
        with publisher.do_inside_transaction():
            some_body = {"send": 2, "some": "VirtualTopic"}
            publisher.send(some_body, f"/topic/{some_virtual_topic}", attempt=1)
            publisher.send(some_body, f"/topic/{some_virtual_topic}", attempt=1)
            publisher.send(some_body, f"/topic/{some_virtual_topic}", attempt=1)

    wait_for_message_in_log(caplog, sending_frame_pattern.pattern, message_count_to_wait=3)

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

    sending_frame_log_messages = [message for message in caplog.messages if sending_frame_pattern.match(message)]

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

    start_processing(virtual_topic_consumer_queue, callback_with_logging_path, is_testing=True)

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


@mock.patch("django_stomp.execution.is_correlation_id_required", True)
def test_should_raise_exception_when_correlation_id_is_required_but_not_received(settings):
    test_destination_one = f"/queue/test-correlation-id-required-one-{uuid4()}"
    test_destination_two = f"/queue/test-correlation-id-required-two-{uuid4()}"

    some_body = {"keyOne": 1, "keyTwo": 2}
    publish_without_correlation_id_header(test_destination_one, some_body)

    with pytest.raises(Exception):
        assert start_processing(
            test_destination_one, callback_move_and_ack_path, param_to_callback=test_destination_two, is_testing=True
        )


@mock.patch("django_stomp.execution.is_correlation_id_required", True)
def test_should_raise_exception_when_correlation_id_is_not_supplied_and_publish_it_to_dlq(settings, caplog):
    some_body = {"keyOne": 1, "keyTwo": 2}
    destination_name = f"/queue/destination-for-correlation-id-testing-required-{uuid4()}"

    # removing /queue/
    *_, source_queue_name = destination_name.split("/")
    dlq_source_queue_name = f"DLQ.{source_queue_name}"

    # publishes messages WITHOUT correlation-id header, but message must be persistent or won't go to DLQ
    # https://activemq.apache.org/message-redelivery-and-dlq-handling
    publish_without_correlation_id_header(destination_name, some_body, persistent=True)

    consumer = start_processing(destination_name, callback_standard_path, is_testing=True, return_listener=True)
    wait_for_message_in_log(
        caplog,
        r"A exception of type <class 'django_stomp\.exceptions\.CorrelationIdNotProvidedException'>.*",
        message_count_to_wait=1,
    )
    consumer.close()

    dlq_source_queue_status = get_destination_metrics_from_broker(dlq_source_queue_name)

    # asserts that DLQ has a message on it!
    assert dlq_source_queue_status.number_of_pending_messages == 1
    assert dlq_source_queue_status.number_of_consumers == 0


@mock.patch("django_stomp.execution.is_correlation_id_required", False)
def test_should_consume_message_without_correlation_id_when_it_is_not_required_no_dlq(settings):
    some_body = {"keyOne": 1, "keyTwo": 2}
    destination_name = f"/queue/destination-for-correlation-id-testing-not-required-{uuid4()}"

    # removing /queue/
    *_, source_queue_name = destination_name.split("/")
    dlq_source_queue_name = f"DLQ.{source_queue_name}"

    # publishes messages WITHOUT correlation-id header, but message must be persistent or won't go to DLQ
    # https://activemq.apache.org/message-redelivery-and-dlq-handling
    publish_without_correlation_id_header(destination_name, some_body, persistent=True)

    start_processing(destination_name, callback_standard_path, is_testing=True)

    source_queue_status = get_destination_metrics_from_broker(source_queue_name)

    # normal queue should have ONE dequeued message: no exception was raised!
    assert source_queue_status.number_of_pending_messages == 0
    assert source_queue_status.number_of_consumers == 0
    assert source_queue_status.messages_dequeued == 1

    dlq_source_queue_status = get_destination_metrics_from_broker(dlq_source_queue_name)

    # DLQ should have NO messages
    assert dlq_source_queue_status.number_of_pending_messages == 0
    assert dlq_source_queue_status.number_of_consumers == 0
    assert dlq_source_queue_status.messages_dequeued == 0


@mock.patch("django_stomp.execution.should_process_msg_on_background", True)
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
    some_body = {"keyOne": 1, "keyTwo": 2}
    publish_to_destination(some_destination, some_body)

    settings.STOMP_OUTGOING_HEARTBEAT = 1000
    settings.STOMP_INCOMING_HEARTBEAT = 1000

    message_consumer = start_processing(
        some_destination, callback_with_sleep_three_seconds_path, is_testing=True, return_listener=True
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
    destination_two = f"/queue/testing-for-durable-subscriber-with-virtual-topics-{uuid4()}"

    some_virtual_topic = f"VirtualTopic.{uuid.uuid4()}"
    virtual_topic_consumer_queue = f"Consumer.{uuid.uuid4()}.{some_virtual_topic}"
    start_processing(
        virtual_topic_consumer_queue, callback_move_and_ack_path, param_to_callback=destination_two, is_testing=True
    )

    all_offline_subscribers_after_the_virtual_topic_connection = list(offline_durable_subscribers("localhost"))

    assert sorted(all_offline_subscribers_before_the_virtual_topic_connection) == sorted(
        all_offline_subscribers_after_the_virtual_topic_connection
    )


def test_should_connect_with_a_queue_created_without_the_durable_header(
    caplog: pytest.LogCaptureFixture, sending_frame_pattern: re.Pattern
):
    caplog.set_level(logging.DEBUG)
    some_destination = f"/queue/some-queue-without-durable-headers-{uuid.uuid4()}"

    listener = build_listener(some_destination)
    listener._subscription_configuration.pop("durable")
    listener.start(wait_forever=False)
    listener.close()

    send_frames_with_durable_true_regex = re.compile(r"^Sending frame:.*durable:true.*")

    assert all(not send_frames_with_durable_true_regex.match(m) for m in caplog.messages)

    some_header = {"correlation-id": uuid.uuid4()}
    some_body = {"keyOne": 1, "keyTwo": 2}
    publish_to_destination(some_destination, some_body, some_header)

    # Calling what we need to test
    message_consumer = start_processing(
        some_destination, callback_with_logging_path, is_testing=True, return_listener=True
    )

    wait_for_message_in_log(caplog, sending_frame_pattern.pattern, message_count_to_wait=1)
    message_consumer.close()

    consumer_log_message_regex = re.compile(f"I'll process the message: {some_body}!")

    assert any(send_frames_with_durable_true_regex.match(m) for m in caplog.messages)
    assert any(consumer_log_message_regex.match(m) for m in caplog.messages)


def test_should_clean_all_messages_on_a_destination(caplog):
    caplog.set_level(logging.DEBUG)
    trash_msgs_count = 10
    some_source_destination = f"/queue/flood-this-queue-with-trash-{uuid4()}"
    *_, source_queue_name = some_source_destination.split("/")

    some_body = {"some": "trash"}
    some_headers = {"some": "header"}

    # command invocation
    consumer = clean_messages_on_destination_by_acking(some_source_destination, is_testing=True, return_listener=True)

    with build_publisher().auto_open_close_connection() as publisher:
        for _ in range(0, trash_msgs_count):
            publisher.send(some_body, some_source_destination, some_headers, attempt=1)

    wait_for_message_in_log(caplog, r"Message has been removed!", message_count_to_wait=trash_msgs_count)
    consumer.close()

    # asserts that messages were acked
    source_queue_status = get_destination_metrics_from_broker(source_queue_name)

    assert source_queue_status.number_of_pending_messages == 0
    assert source_queue_status.number_of_consumers == 0
    assert source_queue_status.messages_enqueued == trash_msgs_count  # enqueued the queue with trash!
    assert source_queue_status.messages_dequeued == trash_msgs_count  # cleaned all the trash on the queue!


@mock.patch("django_stomp.execution.is_correlation_id_required", True)
def test_should_clean_problematic_headers_and_publish_it_to_destination_successfully(settings, caplog):
    destination_name = f"/queue/headers-cleaning-destination-{uuid4()}"
    *_, source_queue_name = destination_name.split("/")

    loyalty_event_body = {
        "points": 300,
        "account": "7cdd43af-7e36-40c2-b7e7-e0e0a62fa328",
        "sponsor": "3591bfff-3241-46e3-8829-2389d56da04c",
    }

    dangerous_headers = {
        "subscription": "77625173-42b5-4c62-9c24-1fc4a4668dcc-listener",
        "destination": "/queue/wrong-destination",
        "message-id": "T_77625173-42b5-4c62-9c24-1fc4a4668dcc-listener@@session-jSfP4eyH59eKxHaZDv59Cg@@2",
        "redelivered": "false",
        "x-dead-letter-routing-key": "DLQ.wrong-destination",
        "x-dead-letter-exchange": "",
        "tshoot-destination": "/queue/wrong-destination",
        "transaction": "11837f0b-f1c5-494f-9b2b-347c636d8ca2",
        "eventType": "someType",
        "correlation-id": "6e10903e13ddcde54304883e5df713a5",
        "persistent": "true",
        "content-type": "application/json;charset=utf-8",
        "content-length": "298",
    }

    # headers such as message-id, transaction are reserved for internal use of RabbitMQ: they should
    # generate problems if NOT removed
    publish_to_destination(destination_name, loyalty_event_body, dangerous_headers)

    # published message assertions
    received_message = get_latest_message_from_destination_using_test_listener(destination_name)
    message_headers = received_message[0]
    message_body = json.loads(received_message[1])

    assert message_headers["tshoot-destination"] == destination_name
    assert message_headers["x-dead-letter-routing-key"] == f"DLQ.{source_queue_name}"
    assert message_headers["correlation-id"] == "6e10903e13ddcde54304883e5df713a5"
    assert message_headers["eventType"] == "someType"

    assert message_body["points"] == 300
    assert message_body["account"] == "7cdd43af-7e36-40c2-b7e7-e0e0a62fa328"
    assert message_body["sponsor"] == "3591bfff-3241-46e3-8829-2389d56da04c"


def test_should_not_publish_any_messages_if_connection_drops_when_using_transactions():
    # Base environment setup
    destination_one = f"/queue/no-retrying-destination-one-{uuid4()}"
    *_, queue_name = destination_one.split("/")
    some_correlation_id = uuid.uuid4()
    some_header = {"correlation-id": some_correlation_id}
    some_body = NO_ERRORS_DICT

    # creates destination and publishes to it
    start_processing(destination_one, callback_standard_path, is_testing=True, return_listener=True).close()
    publisher = build_publisher(f"random-publisher-{uuid4()}")

    with pytest.raises(NotConnectedException):
        # transaction with connection errors: everything should be aborted and no messages published
        with do_inside_transaction(publisher):
            publisher.send(some_body, queue=destination_one, headers=some_header)
            publisher.close()  # simulates a closed connection/timeout/broken pipe/etc IN A TRANSACTION
            publisher.send(some_body, queue=destination_one, headers=some_header)

    queue_status = get_destination_metrics_from_broker(queue_name)

    # no messages should have been published ahead
    assert queue_status.number_of_pending_messages == 0


def test_should_publish_many_messages_if_no_connection_problems_happen_when_using_transactions():
    # Base environment setup
    destination_one = f"/queue/no-retrying-destination-one-{uuid4()}"
    *_, queue_name = destination_one.split("/")
    some_correlation_id = uuid.uuid4()
    some_header = {"correlation-id": some_correlation_id}
    some_body = NO_ERRORS_DICT

    # creates destination and publishes to it
    start_processing(destination_one, callback_standard_path, is_testing=True, return_listener=True).close()
    publisher = build_publisher(f"random-publisher-{uuid4()}")

    # no connection errors inside this transaction
    with do_inside_transaction(publisher):
        publisher.send(some_body, queue=destination_one, headers=some_header)
        publisher.send(some_body, queue=destination_one, headers=some_header)

    queue_status = get_destination_metrics_from_broker(queue_name)

    # two messages should have been published (no connection/errors on send)
    assert queue_status.messages_enqueued == 2
    assert queue_status.number_of_pending_messages == 2


def test_should_publish_messages_if_connection_drops_when_not_transactions():
    # Base environment setup
    destination_one = f"/queue/yes-retrying-destination-one-{uuid4()}"
    *_, queue_name = destination_one.split("/")
    some_correlation_id = uuid.uuid4()
    some_header = {"correlation-id": some_correlation_id}
    some_body = NO_ERRORS_DICT

    # creates destination and publishes to it
    start_processing(destination_one, callback_standard_path, is_testing=True, return_listener=True).close()
    publisher = build_publisher(f"random-publisher-{uuid4()}")

    # no transaction
    publisher.send(some_body, queue=destination_one, headers=some_header)
    publisher.close()  # simulates a closed connection/timeout/broken pipe/etc
    publisher.send(some_body, queue=destination_one, headers=some_header)

    # some sleep to give some time for RabbitMQ Console
    sleep(2)
    queue_status = get_destination_metrics_from_broker(queue_name)

    # the two message should have been published due to retry (but no transactions involved)
    assert queue_status.messages_enqueued == 2
    assert queue_status.number_of_pending_messages == 2


@pytest.mark.django_db
def test_should_open_a_new_db_connection_when_previous_connection_is_obsolete_or_unusable(settings):
    # Arrange - listen for db connection created signal with mocked function
    new_db_connection_callback = mock.MagicMock(return_value=None)
    connection_created.connect(new_db_connection_callback)

    # Arrange - settings CONN_MAX_AGE to zero, forcing connection renewal for every new message
    settings.DATABASES["default"]["CONN_MAX_AGE"] = 0

    # Arrange - random destination and fake arbitrary message body
    destination = f"/queue/new-connections-{uuid4()}"
    body = {"key": "value"}
    arbitrary_number_of_msgs = 5

    # Act - start listening to a random destination queue and publishing an arbitrary number of messages to it
    listener = start_processing(
        destination, callback_with_explicit_db_connection_path, is_testing=True, return_listener=True
    )

    with build_publisher(f"random-publisher-{uuid4()}").auto_open_close_connection() as publisher:
        for _ in range(arbitrary_number_of_msgs):
            publisher.send(body, destination)

    sleep(0.5)  # some sleep to give enough time to process the messages

    # Assert - for every new message a new db connection is created
    assert new_db_connection_callback.call_count == arbitrary_number_of_msgs

    # Assert - all threads that have established a db connection, should have closed them as CONN_MAX_AGE == 0
    threads_with_db_connections = [t for t in threading.enumerate() if hasattr(t, "db")]
    assert any(threads_with_db_connections)
    assert all(t.db.connection is None for t in threads_with_db_connections)

    listener.close()


@pytest.mark.django_db
def test_shouldnt_open_a_new_db_connection_when_there_is_one_still_usable(settings):
    # Arrange - listen for db connection created signal with mocked function
    new_db_connection_callback = mock.MagicMock(return_value=None)
    connection_created.connect(new_db_connection_callback)

    # Arrange - settings CONN_MAX_AGE to 86400s or 1 day
    settings.DATABASES["default"]["CONN_MAX_AGE"] = 86400

    # Arrange - random destination and fake arbitrary message body
    destination = f"/queue/no-new-connections-{uuid4()}"
    body = {"key": "value"}
    arbitrary_number_of_msgs = 5

    # Act - start listening random destination queue and publish arbitrary number of messages to it
    listener = start_processing(
        destination, callback_with_explicit_db_connection_path, is_testing=True, return_listener=True
    )

    with build_publisher(f"random-publisher-{uuid4()}").auto_open_close_connection() as publisher:
        for _ in range(arbitrary_number_of_msgs):
            publisher.send(body, destination)

    sleep(0.5)  # some sleep to give enough time to process the messages

    # Assert - only one connection is estabilished
    assert new_db_connection_callback.call_count == 1

    # Assert - all threads that have established a db connection, shouldn't have reset them as CONN_MAX_AGE == 1 day
    threads_with_db_connections = [t for t in threading.enumerate() if hasattr(t, "db")]
    assert any(threads_with_db_connections)
    assert all(t.db.connection is not None for t in threads_with_db_connections)

    listener.close()
