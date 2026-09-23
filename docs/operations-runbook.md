# Operations runbook

*Written for whoever is on call for FORGE — during the pilot, a student
maintainer.*

## Daily

Nothing. The scheduled jobs run themselves. Check `/readyz/` is green if you
want reassurance.

## Weekly

```bash
python manage.py verify_ledger
```

This also runs nightly as a Celery task, but run it by hand before anything
the Advisory Committee will see.

## The ledger reports a problem

**Do not repair it.** Do not recompute hashes, do not delete entries, do not
"fix" the chain.

A broken chain means a settled contribution record has been altered in the
database. That is either a bug or an intrusion, and in both cases the current
state is the evidence.

1. Note the sequence numbers reported.
2. Take a database snapshot immediately.
3. Tell the faculty advisor the same day.
4. Preserve the audit log — `AuditEvent` will show who did what around the
   time in question.

Only after the cause is understood does anyone decide what to do about it.

## Backups

**This is the outstanding gap.** Before the pilot opens to students there must
be:

- A nightly `pg_dump` to storage outside the application host
- A retention schedule agreed with the faculty advisor
- **A restore that has actually been tested.** A backup nobody has restored is
  a hypothesis, not a backup.

Everything else in this runbook is less important than that paragraph.

## A member cannot sign in

Most likely, in order:

1. They never confirmed their email. Check `email_verified_at` on the account.
   They can request a new link at `/api/v1/accounts/resend-verification/`.
2. They have graduated. Their status is `alumnus` and they should be using
   their recovery address.
3. They are suspended. Check `ModerationAction` for the account.

## Recognition looks wrong

```bash
python manage.py rebuild_standings --slug <their-public-slug>
```

Standing is entirely derived. If a rebuild does not fix it, the problem is in
the ledger, not in the standing.

## Rotating the signing key

```bash
python manage.py generate_signing_key
```

Put the new private key in the environment and bump `PORTFOLIO_SIGNING_KEY_ID`.

**Keep publishing the old public key.** Exports carry the key id they were
signed with, and an employer verifying a six-month-old export needs the key it
was signed with. Retiring a key without publishing it silently invalidates
every export made under it.

## Sponsored credits are running out

Known cliff, flagged in the concept proposal. Before it arrives:

- Confirm the infrastructure is registered to an **organisation account with
  more than one owner**, not to an individual student's account. A student
  account is a person, and people graduate.
- Have the monthly figure ready for the University, not a claim that costs are
  small.

## Restoring a project archived in error

Archiving is reversible. A project moved to `abandoned` by the stale-project
task can be transitioned back to `recruiting` by its lead, or from the admin.

## Somebody says their certificate was downloaded without them

Every download is recorded against the certificate — **Achievements** shows the
holder their own trail, and a steward can see it in the admin. Check:

1. Were the extra downloads marked `was_holder = False`? Then a steward took
   them, and the trail names who.
2. If they were marked as the holder, the account is compromised. Reissue
   credentials (**Administration → Members → Reissue credentials**), which
   invalidates the current password, and check the audit log for what else
   that session did.

A downloaded copy carries the timestamp it was issued at, in small type at the
bottom left. If a suspect copy is produced, that stamp identifies which
download it came from.

## Escalation

| Situation | Who |
| --- | --- |
| Ledger integrity failure | Faculty advisor, same day |
| Suspected data breach | Faculty advisor, then the University's DPO |
| Harassment or conduct matter | Faculty advisor — not a student moderator |
| Site down | Platform technical lead, then the faculty advisor if unresolved |
