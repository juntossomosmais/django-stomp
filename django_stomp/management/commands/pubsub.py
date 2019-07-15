from django.core.management.base import BaseCommand
from django_stomp.execution import start_processing


class Command(BaseCommand):
    help = "Start internal PUB/SUB logic"

    def add_arguments(self, parser):
        parser.add_argument("consume_queue", type=str)
        parser.add_argument("callback", type=str)

    def handle(self, *args, **options):
        start_processing(options.get("consume_queue"), options.get("callback"))
