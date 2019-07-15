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
    all_queues = selector.xpath('//*[@id="queues"]/tbody/tr').getall()

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


test_destination_durable_consumer_one = "/topic/my-test-destination-durable-consumer-one"
myself_with_test_callback_four = "tests.integration.test_execution._test_callback_function_four"


def test_should_create_durable_subscriber_and_receive_standby_messages(mocker: MockFixture):
    temp_uuid_listener = str(uuid.uuid4())
    mocker.patch("django_stomp.execution.listener_client_id", temp_uuid_listener)
    mocker.patch("django_stomp.execution.durable_topic_subscription", True)
    # Just to create a durable subscription
    start_processing(test_destination_durable_consumer_one, myself_with_test_callback_four, is_testing=True)

    # In order to publish sample data
    publisher = build_publisher()
    some_body = {"keyOne": 1, "keyTwo": 2}
    publisher.send(some_body, test_destination_durable_consumer_one, attempt=1)
    publisher.send(some_body, test_destination_durable_consumer_one, attempt=1)
    publisher.send(some_body, test_destination_durable_consumer_one, attempt=1)

    # To recreate a durable subscription
    start_processing(test_destination_durable_consumer_one, myself_with_test_callback_four, is_testing=True)

    # Logic to assert if everything is OK
    result = requests.get("http://localhost:8161/admin/topics.jsp", auth=("admin", "admin"))
    selector = Selector(text=str(result.content))

    *_, destination_name = test_destination_durable_consumer_one.split("/")
    all_topics = selector.xpath('//*[@id="topics"]/tbody/tr').getall()

    assert len(all_topics) > 0
    for index, destination_details in enumerate(all_topics):
        destination_details_as_selector = Selector(text=destination_details)
        if destination_name in destination_details_as_selector.css("td a::text").get():
            number_of_consumers = int(destination_details_as_selector.css("td + td::text").get())
            messages_enqueued = int(destination_details_as_selector.css("td + td + td::text").get())
            messages_dequeued = int(destination_details_as_selector.css("td + td + td + td::text").get())
            assert number_of_consumers == 1
            assert messages_enqueued == 3
            assert messages_dequeued == 3
            break
        assert all_topics[index] != all_topics[-1]

    result = requests.get("http://localhost:8161/admin/subscribers.jsp", auth=("admin", "admin"))
    selector = Selector(text=str(result.content))

    all_offline_subscribers = (
        selector.xpath("//h2[contains(text(),'Offline Durable Topic Subscribers')]/following-sibling::table")[0]
        .css("table tbody tr")
        .getall()
    )

    assert len(all_offline_subscribers) > 0
    for index, column_details in enumerate(all_offline_subscribers):
        column_details_as_selector = Selector(text=column_details)
        if f"{temp_uuid_listener}-listener" in column_details_as_selector.css("td a[href]").get():
            dispatched_counter = int(column_details_as_selector.css("td:nth-child(8)::text").get())
            enqueue_counter = int(column_details_as_selector.css("td:nth-child(9)::text").get())
            dequeue_counter = int(column_details_as_selector.css("td:nth-child(10)::text").get())
            assert dispatched_counter == 3
            assert enqueue_counter == 3
            assert dequeue_counter == 3
            break
        assert all_topics[index] != all_topics[-1]


def _test_callback_function_four(payload: Payload):
    # Should dequeue the message
    payload.ack()


test_destination_prefetch_consumer_one = "/queue/my-destination-prefetch-consumer-one"
myself_with_test_callback_five = "tests.integration.test_execution._test_callback_function_five"


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
        myself_with_test_callback_five,
        is_testing=True,
        testing_disconnect=False,
    )

    params = {"connectionID": f"{temp_uuid_listener}-listener"}
    result = requests.get("http://localhost:8161/admin/connection.jsp", params=params, auth=("admin", "admin"))
    selector = Selector(text=str(result.content))

    dirty_prefetch_size_value = selector.css("table#messages")[0].css("tbody td::text")[7].get()
    prefetch_size_value = int(dirty_prefetch_size_value.replace("\\", "").replace("n", "").replace("t", ""))
    assert prefetch_size_value == 1


def _test_callback_function_five(payload: Payload):
    # Should dequeue the message
    payload.ack()
