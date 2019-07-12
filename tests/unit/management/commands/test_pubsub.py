from io import StringIO

from django.core.management import call_command
from pytest_mock import MockFixture


def test_should_call_start_processing(mocker: MockFixture):
    mock_start_processing = mocker.patch("django_stomp.management.commands.pubsub.start_processing")
    fake_queue = "/queue/your-queue"
    fake_function = "your_python_module.your_function"
    out = StringIO()

    call_command("pubsub", fake_queue, fake_function, stdout=out)

    assert not out.getvalue()
    mock_start_processing.assert_called_with(queue=fake_queue, callback_str=fake_function)
