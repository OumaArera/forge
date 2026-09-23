# Verifying a FORGE portfolio

*Written for an employer, internship provider or anyone else who has been
handed a FORGE portfolio export and wants to know whether to believe it.*

A FORGE export is a JSON file. It lists the projects someone worked on and the
individual contributions they made, and each contribution records the two
people who independently confirmed it: the project lead and the project's
assigned mentor.

The file is signed. You do not have to trust the person who gave it to you, and
you do not have to contact the University.

## What a valid signature tells you

- FORGE issued this document, and it has not been altered since.
- Every contribution listed was confirmed by two other named people.
- The ledger entries quoted are part of an append-only, hash-chained record.

## What it does not tell you

- **That the document is current.** The person may have done more since.
- **That the work was good.** FORGE records that work was delivered and
  confirmed. It does not grade it.
- **That this is a University qualification.** It is not. FORGE is a voluntary
  student initiative and carries no academic credit.

## The quick way

POST the document back to the platform:

```bash
curl -X POST https://forge.ouk.ac.ke/api/v1/portfolio/verify/ \
  -H 'Content-Type: application/json' \
  -d @- <<JSON
{
  "portfolio": <the "portfolio" object from the export>,
  "signature": "<the signature.value from the export>"
}
JSON
```

You get back:

```json
{
  "signature_valid": true,
  "ledger_head_recognised": true,
  "member": "Amina Wanjiru",
  "contribution_count": 14,
  "verdict": "This document was issued by FORGE and has not been altered."
}
```

## The independent way

If you would rather not trust our endpoint — which is a reasonable position,
since we would be marking our own homework — verify it yourself. You need the
public key, which is published at:

```
https://forge.ouk.ac.ke/api/v1/portfolio/verification-key/
```

Then, in about fifteen lines:

```python
import base64
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

export = json.load(open("portfolio.json"))

# The signed bytes are the "portfolio" object, serialised with sorted keys,
# no whitespace between tokens, and UTF-8 encoding.
payload = json.dumps(
    export["portfolio"], sort_keys=True, separators=(",", ":"), ensure_ascii=False
).encode("utf-8")

key = Ed25519PublicKey.from_public_bytes(
    base64.b64decode(export["signature"]["public_key"])
)

try:
    key.verify(base64.b64decode(export["signature"]["value"]), payload)
    print("Valid. FORGE issued this and it has not been altered.")
except InvalidSignature:
    print("INVALID. Do not rely on this document.")
```

The same works in any language with an Ed25519 implementation. The only thing
to get right is the serialisation: sorted keys, `,` and `:` separators with no
spaces, UTF-8.

## Checking a certificate instead

A FORGE certificate carries a code like `H7KM-P3QR-9TWX`. Anyone can check it,
with no account:

```
GET https://forge.ouk.ac.ke/api/v1/recognition/certificates/verify/H7KM-P3QR-9TWX/
```

The response gives the recipient's name, what the certificate records, when it
was issued, and whether it has been revoked.

## If verification fails

A failed signature means the document you were given does not match anything
FORGE issued. The most likely explanations, in order:

1. The file was edited after it was downloaded — including by a well-meaning
   person who reformatted it.
2. It was assembled by hand.
3. It was signed with a key FORGE has since retired. Exports carry a `key_id`;
   if it does not match the current one, ask the University whether that key
   was ever in use.

In all three cases, ask the candidate for a fresh export. It takes them one
click, and a genuine one will verify.

## Key rotation

Each export records the `key_id` it was signed with. Rotating the signing key
does not invalidate existing exports, provided the retired public key stays
published. If you are verifying an older export, pass its `public_key` value
rather than the current one.
