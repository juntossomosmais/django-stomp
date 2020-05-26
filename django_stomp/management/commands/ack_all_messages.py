from django.core.management.base import BaseCommand
from django_stomp.exceptions import DjangoStompIncorrectUse
from django_stomp.execution import clean_messages_on_destination_by_acking


class Command(BaseCommand):
    help = "Cleans a destination by acking all messages on it!"

    def add_arguments(self, parser):
        parser.add_argument("destination_to_clean", type=str, help="Destination to be cleaned from all messages")

    def handle(self, *args, **options):
        self.stdout.write(f"Provided parameters: {options}")
        source_destination = options.get("destination_to_clean")

        if not source_destination:
            raise DjangoStompIncorrectUse("No destination_to_clean was supplied! Nothing to clean!")

        self.stdout.write(f"Preparing to clean the queue: {source_destination}")
        clean_messages_on_destination_by_acking(source_destination)
