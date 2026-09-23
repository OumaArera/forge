# Architecture decisions

*Written for whoever maintains FORGE next — most likely a student who has just
joined the platform team.*

Short notes on the decisions that would otherwise look arbitrary, and what
would have to change for each to be worth revisiting.

---

## 1. Django, not a split Django + SPA-framework backend

**Decision.** One Django application with Django REST Framework. A separate
web client talks to it over the API.

**Why.** The volunteer team is small, term-time only, and turns over every year
or two. A split stack means two languages, two toolchains, two deployment
units and authentication plumbed twice — a real cost for a team of that shape.

Django also ships, for free, most of what the platform's own policies commit it
to: an admin for moderation, a permissions framework, migrations, and a
straightforward path to the data export and erasure the Data Protection Act
requires. Building that by hand would have consumed most of a pilot.

**Revisit if.** The team becomes large enough to sustain two codebases, or a
mobile client needs something the REST API cannot express.

## 2. UUID primary keys

**Decision.** Every model uses a UUID primary key.

**Why.** Identifiers appear in URLs that students paste into job applications.
A sequential integer would leak how many students and projects the platform
has, and would make one member's record trivially guessable from another's.

**Cost.** Slightly larger indexes. Irrelevant at this scale.

## 3. Soft deletion nearly everywhere

**Decision.** `deleted_at` rather than `DELETE`.

**Why.** A contribution record that vanished would destroy the evidence the
platform exists to accumulate. A removed forum post would orphan its replies
and leave the thread unreadable for everyone else.

**Exception.** A member exercising their right to erasure. That goes through
`accounts.services.erase_user`, which destroys identifying data while leaving
the collaborative record intact — see decision 6.

## 4. The contribution ledger is append-only and hash-chained

**Decision.** A settled contribution becomes a `LedgerEntry` carrying the hash
of the entry before it. `save()` on an existing entry raises.

**Why.** A portfolio is only worth showing an employer if the claims in it are
hard to fabricate. Chaining does not make tampering impossible — an
administrator with database access could rewrite the whole chain — but it makes
*silent* tampering impossible, which is the achievable goal.

The chain is global rather than per-member, deliberately. A per-member chain
would let someone with database access rewrite one person's history in
isolation. A global chain means any alteration breaks verification for every
entry recorded afterwards, including entries belonging to people with no
connection to the change.

**Cost.** Settlement takes a PostgreSQL advisory lock, so two contributions
settling simultaneously serialise. At this volume that is free.

**Revisit if.** Settlement volume ever makes the lock a bottleneck — at which
point per-discipline chains with periodic cross-anchoring would be the move.

## 5. Two-party attestation, and what it refuses

**Decision.** A contribution settles only when both the project lead and the
assigned mentor confirm it. Nobody attests to their own work. One signature per
capacity, so somebody who is both lead and mentor supplies one, not two. A
peer's confirmation is recorded but does not settle anything.

**Why.** Each of those is a loophole somebody would otherwise find. Without the
first rule the platform is a self-service portfolio generator.

**Cost.** Confirmations are the bottleneck in the whole system. A lead who is
three weeks behind is a team whose portfolios are all empty. That is why
`/api/v1/contributions/awaiting-my-attestation/` exists and why it should be
prominent in any client.

## 6. Erasure keeps the pseudonymous record

**Decision.** Erasure destroys identifying data and makes the account an
unnamed tombstone. Confirmed contributions stay in the ledger, and an
attestor's name is denormalised onto the attestation so it survives their
erasure.

**Why.** The hardest trade-off in the system. A right to erasure is real, but a
ledger one participant could silently rewrite would destroy the value of every
other participant's portfolio — their teammate's confirmed contributions
reference the same projects and the same reviews. And if an attestor's name
vanished, every portfolio that mentor ever confirmed would quietly lose its
backing.

Nobody can recover who the erased member was from what remains, and nobody
else's record is falsified.

## 7. Recognition is computed, never entered

**Decision.** Levels, points and leaderboards are derived from the ledger.
There is no field anywhere an administrator can set to give somebody a level.
`rebuild_standings` regenerates all of it from scratch.

**Why.** A derived table that cannot be rebuilt is a derived table that will
eventually be wrong and unfixable. And a recognition system with a manual
override is a recognition system that will be overridden.

**Related.** Votes on forum posts affect the ordering of answers and nothing
else. The platform's stated position is that it rewards demonstrated
contribution rather than popularity; letting a well-liked post earn points
would quietly abandon that.

## 8. Leaderboards are scoped and frozen

**Decision.** Boards are per discipline area and per trimester, computed on a
schedule into a snapshot. There is no global all-members ranking.

**Why.** A single global board would be won permanently by whoever writes the
most code, and a Nursing or Education student would never appear on it. Freezing
per trimester stops a strong contributor from two years ago occupying the top
forever, which is the other way these boards go dead. A live board recomputed
on every page view would be both the platform's most expensive query and its
most addictive feature.

## 9. Video is linked, never hosted

**Decision.** `ShowcaseEntry.demonstration_url` accepts links to a small
allow-list of video hosts. Uploads are refused.

