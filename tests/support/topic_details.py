from dataclasses import dataclass
from time import sleep

import requests

from parsel import Selector


@dataclass(frozen=True)
class CurrentTopicStatus:
    number_of_consumers: int
    messages_enqueued: int
    messages_dequeued: int


def current_topic_configuration(host, topic_name) -> CurrentTopicStatus:
    sleep(1)
    result = requests.get(f"http://{host}:8161/admin/topics.jsp", auth=("admin", "admin"))
    selector = Selector(text=str(result.content))

    all_topics = selector.xpath('//*[@id="topics"]/tbody/tr').getall()

    assert len(all_topics) > 0
    for index, queue_details in enumerate(all_topics):
        topic_details_as_selector = Selector(text=queue_details)
        if topic_name in topic_details_as_selector.css("td a::attr(href)").get():
            number_of_consumers = int(topic_details_as_selector.css("td + td::text").get())
            messages_enqueued = int(topic_details_as_selector.css("td + td + td::text").get())
            messages_dequeued = int(topic_details_as_selector.css("td + td + td + td::text").get())
            return CurrentTopicStatus(number_of_consumers, messages_enqueued, messages_dequeued)
        if all_topics[index] == all_topics[-1]:
            raise Exception