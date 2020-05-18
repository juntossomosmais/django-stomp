from time import sleep
from typing import Generator

import requests

from parsel import Selector
from tests.support.dtos import SubscriberSetup


def offline_durable_subscribers(host) -> Generator[SubscriberSetup, None, None]:
    sleep(1)
    result = requests.get(f"http://{host}:8161/admin/subscribers.jsp", auth=("admin", "admin"))
    selector = Selector(text=str(result.content))

    all_offline_subscribers = (
        selector.xpath("//h2[contains(text(),'Offline Durable Topic Subscribers')]/following-sibling::table")[0]
        .css("table tbody tr")
        .getall()
    )

    for index, column_details in enumerate(all_offline_subscribers):
        column_details_as_selector = Selector(text=column_details)
        client_id_request_path = column_details_as_selector.css("td a::attr(href)").get()
        address_to_subscriber_details = f"http://{host}:8161/admin/{client_id_request_path}"
        subscriber_id = client_id_request_path.split("connectionID=")[1]
        destination = column_details_as_selector.css("td:nth-child(4) span::text").getall()[1]
        pending_queue_size = int(column_details_as_selector.css("td:nth-child(6)::text").get())
        dispatched_queue_size = int(column_details_as_selector.css("td:nth-child(7)::text").get())
        dispatched_counter = int(column_details_as_selector.css("td:nth-child(8)::text").get())
        enqueue_counter = int(column_details_as_selector.css("td:nth-child(9)::text").get())
        dequeue_counter = int(column_details_as_selector.css("td:nth-child(10)::text").get())
        yield SubscriberSetup(
            address_to_subscriber_details,
            subscriber_id,
            destination,
            pending_queue_size,
            dispatched_queue_size,
            dispatched_counter,
            enqueue_counter,
            dequeue_counter,
        )
