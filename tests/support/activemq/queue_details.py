from dataclasses import dataclass
from time import sleep

import requests

from parsel import Selector


@dataclass(frozen=True)
class CurrentQueueStatus:
    number_of_pending_messages: int
    number_of_consumers: int
    messages_enqueued: int
    messages_dequeued: int


def current_queue_configuration(queue_name, host="localhost") -> CurrentQueueStatus:
    sleep(1)
    result = requests.get(f"http://{host}:8161/admin/queues.jsp", auth=("admin", "admin"))
    selector = Selector(text=str(result.content))

    all_queues = selector.xpath('//*[@id="queues"]/tbody/tr').getall()

    assert len(all_queues) > 0
    for index, queue_details in enumerate(all_queues):
        queue_details_as_selector = Selector(text=queue_details)
        if queue_name in queue_details_as_selector.css("td a::attr(href)").get():
            n_of_pending_messages = int(queue_details_as_selector.css("td + td::text").get())
            n_of_consumers = int(queue_details_as_selector.css("td + td + td::text").get())
            m_enqueued = int(queue_details_as_selector.css("td + td + td + td::text").get())
            m_dequeued = int(queue_details_as_selector.css("td + td + td + td + td::text").get())
            return CurrentQueueStatus(n_of_pending_messages, n_of_consumers, m_enqueued, m_dequeued)
        if all_queues[index] == all_queues[-1]:
            raise Exception
