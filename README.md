# FORGE — backend

A student project, collaboration and practical experience ecosystem for
The Open University of Kenya.

FORGE is where a student proposes a piece of work, recruits classmates from any
school to help build it, is guided by a volunteer academic mentor, delivers
something real, documents it, and accumulates a verifiable record of what they
have actually done.

**FORGE awards no academic credit and issues nothing that could be mistaken for
a University qualification.** It complements the Learning Management System; it
does not duplicate it.

---

## Getting it running

You need Python 3.10+ and PostgreSQL 14+. Redis is only needed for background
work and can wait.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then edit it; DATABASE_URL is the one that matters
createdb forge

python manage.py migrate
python manage.py seed_reference_data
python manage.py generate_signing_key   # paste the key into .env
python manage.py createsuperuser
python manage.py runserver
```

Then:

- `http://localhost:8000/api/docs/` — the whole API, browsable
- `http://localhost:8000/admin/` — the back office
- `http://localhost:8000/healthz/` — liveness
- `http://localhost:8000/readyz/` — readiness

Or with Docker:

```bash
docker compose up --build
docker compose exec api python manage.py migrate
docker compose exec api python manage.py seed_reference_data
```

## Running the tests

```bash
pytest                       # all of it
pytest tests/test_contribution_ledger.py -v   # the rules that matter most
```

The test database is created and dropped per run, so the database role needs
`CREATEDB`.

---

## What is here

```
config/            settings, URLs, Celery
forge/
  common/          base models, permissions, pagination, error shape
  accounts/        identity, profiles, roles, data-subject rights
  audit/           append-only audit log
  projects/        the seven-stage lifecycle, roles, applications, teams
  workspace/       milestones, tasks, weekly progress updates
  contributions/   claims, attestations, the hash-chained ledger
  recognition/     levels, badges, leaderboards, verifiable certificates
  community/       discussion spaces, questions, accepted answers
  showcase/        completed work, presented for an outside reader
  mentorship/      mentor capacity, requests, office hours
  moderation/      reports, moderation actions, acceptable-use records
  notifications/   in-app notifications and email digests
  portfolio/       portfolio assembly, Ed25519 signing, public verification
tests/             181 tests, weighted towards the rules that matter
docs/              the notes a maintainer or the ICT Directorate will want
```

## The parts worth understanding first

**The contribution ledger** (`forge/contributions/`). A claim of work is made
by the contributor, confirmed independently by the project lead *and* the
assigned mentor, and only then settled into an append-only, hash-chained
ledger. Nobody can confirm their own work; one signature per capacity; a peer's
opinion does not settle a record. This is what makes a FORGE portfolio worth
believing, so it is the most heavily tested code in the repository.

Check the chain at any time:

```bash
python manage.py verify_ledger
```

**The project lifecycle** (`forge/projects/models.py`). The seven stages from
the concept proposal are an explicit state machine. `Project.TRANSITIONS` is
the single statement of what may follow what; `services.transition` is the only
supported way to move between them.

**Signed portfolio exports** (`forge/portfolio/`). A student can download their
record signed with an Ed25519 key, and anyone — an employer, with no account —
can verify it against a public key published by the platform. See
[docs/verifying-a-portfolio.md](docs/verifying-a-portfolio.md).

**Access control** (`docs/access-and-abuse.md`). Students never choose a
password — credentials are generated and emailed to the University address, so
opening an account requires being able to read that mailbox. Sign-in carries
two rate limits and an escalating lockout. Staff, alumni and partners join by
invitation, issued by a named steward.

**Recognition** (`forge/recognition/`). Levels and leaderboards are computed
from the ledger and can be rebuilt from scratch. Nothing here can be set by
hand. Boards are per discipline area and per trimester on purpose: a single
global board would be won permanently by whoever writes the most code, and a
Nursing or Education student would never appear on it.

## Conventions

- **Rules live in `services.py`, not in views or serializers.** Views validate
  shapes; services validate meaning. The same rule then applies whether the
  caller is the API, the admin, a management command or a scheduled task.
- **Primary keys are UUIDs.** Identifiers appear in URLs students paste into
  job applications.
- **Almost nothing is hard-deleted.** Deletion is a state. The exception is a
  member exercising their right to erasure, which goes through
  `accounts.services.erase_user`.
- **Errors have one shape:** `{"error": {"code": ..., "detail": ...}}`.

## Operations

| Command | What it does |
| --- | --- |
| `python manage.py verify_ledger` | Walk the chain and report on its integrity |
| `python manage.py rebuild_standings` | Recompute recognition from the ledger |
| `python manage.py seed_reference_data` | Schools, programmes, levels, badges, skills |
| `python manage.py generate_signing_key` | New Ed25519 key pair for exports |
| `python manage.py check_email` | Diagnose outbound mail; `--to` sends a real test |
| `python manage.py bootstrap_admin` | Create the founding student-administrator |
| `python manage.py seed_demo` | Fill a development instance; `--wipe` removes it |

Background work runs under Celery; the schedule is in
`config/settings/base.py` under `CELERY_BEAT_SCHEDULE` and can be adjusted
through the admin without a deployment.

## Security

- No secret is ever committed. `.env` is gitignored and must stay that way —
  a public repository with student contributors is exactly how credentials leak.
- The platform collects the minimum: name, University email, programme, year of
  study, and whatever a member voluntarily adds. No national identification
  numbers, no financial data.
- Free-text fields reject HTML; content is stored as plain text or Markdown and
  rendered safely at the edge.
- Every moderation decision requires a written rationale and the subject is
  told what was done and why.

Found something? Report it to the faculty advisor rather than opening a public
issue.

## Contributing

FORGE is built in the open by students of the University, which is part of the
point: the people building it acquire exactly the experience the initiative
exists to create.

Before a pull request:

```bash
ruff check .
pytest
python manage.py makemigrations --check --dry-run
```

New rules need a test. If you are changing something in `contributions/` or
`portfolio/`, expect that test to be scrutinised more than the code.
