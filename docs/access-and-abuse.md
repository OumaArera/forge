# Access, credentials and abuse control

*Written for whoever maintains FORGE, and for the Directorate of ICT reviewing
what the platform does about unauthorised access.*

Four mechanisms, each addressing a different thing that goes wrong.

---

## 1. Credentials are emailed, never chosen

A student registers with a University address and gives no password. FORGE
generates one, emails it to that address, and holds the member at a
change-password screen until they replace it.

**Why.** With a self-chosen password, anyone who can guess the *shape* of a
University address opens a working account without ever proving they hold the
mailbox. Student address formats are predictable by design. Mailing the
credential makes the mailbox the credential.

**What follows from it.**

- There is no separate "verify your email" step. Receiving the credentials
  *is* the proof of address, and a second click would add friction without
  adding assurance.
- There is no self-service password reset. A reset link is a second credential
  travelling by email, and the account can already be recovered through the
  same mailbox. A steward reissues credentials instead, which leaves an audit
  row naming who asked and who acted.
- Registration answers identically whether or not the address is already
  taken. A different answer would turn the endpoint into a way of discovering
  which students are on the platform.

## 2. Invitations, for everybody the open route excludes

Staff, alumni returning to mentor, and external partners have no
`students.ouk.ac.ke` address. Their accounts are exempt from the domain check,
so each one is issued deliberately by a named steward, and the invitation row
records who.

- Only a hash of the token is stored.
- One use, then dead. Resending rotates the token, so the previous link stops
  working.
- Expires after `INVITATION_TTL_DAYS` (14 by default).
- A role can be attached and is granted on acceptance.
- The invitee previews who invited them and in what capacity before filling
  anything in — a bare form behind a link from a stranger reads like phishing.

## 3. Rate limits

Two layers, in `forge/common/throttling.py`.

| Scope | Default | Keyed on | Stops |
|---|---|---|---|
| `anon-burst` | 60/min | IP | a tight loop |
| `anon-sustained` | 600/hour | IP | a slow crawl |
| `user-burst` | 180/min | account | a broken client |
| `user-sustained` | 3000/hour | account | scripted scraping |
| `login` | 10/min | IP | one host working through a list of accounts |
| `login-email` | 8/hour | email | a botnet working on one account |
| `registration` | 5/hour | IP | bulk account creation |
| `email-verification` | 6/hour | IP | mail-sending abuse |
| `pdf` | 40/hour | account or IP | certificate rendering as a CPU sink |
| `invite` | 60/day | account | a compromised steward account |

All tunable by environment variable; see `.env.example`.

**What these are not.** A real distributed flood has to be stopped upstream, at
the reverse proxy or CDN, before it reaches Django at all — by the time a
request is being throttled, a worker has already been occupied parsing it.
What these actually buy is protection against the single-host script, which is
what a student platform meets in practice. **Put Cloudflare or equivalent in
front of the pilot; do not treat these limits as the perimeter.**

**The counters live in the cache.** With the local-memory fallback each worker
process keeps its own, so a limit of "10 a minute" silently becomes "10 a
minute per worker". Set `REDIS_URL` in anything running more than one process.

## 4. Sign-in lockout

A rate limit caps how fast somebody guesses. A lockout caps how many guesses
they get at all, which is the property that actually protects a weak password —
10/min still permits about fourteen thousand attempts a day.

In `forge/accounts/lockout.py`, counted per account with an escalating backoff:

| Failures in 15 minutes | Locked for |
|---|---|
| 5 | 5 minutes |
| 8 | 30 minutes |
| 12 | 2 hours |
| 20 | 12 hours |

- Checked **before** the password is compared, so a locked account costs an
  attacker a request and tells them nothing.
- Unknown addresses are counted too. Not counting them would mean the
  addresses that can be retried forever are exactly the ones with no account,
  which is an enumeration oracle.
- A correct password clears the count immediately. The usual cause of five
  failures is a student who has forgotten their password, not an attacker.
- The member is emailed once, at the fifth failure. An unexplained lockout is
  indistinguishable from a broken site — and if it was not them, they need to
  know somebody is trying.
- A steward can clear it without changing the password:
  **Administration → Members → Unlock**.

**Per account, not per IP.** A per-IP lockout is useless against a botnet.
A per-account lockout has its own weakness — an attacker can lock a known
account deliberately — which is why the lock is short, self-healing, and
clearable by a steward.

---

## What a steward can do

Administration → in the sidebar, for faculty advisors and platform
maintainers.

| Action | Effect | Recorded |
|---|---|---|
| Invite | Creates an account bypassing the domain check | Audit log, with the issuer |
| Grant / revoke role | Changes standing capabilities | Audit log, with the grantor |
| Suspend | Blocks sign-in; a written reason is required | Audit log, with the reason |
| Reinstate | Restores the previous status, clears any lockout | Audit log |
| Reissue credentials | New generated password, emailed | Audit log |
| Unlock | Clears failed sign-in attempts only | — |

Suspension **requires a rationale of at least ten characters**. A decision
nobody has to explain is a decision that will eventually be made badly, and an
account suspended without one cannot be appealed.

## Seeing whether mail actually went out

Every message goes through `forge/common/mail.py`, which records an `EmailLog`
row whether it succeeded or failed. **Administration → Email.**

This exists because "the email never arrived" is otherwise unanswerable. With
the log, it splits into three questions that each have an answer: did we try,
did the server accept it, and what address did it go to.

No message body is stored — verification links and generated passwords pass
through this path, and a table holding them would be a better target than the
password hashes it sits beside.

If mail is accepted but never arrives, the cause is almost always
deliverability rather than sending. Check SPF and DKIM on the sending domain;
see [for-the-ict-directorate.md](for-the-ict-directorate.md).

## Still outstanding

- **No CDN or WAF in front of the pilot.** The limits above are a speed bump,
  not a perimeter.
- **No second factor.** Worth considering for accounts holding
  `faculty_advisor` or `platform_maintainer`, which can grant roles and
  suspend accounts.
- **Backups.** Still the largest operational gap; see
  [operations-runbook.md](operations-runbook.md).
