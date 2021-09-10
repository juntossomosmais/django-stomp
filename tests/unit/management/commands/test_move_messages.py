from io import StringIO

import pytest
from django.core.management import CommandError
from django.core.management import call_command
from pytest_mock import MockFixture


@pytest.fixture
def mock_send_message_from_one_destination_to_another(mocker: MockFixture):
    return mocker.patch("django_stomp.management.commands.move_messages.send_message_from_one_destination_to_another")


def test_should_call_logic_to_send_one_destination_to_another(mock_send_message_from_one_destination_to_another):
    out = StringIO()
    fake_source = "/queue/your-source"
    fake_target = "/queue/your-target"

    call_command("move_messages", fake_source, fake_target, stdout=out)

    assert "Calling internal service to send messages to target" in out.getvalue()
    mock_send_message_from_one_destination_to_another.assert_called_with(
        fake_source, fake_target, custom_stomp_server_host=None, custom_stomp_server_port=None
    )


def test_should_raise_error_if_essential_parameters_are_missing(mock_send_message_from_one_destination_to_another):
    fake_source = "/queue/your-source"

    with pytest.raises(CommandError) as e:
        call_command("move_messages")

    assert e.value.args[0] == "Error: the following arguments are required: source_destination, target_destination"

    with pytest.raises(CommandError) as e:
        call_command("move_messages", fake_source)

    assert e.value.args[0] == "Error: the following arguments are required: target_destination"

    mock_send_message_from_one_destination_to_another.assert_not_called()


def test_should_call_logic_to_send_one_destination_to_another_given_custom_broker(
    mock_send_message_from_one_destination_to_another,
):
    out = StringIO()
    fake_source = "/queue/your-source"
    fake_target = "/queue/your-target"
    fake_custom_broker_host = "jafar-host"
    fake_custom_broker_port = "61614"

    call_command(
        "move_messages", fake_source, fake_target, fake_custom_broker_host, fake_custom_broker_port, stdout=out
    )

    assert "Calling internal service to send messages to target" in out.getvalue()
    mock_send_message_from_one_destination_to_another.assert_called_with(
        fake_source,
        fake_target,
        custom_stomp_server_host=fake_custom_broker_host,
        custom_stomp_server_port=int(fake_custom_broker_port),
    )


def test_should_raise_error_given_custom_port_is_not_informed_to_use_custom_broker(
    mock_send_message_from_one_destination_to_another,
):
    out = StringIO()
    fake_source = "/queue/your-source"
    fake_target = "/queue/your-target"
    fake_custom_broker_host = "jafar-host"

    with pytest.raises(CommandError) as e:
        call_command("move_messages", fake_source, fake_target, fake_custom_broker_host, stdout=out)

    assert e.value.args[0] == "You should provide broker_port_for_source_destination option as well"

    mock_send_message_from_one_destination_to_another.assert_not_called()
