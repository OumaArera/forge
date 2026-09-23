"""
Ed25519 signing for portfolio exports.

Why sign at all: a FORGE portfolio is meant to be shown to an employer, and
an employer receiving a JSON file has no reason to believe it. A signature
turns "this student says the platform confirmed their work" into something an
employer can check against a public key served by the University's own
subdomain, without an account and without contacting anybody.

Why Ed25519: short keys, short signatures, no parameter choices to get wrong,
and it is in the standard cryptography library rather than needing anything
exotic. A student maintainer can read this module and follow it.

Key handling: the private key is 32 bytes, hex-encoded, supplied in
PORTFOLIO_SIGNING_KEY and never committed. Generate one with
`python manage.py generate_signing_key`. Rotating it does not invalidate old
exports provided the old public key stays published -- which is why exports
carry a key id.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from django.conf import settings

logger = logging.getLogger("forge.portfolio")


class SigningUnavailable(RuntimeError):
    """Raised when no signing key is configured."""


def canonical_json(document: dict) -> str:
    """
    The exact bytes that get signed.

    Sorted keys, no incidental whitespace, UTF-8. A verifier reproduces this
    from the document it received; if the serialisation were not deterministic,
    a valid document would fail verification for cosmetic reasons.
    """
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _private_key() -> Ed25519PrivateKey:
    raw = (settings.PORTFOLIO_SIGNING_KEY or "").strip()
    if not raw:
        raise SigningUnavailable(
            "No PORTFOLIO_SIGNING_KEY is configured, so exports cannot be signed. "
            "Generate one with: python manage.py generate_signing_key"
        )
    try:
        return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(raw))
    except ValueError as exc:
        raise SigningUnavailable("PORTFOLIO_SIGNING_KEY is not 32 hex-encoded bytes.") from exc


def generate_key_pair() -> tuple[str, str]:
    """Returns (private_hex, public_base64). Used by the management command."""
    private = Ed25519PrivateKey.generate()
    private_hex = private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    ).hex()
    return private_hex, public_key_b64(private.public_key())


def public_key_b64(key: Ed25519PublicKey | None = None) -> str:
    key = key or _private_key().public_key()
    raw = key.public_bytes(encoding=serialization.Encoding.Raw,
                           format=serialization.PublicFormat.Raw)
    return base64.b64encode(raw).decode("ascii")


def sign(document: dict) -> tuple[str, str, str]:
    """
    Sign a document.

    Returns (signature_base64, key_id, sha256_of_canonical_json).
    """
    payload = canonical_json(document).encode("utf-8")
    signature = _private_key().sign(payload)
    digest = hashlib.sha256(payload).hexdigest()
    return (base64.b64encode(signature).decode("ascii"),
            settings.PORTFOLIO_SIGNING_KEY_ID, digest)


def verify(document: dict, signature_b64: str, public_b64: str | None = None) -> bool:
    """
    Check a signature against a document.

    Exposed through the API so that anyone holding an export can verify it,
    and published in docs/verifying-a-portfolio.md so that a recipient who
    would rather not trust our endpoint can do it in about fifteen lines of
    their own code.
    """
    try:
        raw_public = base64.b64decode(public_b64) if public_b64 else base64.b64decode(
            public_key_b64()
        )
        key = Ed25519PublicKey.from_public_bytes(raw_public)
        key.verify(base64.b64decode(signature_b64),
                   canonical_json(document).encode("utf-8"))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False
