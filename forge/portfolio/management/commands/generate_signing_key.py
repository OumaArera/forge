"""Generate an Ed25519 key pair for signing portfolio exports."""

from django.core.management.base import BaseCommand

from forge.portfolio.signing import generate_key_pair


class Command(BaseCommand):
    help = "Generate an Ed25519 key pair for signing portfolio exports."

    def handle(self, *args, **options):
        private_hex, public_b64 = generate_key_pair()
        self.stdout.write(self.style.SUCCESS("Generated a new signing key pair.\n"))
        self.stdout.write("Put this in your environment, never in the repository:\n")
        self.stdout.write(f"  PORTFOLIO_SIGNING_KEY={private_hex}\n")
        self.stdout.write("  PORTFOLIO_SIGNING_KEY_ID=forge-key-1\n\n")
        self.stdout.write("Publish this alongside it, so exports can be verified:\n")
        self.stdout.write(f"  public key (base64): {public_b64}\n\n")
        self.stdout.write(self.style.WARNING(
            "Rotating the key does not invalidate existing exports, provided the "
            "retired public key stays published. Every export records the key id "
            "it was signed with."
        ))
