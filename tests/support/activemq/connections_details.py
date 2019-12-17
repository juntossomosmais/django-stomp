from time import sleep
from typing import Generator

import requests

from django_stomp.helpers import eval_str_as_boolean
from parsel import Selector
from tests.support.dtos import ConsumerStatus


def consumers_details(connection_id, host="localhost") -> Generator[ConsumerStatus, None, None]:
    sleep(1)

    params = {"connectionID": connection_id}
    result = requests.get(f"http://{host}:8161/admin/connection.jsp", params=params, auth=("admin", "admin"))
    selector = Selector(text=str(result.content))

    consumers_table = selector.xpath('//*[@id="messages"]/tbody/tr').getall()

    assert len(consumers_table) > 0
    for index, consumer_details in enumerate(consumers_table):
        consumer_details_as_selector = Selector(text=consumer_details)
        destination_request_path = consumer_details_as_selector.css("td a::attr(href)").get()

        address_to_destination_details = f"http://{host}:8161/admin/{destination_request_path}"
        destination_name = destination_request_path.split("Destination=")[1]
        session_id = int(consumer_details_as_selector.css("td + td::text").get())
        enqueues = int(consumer_details_as_selector.css("td + td + td::text").get())
        dequeues = int(consumer_details_as_selector.css("td + td + td + td::text").get())
        dispatched = int(consumer_details_as_selector.css("td + td + td + td + td::text").get())
        dispatched_queue = int(consumer_details_as_selector.css("td + td + td + td + td + td::text").get())

        last_two_columns = consumer_details_as_selector.css("td + td + td + td + td + td+ td + td::text").getall()

        prefetch = int(last_two_columns[0].replace("\\", "").replace("t", "").replace("n", ""))
        max_pending = int(last_two_columns[1].replace("\\", "").replace("t", "").replace("n", ""))
        exclusive = eval_str_as_boolean(last_two_columns[2].replace("\\", "").replace("t", "").replace("n", ""))
        retroactive = eval_str_as_boolean(last_two_columns[3].replace("\\", "").replace("t", "").replace("n", ""))

        yield ConsumerStatus(
            address_to_destination_details,
            destination_name,
            session_id,
            enqueues,
            dequeues,
            dispatched,
            dispatched_queue,
            prefetch,
            max_pending,
            exclusive,
            retroactive,
        )
