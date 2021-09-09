import json
from uuid import uuid4

from django_stomp import builder
from django_stomp.services.consumer import StompFrame
from django_stomp.services.consumer import build_listener
from tests.support.helpers import get_active_threads_name_with_prefix


def test_should_create_at_most_the_defined_number_of_workers(mocker):
    mocker.patch("django_stomp.services.consumer.STOMP_PROCESS_MSG_WORKERS", 3)

    listener = build_listener(f"some-destination-{uuid4()}", should_process_msg_on_background=True)

    fake_frame = StompFrame(cmd="FAKE_CMD", headers={"message-id": "123"}, body=json.dumps({"someKey": 1}))

    listener.on_message(fake_frame)
    listener.on_message(fake_frame)
    listener.on_message(fake_frame)
    listener.on_message(fake_frame)

    workers_threads = get_active_threads_name_with_prefix(listener._subscription_id)
    assert len(workers_threads) == 3  # 3 workers
    listener.shutdown_worker_pool()


def test_should_clean_up_worker_pool():
    listener = build_listener(f"some-destination-{uuid4()}", should_process_msg_on_background=True)

    fake_frame = StompFrame(cmd="FAKE_CMD", headers={"message-id": "123"}, body=json.dumps({"someKey": 1}))

    listener.on_message(fake_frame)

    workers_threads_before_pool_shutdown = get_active_threads_name_with_prefix(listener._subscription_id)
    assert len(workers_threads_before_pool_shutdown) == 1  # only one worker

    listener.shutdown_worker_pool()

    workers_threads_after_pool_shutdown = get_active_threads_name_with_prefix(listener._subscription_id)
    assert len(workers_threads_after_pool_shutdown) == 0  # no active worker thread


def test_should_still_process_message_if_worker_pool_was_explicitly_shutdown():
    listener = build_listener(f"some-destination-{uuid4()}", should_process_msg_on_background=True)

    fake_frame = StompFrame(cmd="FAKE_CMD", headers={"message-id": "123"}, body=json.dumps({"someKey": 1}))

    listener.on_message(fake_frame)

    workers_threads_before_pool_shutdown = get_active_threads_name_with_prefix(listener._subscription_id)
    assert len(workers_threads_before_pool_shutdown) == 1  # only one worker
    listener.shutdown_worker_pool()

    workers_threads_after_pool_shutdown = get_active_threads_name_with_prefix(listener._subscription_id)
    assert len(workers_threads_after_pool_shutdown) == 0  # no active worker thread

    listener.on_message(fake_frame)

    workers_threads_before_pool_shutdown = get_active_threads_name_with_prefix(listener._subscription_id)
    assert len(workers_threads_before_pool_shutdown) == 1  # only one worker

    listener.shutdown_worker_pool()


def test_should_have_only_one_django_stomp_listener_even_if_set_listener_is_called_multiple_times():
    # Arrange - build listener to some arbirtrary queue
    django_stomp_listener = builder.build_listener(f"some-destination-{uuid4()}")

    # Act - in sucession, multiples _set_listener call to trigger _connection.set_listener
    django_stomp_listener._set_listener()
    django_stomp_listener._set_listener()
    django_stomp_listener._set_listener()
    django_stomp_listener._set_listener()
    django_stomp_listener._set_listener()

    # Assert - it has two listeners (protocol-listener, stomp.py defined and the one defined by django-stomp)
    assert len(django_stomp_listener._connection.transport.listeners) == 2
    assert django_stomp_listener._connection.get_listener("protocol-listener") is not None

    django_stomp_listener_id = django_stomp_listener._listener_id
    assert django_stomp_listener._connection.get_listener(django_stomp_listener_id) is not None
