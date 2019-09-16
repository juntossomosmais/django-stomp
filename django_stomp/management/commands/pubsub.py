from django.core.management.base import BaseCommand
from django_stomp.execution import start_processing


class Command(BaseCommand):
    help = "Start internal PUB/SUB logic"

    def add_arguments(self, parser):
        parser.add_argument("source_destination", type=str, help="Source destination used to consume messages")
        parser.add_argument(
            "callback_function",
            type=str,
            help="Entire module path with its function to process messages from source destination",
        )

    def handle(self, *args, **options):
        self.stdout.write(f"Provided parameters: {options}")

        source_destination = options.get("source_destination")
        callback_function = options.get("callback_function")

        self.stdout.write("Calling internal service to consume messages")
        start_processing(source_destination, callback_function)
