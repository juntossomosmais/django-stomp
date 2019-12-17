import json
import uuid
from datetime import datetime

import pytest
from django_stomp.builder import build_publisher
from django_stomp.services.consumer import Acknowledgements
from stomp.listener import TestListener

test_destination = "/queue/my-test-destination"


@pytest.fixture
def setup_publisher_and_test_listener():
    subscription_id = str(uuid.uuid4())
    test_listener = TestListener()
    publisher = build_publisher()
    publisher.connection.set_listener(str(uuid.uuid4()), test_listener)
    # Start is needed to make `connection.subscribe` work properly
    publisher.start()
    publisher.connection.subscribe(destination=test_destination, id=subscription_id, ack=Acknowledgements.AUTO.value)

    yield publisher, (test_listener, subscription_id)

    publisher.close()


def test_should_publish_message_on_destination(setup_publisher_and_test_listener):
    publisher, listener_configuration = setup_publisher_and_test_listener
    listener, subscription_id = listener_configuration

    some_correlation_id = uuid.uuid4()
    some_header = {"correlation-id": some_correlation_id}
    some_body = {"keyOne": 1, "keyTwo": 2}

    publisher.send(some_body, test_destination, headers=some_header, attempt=1)

    listener.wait_for_message()
    received_message = listener.get_latest_message()

    assert received_message is not None
    received_header = received_message[0]
    assert received_header["correlation-id"] == str(some_correlation_id)
    assert received_header["destination"] == test_destination
    assert received_header["subscription"] == subscription_id
    assert received_header["message-id"] is not None
    assert received_header["content-type"] == "application/json;charset=utf-8"
    assert received_header["persistent"] == "true"
    received_body = json.loads(received_message[1])
    assert received_body == some_body
    #### ActiveMQ has it by default
    # assert received_header["priority"] == "4"
    #### ActiveMQ has it by default
    # timestamp_value = int(received_header["timestamp"])
    # converted_timestamp = datetime.utcfromtimestamp(timestamp_value / 1000.0)
    # assert converted_timestamp.date() == datetime.today().date()
