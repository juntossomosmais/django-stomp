from django.conf import settings as django_settings
from django.core.management.base import BaseCommand
from django.utils.module_loading import import_string

from django_stomp.api.conf_reader.django import parse_settings
from django_stomp.api.subscribe.stomp11.subscribe import subscribe_forever


class Command(BaseCommand):
    help = "Subscribes to a destination using STOMP 1.1 protocol version."

    def add_arguments(self, parser):
        parser.add_argument("destination", type=str, help="Source destination used to consume messages")
        parser.add_argument(
            "callback_path",
            type=str,
            help="Entire module path with its function to process messages from source destination",
        )

    def handle(self, *args, **options):
        self.stdout.write(f"Provided parameters: {options}")
        destination = options["source_destination"]
        callback_path = options["callback_function"]

        self.stdout.write("Using django as the settings provider...")
        settings = parse_settings(destination, django_settings)

        self.stdout.write("Locating the subscription's callback...")
        callback_function = import_string(callback_path)

        self.stdout.write("Subscribing forever...")
        subscribe_forever(callback_function, settings)
