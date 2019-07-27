import json
from dataclasses import dataclass
from time import sleep
from typing import Dict

import requests

from parsel import Selector


@dataclass(frozen=True)
class MessageStatus:
    message_id: str
    details: Dict
    persistent: bool
    correlation_id: str


def retrieve_message_published(host, destination_name) -> MessageStatus:
    sleep(1)
    address = f"http://{host}:8161/admin/browse.jsp?JMSDestination={destination_name}"
    result = requests.get(address, auth=("admin", "admin"))
    selector = Selector(text=str(result.content))

    all_messages = selector.xpath('//*[@id="messages"]/tbody/tr').getall()

    assert len(all_messages) > 0

    for index, message_details in enumerate(all_messages):
        message_details_as_selector = Selector(text=message_details)
        message_id_request_path = message_details_as_selector.css("td a::attr(href)").get()
        address_to_message = f"http://{host}:8161/admin/{message_id_request_path}"
        result_all_message_details = requests.get(address_to_message, auth=("admin", "admin"))
        selector_all_message_details = Selector(text=str(result_all_message_details.content))
        return _process_message_details(selector_all_message_details)


def _process_message_details(selector_message_details) -> MessageStatus:
    message_id = selector_message_details.css("table#header td + td::text").get()
    details = json.loads(selector_message_details.css("pre::text").get())
    css_persistent_location = "table#header tr + tr + tr + tr + tr + tr + tr td + td::text"
    persistent = "persistent" in selector_message_details.css(css_persistent_location).get().lower()
    correlation_id = selector_message_details.css("table#header tr + tr + tr td + td::text").get()

    return MessageStatus(message_id, details, persistent, correlation_id)