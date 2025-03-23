from django.core.cache import cache
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Clear Site Cache"

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Clear ALL Cache")

    def handle(self, *args, **options):
        if options["all"]:
            cache.clear()
            self.stdout.write(self.style.SUCCESS("ALL Cache Cleared"))
        else:
            cache.delete_pattern("*.decorators.cache.*")
            self.stdout.write(self.style.SUCCESS("Template Cache Cleared"))
