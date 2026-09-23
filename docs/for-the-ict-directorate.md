# Notes for the Directorate of ICT

*Written for the Directorate of ICT, who will be asked to approve, host or
integrate with this platform.*

This is the short technical summary of what FORGE is, what it asks of the
University, and what it deliberately does not ask for.

## What it is

A Django application backed by PostgreSQL, containerised, with a REST API and a
separate web client. It is a voluntary student project and collaboration
platform. It holds no grades, issues no credit, and is not part of assessment.

## What we are asking the University for

There are five things, and only the first two are blocking.

**1. A subdomain.** For example `forge.ouk.ac.ke`, pointed at infrastructure
the student team operates during the pilot.

**2. A decision on identity.** In order of preference:

- *Single sign-on (preferred).* If the University runs Microsoft Entra ID,
  Google Workspace or Keycloak, we would use OIDC. Turning this on is a
  configuration change, not a code change — see `OIDC_*` in `.env.example`. We
  need a client id, a client secret and a redirect URI allow-listed.
- *Verified University email (the fallback, and what the pilot assumes).* We
  accept registration only from the domains listed in
  `UNIVERSITY_EMAIL_DOMAINS` and require a confirmed address. **Please confirm
  the authoritative list of student email domains** — this is the single gate
  keeping non-students out.

**3. Email sending.** Transactional email from the subdomain needs SPF and DKIM
records. Without them, verification messages land in spam and the platform does
not work at all.

**4. A deprovisioning signal, if one exists.** When a student graduates or
leaves, we would like to know. If there is no feed, we will re-verify annually.
Note what happens on deprovisioning: the account becomes an alumnus, keeps its
portfolio and its public address, and can still sign in via a personal recovery
address. It cannot take up new project roles. Students are asked for a recovery
address at registration precisely so that graduation does not destroy the
record the platform exists to build.

**5. Nothing else.** No access to the Learning Management System, no student
records feed, no integration with assessment.

## What we collect

Name, University email, programme, year of study, and whatever a member
voluntarily adds to a profile. A personal recovery email if they give one.

We do not collect national identification numbers, dates of birth, postal
addresses or any financial data, and there are no fields for them. Processing
is under the Data Protection Act, 2019. Members can export everything held
about them (`GET /api/v1/accounts/me/data/`) or have it erased
(`DELETE` on the same endpoint).

Erasure is worth understanding precisely: identifying data is destroyed and the
account becomes an unnamed tombstone, but confirmed contributions stay in the
ledger pseudonymously. This is a deliberate trade-off. A teammate's confirmed
contributions reference the same projects and reviews, so a ledger that one
participant could silently rewrite would destroy the value of every other
participant's record.

## Security posture

- Non-root container, no shell tooling in the image.
- Secrets from the environment only. Nothing in the repository, which is public.
- Free-text fields reject HTML; content is stored as plain text or Markdown.
- Append-only audit log covering authentication, role grants, lifecycle
  changes, attestations, moderation actions and data exports.
- Rate limiting on registration, verification, exports and reports.
- Role-based access, with every grant recording who made it and when it expires.
- **No offensive security activity of any kind** against University systems,
  third parties or live infrastructure. Any technical exercise runs in an
  isolated environment, and participants accept a written undertaking
  referencing the Computer Misuse and Cybercrimes Act, 2018, recorded per
  version with a digest of the exact text accepted.

## What FORGE does not host

**Video.** Demonstration videos are linked, never uploaded. Video is the single
largest bandwidth and storage cost a platform like this can acquire, it brings
transcoding and adaptive bitrate for students on poor connections, and it is a
moderation surface a volunteer team is not equipped to police. Teams link to an
unlisted upload elsewhere. This costs the platform nothing.

Screenshots are hosted; they are small and a showcase without a picture does
not get read.

## Running it on University infrastructure

The application is containerised so that this is a decision the University can
take at any point without the student team's involvement. It needs:

- A container runtime
- PostgreSQL 14 or later
- Redis (for background work only; the site functions without it)
- Object storage, or a persistent volume, for screenshots
- An SMTP relay

There is no dependency on any cloud provider's proprietary services. The
handover package — source, documentation, credentials procedure and runbook —
is maintained from the start of the pilot rather than assembled at the end.

## Things we would like your advice on

1. Whether OIDC is available, and against which identity provider.
2. The authoritative student email domain list.
3. Whether the University would prefer to host from the outset, rather than
   after the pilot.
4. Whether backups should be the student team's responsibility during the
   pilot or run under existing University arrangements. **Backups are not
   optional and are not yet configured** — this is the one operational gap we
   would ask for help closing before launch.
