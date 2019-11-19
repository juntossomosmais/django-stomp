from django.core.management.base import BaseCommand
from django_stomp.execution import send_message_from_one_destination_to_another


class Command(BaseCommand):
    help = "Start internal PUB/SUB logic"

    def add_arguments(self, parser):
        parser.add_argument("source_destination", type=str, help="Source destination used to consume messages")
        parser.add_argument(
            "target_destination", type=str, help="The target which will receive messages from consumed destination"
        )

    def handle(self, *args, **options):
        self.stdout.write(f"Provided parameters: {options}")

        source_destination = options.get("source_destination")
        target_destination = options.get("target_destination")

        self.stdout.write("Calling internal service to send messages to target")
        send_message_from_one_destination_to_another(source_destination, target_destination)
