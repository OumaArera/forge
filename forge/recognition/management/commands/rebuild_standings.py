"""
Recompute every member's standing from the ledger.

Standing is derived data. If it is ever wrong -- a bug, an interrupted task,
a change to the weighting -- this rebuilds it from the record. A derived table
that cannot be rebuilt is a derived table that will eventually be wrong and
unfixable.
"""

from django.core.management.base import BaseCommand

from forge.accounts.models import User
from forge.recognition.services import reassess_standing


class Command(BaseCommand):
    help = "Recompute recognition standing for every member from the ledger."

    def add_arguments(self, parser):
        parser.add_argument("--slug", help="Rebuild one member only.")

    def handle(self, *args, **options):
        queryset = User.objects.filter(is_active=True)
        if options["slug"]:
            queryset = queryset.filter(public_slug=options["slug"])

        total = queryset.count()
        for index, user in enumerate(queryset.iterator(), start=1):
            reassess_standing(user)
            if index % 100 == 0:
                self.stdout.write(f"  {index}/{total}")
        self.stdout.write(self.style.SUCCESS(f"Rebuilt standing for {total} member(s)."))
