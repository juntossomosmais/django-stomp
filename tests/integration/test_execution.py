import json
import logging
import re
import uuid
from time import sleep

import pytest
import trio
from django_stomp.builder import build_listener
from django_stomp.builder import build_publisher
from django_stomp.execution import send_message_from_one_destination_to_another
from django_stomp.execution import start_processing
from django_stomp.services.consumer import Payload
from pytest_mock import MockFixture
from tests.support import rabbitmq
from tests.support.activemq.connections_details import consumers_details
from tests.support.activemq.message_details import retrieve_message_published
from tests.support.activemq.queue_details import current_queue_configuration
from tests.support.activemq.subscribers_details import offline_durable_subscribers
from tests.support.activemq.topic_details import current_topic_configuration

myself_with_test_callback_standard = "tests.integration.test_execution._test_callback_function_standard"
myself_with_test_callback_nack = "tests.integration.test_execution._test_callback_function_with_nack"
myself_with_test_callback_exception = "tests.integration.test_execution._test_callback_function_with_exception"
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
    mocker.patch("django_stomp.execution.listener_client_id", temp_uuid_listener)
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
    mocker.patch("django_stomp.execution.listener_client_id", listener_id)
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
    publisher = build_publisher()
    some_body = {"keyOne": 1, "keyTwo": 2}
    publisher.send(some_body, test_destination_dlq_one, attempt=1)

    start_processing(test_destination_dlq_one, myself_with_test_callback_nack, is_testing=True)

    *_, queue_name = test_destination_dlq_one.split("/")
    dlq_queue_name = f"DLQ.{queue_name}"
    queue_status = current_queue_configuration(dlq_queue_name)

    assert queue_status.number_of_pending_messages == 1
    assert queue_status.number_of_consumers == 0
    assert queue_status.messages_enqueued == 1
    assert queue_status.messages_dequeued == 0


test_destination_dlq_two = f"/queue/my-destination-dql-two-{uuid.uuid4()}"


def test_should_publish_to_dql_due_to_implicit_nack_given_internal_callback_exception():
    # In order to publish sample data
    publisher = build_publisher()
    some_body = {"keyOne": 1, "keyTwo": 2}
    publisher.send(some_body, test_destination_dlq_two, attempt=1)

    with pytest.raises(Exception) as e:
        start_processing(test_destination_dlq_two, myself_with_test_callback_exception, is_testing=True)

    *_, queue_name = test_destination_dlq_two.split("/")
    dlq_queue_name = f"DLQ.{queue_name}"
    queue_status = current_queue_configuration(dlq_queue_name)

    assert queue_status.number_of_pending_messages == 1
    assert queue_status.number_of_consumers == 0
    assert queue_status.messages_enqueued == 1
    assert queue_status.messages_dequeued == 0


def test_should_save_tshoot_properties_on_header():
    some_destination = f"tshoot-header-{uuid.uuid4()}"

    # In order to publish sample data
    publisher = build_publisher()
    some_body = {"keyOne": 1, "keyTwo": 2}
    publisher.send(some_body, some_destination, attempt=1)

    try:
        message_status = retrieve_message_published(some_destination)

        assert message_status.properties.get("tshoot-destination")
        assert message_status.properties["tshoot-destination"] == some_destination
    except Exception:
        message_status = rabbitmq.retrieve_message_published(some_destination)

        assert message_status.properties["headers"].get("tshoot-destination")
        assert message_status.properties["headers"]["tshoot-destination"] == some_destination


@pytest.mark.skip(reason="This behaves not as expected, but when used as Django command, it does")
def test_should_send_to_another_destination():
    some_source_destination = f"/queue/source-{uuid.uuid4()}"
    some_target_destination = f"/queue/target-{uuid.uuid4()}"

    # In order to publish sample data
    with build_publisher().auto_open_close_connection() as publisher:
        some_body = {"keyOne": 1, "keyTwo": 2}
        some_headers = {"some-header-1": 1, "some-header-2": 2}
        publisher.send(some_body, some_source_destination, some_headers, attempt=1)

    send_message_from_one_destination_to_another(some_source_destination, some_target_destination, is_testing=True)

    *_, queue_name = some_source_destination.split("/")
    queue_status = current_queue_configuration(queue_name)
    assert queue_status.number_of_pending_messages == 0
    assert queue_status.number_of_consumers == 0
    assert queue_status.messages_enqueued == 1
    assert queue_status.messages_dequeued == 1

    *_, queue_name = some_target_destination.split("/")
    queue_status = current_queue_configuration(queue_name)
    assert queue_status.number_of_pending_messages == 1
    assert queue_status.number_of_consumers == 0
    assert queue_status.messages_enqueued == 1
    assert queue_status.messages_dequeued == 0

    message_status = retrieve_message_published(queue_name)

    keys = list(some_headers.keys())
    assert len(keys) == 2
    assert int(message_status.properties[keys[0]]) == some_headers[keys[0]]
    assert int(message_status.properties[keys[1]]) == some_headers[keys[1]]
    assert message_status.details == some_body


def test_should_use_heartbeat_and_then_lost_connection_due_message_takes_longer_than_heartbeat(caplog, settings):
    """
    The listener in this code has an, arguably broken, message handler (see
    _test_callback_function_with_sleep_three_seconds function) which takes longer to process than the
    heartbeat time of 1 second (1000); resulting in a heartbeat timeout when
    a message is received, and a subsequent disconnect.

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

    settings.STOMP_OUTGOING_HEARTBIT = 1000
    settings.STOMP_INCOMING_HEARTBIT = 1000
    start_processing(some_destination, myself_with_test_callback_sleep_three_seconds, is_testing=True)
    sleep(1)

    assert any(
        re.compile(
            f"Received frame.+eart-beat.+{settings.STOMP_OUTGOING_HEARTBIT},{settings.STOMP_INCOMING_HEARTBIT}"
        ).match(m)
        for m in caplog.messages
    )
    assert any(re.compile("Sending a heartbeat message at [0-9.]+").match(message) for message in caplog.messages)
    assert any(
        re.compile("Heartbeat timeout: diff_receive=[0-9.]+, time=[0-9.]+, lastrec=[0-9.]+").match(message)
        for message in caplog.messages
    )
    assert any(re.compile("Lost connection, unable to send heartbeat").match(message) for message in caplog.messages)


def _test_callback_function_standard(payload: Payload):
    # Should dequeue the message
    payload.ack()


def _test_callback_function_with_nack(payload: Payload):
    payload.nack()


def _test_callback_function_with_exception(payload: Payload):
    raise Exception("Lambe Sal")


def _test_callback_function_with_sleep_three_seconds(payload: Payload):
    sleep(3)
    payload.ack()
