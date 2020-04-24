import json
from uuid import uuid4

from django_stomp.services.consumer import build_listener
from tests.support.helpers import get_currently_active_threads_name


def test_should_clean_up_thread_pool_when_listener_is_deleted():
    listener = build_listener(f"some-destination-{uuid4()}", should_process_msg_on_background=True)

    listener.on_message(headers={"message-id": "123"}, body=json.dumps({"someKey": 1}))

    threads_active_before_delete = get_currently_active_threads_name()

    del listener

    remaining_threads = get_currently_active_threads_name()

    assert len(threads_active_before_delete) != len(remaining_threads)
    assert sorted(threads_active_before_delete) != sorted(remaining_threads)
