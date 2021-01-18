from django.conf import settings as django_settings
from django.core.management.base import BaseCommand
from django.utils.module_loading import import_string

from django_stomp.api.conf_reader import parse_settings
from django_stomp.api.stomp11.subscribe import subscribe_forever
from django_stomp.exceptions import DjangoStompIncorrectUse


class Command(BaseCommand):
    help = "Cleans a destination by acking all messages on it!"

    def add_arguments(self, parser):
        parser.add_argument("destination_to_clean", type=str, help="Destination to be cleaned from all messages")

    def handle(self, *args, **options):
        self.stdout.write(f"Provided parameters: {options}")

        callback_path = "django_stomp.callbacks.callback_for_cleaning_queues"
        destination_to_clean = options.get("destination_to_clean")

        if not destination_to_clean:
            raise DjangoStompIncorrectUse("No destination_to_clean was supplied! Nothing to clean!")

        self.stdout.write("Using django as the settings provider...")
        settings = parse_settings(destination_to_clean, django_settings)

        self.stdout.write("Locating the subscription's callback...")
        callback_function = import_string(callback_path)

        self.stdout.write("Subscribing forever...")
        subscribe_forever(callback_function, settings)
