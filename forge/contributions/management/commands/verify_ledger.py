"""
Walk the contribution ledger and report on its integrity.

Run this at every decision gate in the roadmap, and on a schedule in between.
A tamper-evident record is only worth having if somebody actually looks.
"""

import json

from django.core.management.base import BaseCommand

from forge.contributions.services import verify_chain


class Command(BaseCommand):
    help = "Verify the integrity of the contribution ledger hash chain."

    def add_arguments(self, parser):
        parser.add_argument("--from", type=int, default=1, dest="start")
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, **options):
        report = verify_chain(start=options["start"], limit=options["limit"])

        if options["json"]:
            self.stdout.write(json.dumps(report, indent=2))
            return

        self.stdout.write(f"Entries checked: {report['checked']}")
        self.stdout.write(f"Ledger head:     {report['head']}")
        if report["intact"]:
            self.stdout.write(self.style.SUCCESS("Chain intact. Every link verifies."))
            return

        self.stdout.write(self.style.ERROR(
            f"\n{len(report['problems'])} problem(s) found:\n"))
        for problem in report["problems"]:
            self.stdout.write(self.style.ERROR(
                f"  sequence {problem['sequence']}: {problem['issue']}"))
        self.stdout.write(self.style.WARNING(
            "\nA broken chain means a settled contribution record has been altered "
            "in the database. Preserve the current state, tell the faculty advisor, "
            "and do not repair it by rewriting hashes."
        ))
        raise SystemExit(1)
