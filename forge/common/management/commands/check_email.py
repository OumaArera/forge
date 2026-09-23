"""
Report whether this host can actually send mail, and over which port.

Every mail failure looks identical from inside the application: the send hangs,
then times out, and nothing in the logs says why. The cause is almost always
that outbound 25, 465 and 587 are filtered by the hosting provider. This
command answers the question directly instead of leaving it to be inferred from
a verification link that never arrived.

    python manage.py check_email                    # configuration and ports
    python manage.py check_email --to me@x.com      # also send a real message
"""

from __future__ import annotations

import smtplib
import socket

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.management.base import BaseCommand

#: 26 and 2525 are the interesting ones -- cPanel-style hosts listen on them
#: and cloud providers rarely filter them.
SMTP_PORTS = (25, 26, 465, 587, 2525)


class Command(BaseCommand):
    help = "Diagnose outbound mail: configuration, port reachability, optional test send."

    def add_arguments(self, parser):
        parser.add_argument("--to", help="Send a real test message to this address.")
        parser.add_argument("--timeout", type=float, default=6.0)

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Configuration"))
        for key in (
            "EMAIL_BACKEND", "EMAIL_HOST", "EMAIL_PORT", "EMAIL_USE_TLS",
            "EMAIL_USE_SSL", "EMAIL_TIMEOUT", "EMAIL_HOST_USER",
            "DEFAULT_FROM_EMAIL", "FRONTEND_BASE_URL",
        ):
            self.stdout.write(f"  {key:22} {getattr(settings, key, None)!r}")
        # Never print the password, even here. A diagnostic that leaks the
        # credential into a terminal history or a pasted support thread is
        # worse than the problem it is diagnosing.
        self.stdout.write(
            f"  {'EMAIL_HOST_PASSWORD':22} "
            f"{'<set>' if settings.EMAIL_HOST_PASSWORD else '<empty>'}"
        )

        backend = settings.EMAIL_BACKEND
        if not backend.endswith("smtp.EmailBackend"):
            self.stdout.write(self.style.WARNING(
                f"\nBackend is {backend} -- not SMTP, so there are no ports to test. "
                f"Set EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend to "
                f"send for real."
            ))
        elif not settings.EMAIL_HOST:
            self.stdout.write(self.style.WARNING("\nEMAIL_HOST is empty; nothing to test."))
        else:
            self._check_ports(settings.EMAIL_HOST, options["timeout"])

        if options["to"]:
            self._send(options["to"])

    def _check_ports(self, host: str, timeout: float) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING(f"\nReachability of {host}"))

        try:
            self.stdout.write(f"  resolves to {socket.gethostbyname(host)}")
        except OSError as error:
            self.stdout.write(self.style.ERROR(f"  DNS lookup failed: {error}"))
            self.stdout.write(self.style.WARNING(
                "  The mail host does not resolve. Nothing can be sent until it does."))
            return

        reachable = []
        for port in SMTP_PORTS:
            try:
                with socket.create_connection((host, port), timeout=timeout):
                    reachable.append(port)
                    marker = "  <- configured" if port == settings.EMAIL_PORT else ""
                    self.stdout.write(self.style.SUCCESS(f"  {port:>5}  open{marker}"))
            except (TimeoutError, OSError) as error:
                # socket.timeout is an alias of TimeoutError on 3.10+.
                reason = ("timed out (usually a provider filter)"
                          if isinstance(error, TimeoutError) else str(error))
                self.stdout.write(f"  {port:>5}  {reason}")

        if settings.EMAIL_PORT not in reachable:
            self.stdout.write(self.style.ERROR(
                f"\n  EMAIL_PORT={settings.EMAIL_PORT} is NOT reachable. Mail will hang "
                f"for {settings.EMAIL_TIMEOUT}s and then silently fail."))
            if reachable:
                self.stdout.write(self.style.WARNING(
                    f"  Reachable instead: {', '.join(map(str, reachable))}"))

    def _send(self, address: str) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING(f"\nTest send to {address}"))
        try:
            connection = get_connection(fail_silently=False)
            message = EmailMultiAlternatives(
                subject="FORGE mail check",
                body=(
                    "This is a test message from FORGE.\n\n"
                    "If you are reading it, outbound mail works: the host is "
                    "reachable, the credentials are accepted, and the message was "
                    "not rejected on the way out.\n\n"
                    "-- FORGE, The Open University of Kenya\n"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[address],
                connection=connection,
            )
            sent = message.send()
        except smtplib.SMTPAuthenticationError as error:
            self.stdout.write(self.style.ERROR(
                f"  Authentication refused: {error}\n"
                f"  The host is reachable but EMAIL_HOST_USER / EMAIL_HOST_PASSWORD "
                f"were not accepted."))
            return
        except (smtplib.SMTPException, OSError) as error:
            self.stdout.write(self.style.ERROR(f"  {type(error).__name__}: {error}"))
            return

        if sent:
            self.stdout.write(self.style.SUCCESS(
                "  Sent. Check the inbox and the spam folder."))
            self.stdout.write(
                "  If it lands in spam, the sending domain needs SPF and DKIM "
                "records -- see docs/for-the-ict-directorate.md.")
        else:
            self.stdout.write(self.style.ERROR("  Not sent, and no exception was raised."))
