import os
import signal
from unittest import mock
from uuid import uuid4

from django_stomp.execution import start_processing
from tests.support.callbacks_for_tests import callback_move_and_ack_path


def mocked_os_kill(*args, **kwargs) -> None:
    os.kill(os.getpid(), signal.SIGTERM)


@mock.patch("django_stomp.execution.get_listener_client_id")
def test_should_gracefully_shutdown_pubsub_command(mocked_get_listener_client_id: mock.MagicMock):
    destination_one = f"/queue/my-test-destination-one-{uuid4()}"
    destination_two = f"/queue/my-test-destination-two-{uuid4()}"

    mocked_get_listener_client_id.side_effect = mocked_os_kill

    start_processing(
        destination_one,
        callback_move_and_ack_path,
        param_to_callback=destination_two,
        is_testing=True,
        return_listener=True,
    )
