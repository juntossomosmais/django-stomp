import json
from time import sleep

import requests

from parsel import Selector
from tests.support.dtos import MessageStatus


def retrieve_message_published(destination_name, host="localhost") -> MessageStatus:
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

    properties = {}
    all_configured_properties = selector_message_details.css("table#properties td").getall()
    for index, configured_property in enumerate(all_configured_properties):
        configured_property_as_selector = Selector(text=configured_property)
        key = configured_property_as_selector.css("td[class='label']::text").get()
        if key:
            value = Selector(text=all_configured_properties[index + 1]).css("td::text").get()
            properties.update({key: value})

    return MessageStatus(message_id, details, persistent, correlation_id, properties)
