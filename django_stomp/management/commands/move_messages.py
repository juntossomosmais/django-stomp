from django.core.management import CommandError
from django.core.management.base import BaseCommand
from django_stomp.execution import send_message_from_one_destination_to_another


class Command(BaseCommand):
    help = "Move messages from one destination to another"

    def add_arguments(self, parser):
        parser.add_argument("source_destination", type=str, help="Source destination used to consume messages")
        parser.add_argument(
            "target_destination", type=str, help="The target which will receive messages from consumed destination"
        )
        parser.add_argument(
            "broker_host_for_source_destination",
            type=str,
            nargs="?",
            help="Custom broker host only to get messages from source_destination",
        )
        parser.add_argument(
            "broker_port_for_source_destination",
            type=int,
            nargs="?",
            help="Custom broker port only to get messages from source_destination",
        )

    def handle(self, *args, **options):
        self.stdout.write(f"Provided parameters: {options}")

        source_destination = options.get("source_destination")
        target_destination = options.get("target_destination")
        broker_host_for_source_destination = options.get("broker_host_for_source_destination")
        broker_port_for_source_destination = options.get("broker_port_for_source_destination")

        if broker_host_for_source_destination and not broker_port_for_source_destination:
            raise CommandError("You should provide broker_port_for_source_destination option as well")

        self.stdout.write("Calling internal service to send messages to target")

        send_message_from_one_destination_to_another(
            source_destination,
            target_destination,
            custom_stomp_server_host=broker_host_for_source_destination,
            custom_stomp_server_port=broker_port_for_source_destination,
        )
