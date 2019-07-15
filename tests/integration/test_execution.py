import json
import uuid

import requests

from django_stomp.builder import build_listener
from django_stomp.builder import build_publisher
from django_stomp.execution import start_processing
from django_stomp.services.consumer import Payload
from parsel import Selector
from pytest_mock import MockFixture

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
myself_with_test_callback_three = "tests.integration.test_execution._test_callback_function_three"


def test_should_consume_message_and_dequeue_it_using_ack():
    # In order to publish sample data
    publisher = build_publisher()
    some_body = {"keyOne": 1, "keyTwo": 2}
    publisher.send(some_body, test_destination_consumer_one, attempt=1)

    start_processing(test_destination_consumer_one, myself_with_test_callback_three, is_testing=True)

    result = requests.get("http://localhost:8161/admin/queues.jsp", auth=("admin", "admin"))
    selector = Selector(text=str(result.content))

    *_, queue_name = test_destination_consumer_one.split("/")
    all_queues = selector.xpath('//*[@id="queues"]/tbody').getall()

    assert len(all_queues) > 0
    for index, queue_details in enumerate(all_queues):
        queue_details_as_selector = Selector(text=queue_details)
        if queue_name in queue_details_as_selector.css("td a::text").get():
            number_of_pending_messages = int(queue_details_as_selector.css("td + td::text").get())
            messages_dequeued = int(queue_details_as_selector.css("td + td + td + td + td::text").get())
            assert number_of_pending_messages == 0
            assert messages_dequeued == 1
            break
        if all_queues[index] == all_queues[-1]:
            raise Exception


def _test_callback_function_three(payload: Payload):
    # Should dequeue the message
    payload.ack()
