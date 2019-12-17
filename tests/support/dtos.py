from dataclasses import dataclass
from typing import Dict
from typing import Optional


@dataclass(frozen=True)
class CurrentDestinationStatus:
    number_of_pending_messages: Optional[int]
    number_of_consumers: int
    messages_enqueued: int
    messages_dequeued: int


@dataclass(frozen=True)
class ConsumerStatus:
    address_to_destination_details: Optional[str]
    destination_name: str
    session_id: Optional[int]
    enqueues: Optional[int]
    dequeues: Optional[int]
    dispatched: Optional[int]
    dispatched_queue: Optional[int]
    prefetch: int
    max_pending: Optional[int]
    exclusive: bool
    retroactive: Optional[bool]


@dataclass(frozen=True)
class MessageStatus:
    message_id: Optional[str]
    details: Dict
    persistent: Optional[bool]
    correlation_id: str
    properties: Optional[Dict]


@dataclass(frozen=True)
class SubscriberSetup:
    address_to_subscriber_details: str
    subscriber_id: str
    destination: str
    pending_queue_size: int
    dispatched_queue_size: int
    dispatched_counter: int
    enqueue_counter: int
    dequeue_counter: int