**Why.** Video is the largest storage and bandwidth item a platform like this
can acquire, and on a pilot funded by sponsored credits it is what exhausts
them. It also brings transcoding, adaptive bitrate for students on poor
connections, and a moderation surface a volunteer team cannot police. An
unlisted upload elsewhere is free and solves all three.

## 10. Rules live in `services.py`

**Decision.** Views validate shapes. Services validate meaning. Views never
change `Project.status` directly.

**Why.** The same rule has to apply whether the caller is the API, the Django
admin, a management command or a scheduled task. A rule enforced in a
serializer is a rule that does not exist for the admin.

## 11. AI assistance is disclosed, not prohibited

**Decision.** Every contribution carries an `ai_assistance` field, and
declaring anything other than "none" requires a written note. An attestor who
finds undisclosed assistance has grounds to dispute.

**Why.** The platform's principle is evidence before claims, and a contribution
record is worth nothing if it cannot distinguish work someone did from work
someone prompted. But a prohibition would simply be ignored — generative tools
are part of how software is now written. Disclosure is enforceable; a ban is
not.

**Note for the code of conduct.** This needs a matching clause in the written
conduct document, not just a database field.

## 12. Digests, not immediate email

**Decision.** Everything is written in-app. Email is a daily digest by default.
Only a short list of verbs — your application was decided, your contribution
was confirmed or disputed, a moderator acted on your account — sends
immediately.

**Why.** Most members are studying at a distance and many are in employment. A
platform that emails somebody eleven times a day gets muted within a week, and
is then unable to reach them about the one thing that mattered.

## 13. Discussion is deliberately minimal

**Decision.** Threaded discussion per discipline area, questions with an
accepted answer, one level of reply nesting. That is all.

**Why.** A good forum is a year of work. What the platform actually needs is
the thing a chat group cannot do: a persistent, searchable, attributable record,
and a question with a marked answer that the next student does not have to ask.
One level of nesting because deeper trees are unreadable on a phone, which is
where most of this will be read.

**Revisit if.** The pilot shows members want a real forum. The answer then is
to run Discourse alongside FORGE, not to grow this into one.


## 14. A certificate is downloadable only by its holder

**Decision.** The PDF endpoint requires sign-in and refuses anyone but the
holder and platform stewards. Verification by code stays open to everybody,
with no account.

**Why the reversal.** The first version let anyone holding the code download
the file, reasoning that a certificate only its owner can fetch is no use to
the employer it was sent to. That reasoning was wrong in one specific way: the
code is *printed on the document*, so anyone who had ever been shown a
certificate could pull a fresh, clean copy and present it as their own. The
employer never needed the file — they need to know it is genuine, and the
verification endpoint tells them that directly, from us rather than from the
paper they were handed.

**What replaces it.** The verification response reports how many copies the
holder has taken and when the last one was. A certificate presented on paper
that has never been downloaded is worth a second look.

**Every download is recorded**, and each copy is stamped with the moment it was
taken and who took it, so a copy that leaks traces back to one download rather
than to "somebody, at some point". The holder sees their own trail; nobody
else does.

## 15. The certificate carries a security layer, not a security claim

**Decision.** A certificate PDF is printed over a faded FORGE mark, a guilloche
lattice, and microtext repeating the holder's name across the page and in a
band directly beneath their printed name.

**Why.** None of it is cryptography, and it is important not to pretend
otherwise: the verification code and the ledger hash are what actually prove a
certificate is genuine, and both are checkable by anybody with no account. What
the background does is raise the cost of a *casual* forgery. Somebody retyping
the wording in a word processor produces something that looks obviously wrong
beside a real one, and somebody editing a genuine certificate has to rebuild a
background woven from the original holder's name.

**Cost.** The logo is downscaled to 460px and faded into white before being
embedded. Left at its native 1254px it took a 3 KB document to nearly a
megabyte — on a file students email from a phone.

**Text is not text.** The holder's name, the verification code, the confirming
parties and the microtext are drawn as filled vector paths rather than
characters, so there is nothing to extract however the file is opened. The PDF
also sets the copy-forbidden permission flag, but that is advisory — a
compliant viewer honours it and `pdftotext` does not, which is exactly why the
outlines exist.

The cost is real: outlined text cannot be read by a screen reader or searched.
So only the fields a forger would need are outlined. **The statement and the
disclaimer stay as real text**, because a reader using assistive technology
must still be able to hear what the document says and, above all, that it
carries no academic credit.

**Revisit if.** Certificates ever need to survive being printed and
photocopied, at which point a scannable code belongs on them too.

## 16. Project cards use generated marks, not photographs

**Decision.** Each project gets a mesh gradient and a discipline glyph,
deterministic from its slug. There is no image upload.

**Why.** An upload is one more thing between a student and proposing
something, and a stock photograph of a laptop tells a reader nothing about a
clinic queue tracker. The generated mark carries real information — the glyph
and colour come from the discipline — costs no bandwidth, and never looks like
a placeholder somebody forgot to replace.

**Where photographs are used.** The landing page only, as atmosphere behind a
heavy gradient, and every section of it reads correctly with the images absent.
They are WebP at reduced width: the originals were ten times the weight of the
entire JavaScript bundle. Credits in `web/public/img/CREDITS.md`.
