import json
import uuid

import pytest
from django_stomp.builder import build_listener
from django_stomp.builder import build_publisher
from django_stomp.execution import send_message_from_one_destination_to_another
from django_stomp.execution import start_processing
from django_stomp.services.consumer import Payload
from pytest_mock import MockFixture
from tests.support.connections_details import consumers_details
from tests.support.message_details import retrieve_message_published
from tests.support.queue_details import current_queue_configuration
from tests.support.subscribers_details import offline_durable_subscribers
from tests.support.topic_details import current_topic_configuration

myself_with_test_callback_standard = "tests.integration.test_execution._test_callback_function_standard"
myself_with_test_callback_nack = "tests.integration.test_execution._test_callback_function_with_nack"
myself_with_test_callback_exception = "tests.integration.test_execution._test_callback_function_with_exception"

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
    queue_status = current_queue_configuration("localhost", queue_name)

    assert queue_status.number_of_pending_messages == 0
    assert queue_status.number_of_consumers == 0
    assert queue_status.messages_enqueued == 1
    assert queue_status.messages_dequeued == 1


test_destination_durable_consumer_one = "/topic/my-test-destination-durable-consumer-one"


def test_should_create_durable_subscriber_and_receive_standby_messages(mocker: MockFixture):
    temp_uuid_listener = str(uuid.uuid4())
    mocker.patch("django_stomp.execution.listener_client_id", temp_uuid_listener)
    mocker.patch("django_stomp.execution.durable_topic_subscription", True)
    # Just to create a durable subscription
    start_processing(test_destination_durable_consumer_one, myself_with_test_callback_standard, is_testing=True)

    # In order to publish sample data
    publisher = build_publisher()
    some_body = {"keyOne": 1, "keyTwo": 2}
    publisher.send(some_body, test_destination_durable_consumer_one, attempt=1)
    publisher.send(some_body, test_destination_durable_consumer_one, attempt=1)
    publisher.send(some_body, test_destination_durable_consumer_one, attempt=1)

    # To recreate a durable subscription
    start_processing(test_destination_durable_consumer_one, myself_with_test_callback_standard, is_testing=True)

    *_, topic_name = test_destination_durable_consumer_one.split("/")
    queue_status = current_topic_configuration("localhost", topic_name)
    assert queue_status.number_of_consumers == 1
    assert queue_status.messages_enqueued == 3
    assert queue_status.messages_dequeued == 3

    all_offline_subscribers = list(offline_durable_subscribers("localhost"))
    for index, subscriber_setup in enumerate(all_offline_subscribers):
        if subscriber_setup.subscriber_id == f"{temp_uuid_listener}-listener":
            assert subscriber_setup.dispatched_counter == 3
            assert subscriber_setup.enqueue_counter == 3
            assert subscriber_setup.dequeue_counter == 3
            break
        assert all_offline_subscribers[index] != all_offline_subscribers[-1]


test_destination_prefetch_consumer_one = "/queue/my-destination-prefetch-consumer-one"


def test_should_configure_prefetch_size_as_one_following_apache_suggestions(mocker: MockFixture):
    """
    See more details here: https://activemq.apache.org/stomp.html

    Specifies the maximum number of pending messages that will be dispatched to the client.
    Once this maximum is reached no more messages are dispatched until the client acknowledges a
    message. Set to a low value > 1 for fair distribution of messages across consumers
    when processing messages can be slow. Note: if your STOMP client is implemented using a dynamic
    scripting language like Ruby, say, then this parameter must be set to 1 as there is no notion of a
    client-side message size to be sized. STOMP does not support a value of 0.
    """
    temp_uuid_listener = str(uuid.uuid4())
    mocker.patch("django_stomp.execution.listener_client_id", temp_uuid_listener)

    start_processing(
        test_destination_prefetch_consumer_one,
        myself_with_test_callback_standard,
        is_testing=True,
        testing_disconnect=False,
    )

    consumers = list(consumers_details("localhost", f"{temp_uuid_listener}-listener"))

    for index, consumer_status in enumerate(consumers):
        if consumer_status.destination_name in test_destination_prefetch_consumer_one:
            assert consumer_status.prefetch == 1
            assert consumer_status.max_pending == 0
            break
        assert consumers[index] != consumers[-1]


test_destination_dlq_one = f"/queue/my-destination-dql-one-{uuid.uuid4()}"


def test_should_publish_to_dql_due_to_explicit_nack():
    # In order to publish sample data
    publisher = build_publisher()
    some_body = {"keyOne": 1, "keyTwo": 2}
    publisher.send(some_body, test_destination_dlq_one, attempt=1)

    start_processing(test_destination_dlq_one, myself_with_test_callback_nack, is_testing=True)

    *_, queue_name = test_destination_dlq_one.split("/")
    dlq_queue_name = f"DLQ.{queue_name}"
    queue_status = current_queue_configuration("localhost", dlq_queue_name)

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
    queue_status = current_queue_configuration("localhost", dlq_queue_name)

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

    message_status = retrieve_message_published(some_destination)

    assert message_status.properties.get("tshoot-destination")
    assert message_status.properties["tshoot-destination"] == some_destination


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
    queue_status = current_queue_configuration("localhost", queue_name)
    assert queue_status.number_of_pending_messages == 0
    assert queue_status.number_of_consumers == 0
    assert queue_status.messages_enqueued == 1
    assert queue_status.messages_dequeued == 1

    *_, queue_name = some_target_destination.split("/")
    queue_status = current_queue_configuration("localhost", queue_name)
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


def _test_callback_function_standard(payload: Payload):
    # Should dequeue the message
    payload.ack()


def _test_callback_function_with_nack(payload: Payload):
    payload.nack()


def _test_callback_function_with_exception(payload: Payload):
    raise Exception("Lambe Sal")
