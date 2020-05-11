import uuid

import pytest
from django.core.management import call_command

from django_stomp.builder import build_publisher


@pytest.mark.skip("This is done manually for now")
def test_should_send_from_one_broker_to_another(settings):
    fake_source = "/queue/jafar-destination"
    fake_target = "/queue/another-jafar"

    def _to_publish_to_source_broker():
        publisher_name_to_move = f"iago-{uuid.uuid4()}"
        with build_publisher(publisher_name_to_move).auto_open_close_connection() as publisher:
            with publisher.do_inside_transaction():
                sample_body = {"igu": "brick-breaker", "is_enabled": True}
                headers = {"custom-1": 1234, "custom-2": "aladdin"}
                publisher.send(sample_body, fake_source, headers)

    def _to_move_the_message_and_evaluate_result():
        fake_custom_broker_host = "localhost"
        fake_custom_broker_port = "61614"

        call_command("move_messages", fake_source, fake_target, fake_custom_broker_host, fake_custom_broker_port)

    settings.STOMP_SERVER_PORT = 61614
    _to_publish_to_source_broker()
    settings.STOMP_SERVER_PORT = 61613
    _to_move_the_message_and_evaluate_result()
