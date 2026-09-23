# Deployment

FORGE's API runs at **https://forge-api.zafrika.com** on a DigitalOcean
droplet at `159.89.235.222`, as `forge-api.service` under gunicorn, behind
nginx, against PostgreSQL 17 and Redis on the same host.

*Written for whoever deploys or debugs this next — quite possibly a student
maintainer who has never seen the box.*

---

## This is a shared box

The droplet is not ours. It runs **twenty other domains** for other clients —
`dholuo.co.ke`, `api.edmondserenity.com`, `api.orifreightlines.com`,
`auth-service.nest.co.ke` and the rest. Everything below is scoped so that a
mistake in FORGE cannot take them down:

- Its own PostgreSQL role and database (`forge` / `forge`).
- Redis databases **4, 5 and 6**. Databases 0–3 belong to other apps; picking
  one of those would have silently shared a keyspace with somebody else's
  sessions.
- Its own unix socket, its own nginx site, its own systemd unit.
- Nothing shared is edited. The only file the setup adds to a shared directory
  is a symlink in `sites-enabled`, and nginx is only ever reloaded after
  `nginx -t` passes.

**It is also a small box**: 1 vCPU, 2 GB of RAM with a few hundred megabytes
typically free, and 11 GB of disk. gunicorn runs **2 workers × 2 threads** and
sits at about 150 MB. Do not raise that without checking `free -h` first.

## Redeploying

```bash
make deploy          # tests, sync, deps, migrate, static, restart, verify
make deploy-fast     # the same without reinstalling dependencies
```

`scripts/deploy.sh` is idempotent and safe to run repeatedly. It **runs the
test suite first** and stops if anything fails — a deploy that skips the tests
is a deploy that eventually ships the bug they would have caught.

It does **not** touch the database contents, `.env`, nginx or the certificate.
Those were set up once, below.

After migrating it **verifies the ledger chain**. The ledger is the thing this
platform exists to protect; if a migration ever disturbs it, the deploy should
say so rather than leave it to be discovered months later.

It then checks five public endpoints and fails loudly if any is not 200.

## What the one-time setup did

`deploy/bootstrap-root.sh`, run once with sudo. Re-runnable — every step checks
before it acts.

1. **Database.** Created the `forge` role and database, with the password read
   out of `.env` so there is one source of truth for it. Then *proved the app
   can actually connect over TCP* — on a host already running five other
   Postgres apps, discovering a missing `pg_hba.conf` entry at gunicorn-start
   time is a bad way to find out.
2. **systemd.** Installed `deploy/forge-api.service`. It deliberately matches
   the shape of the `hundhwe-api` unit already on this box — default `Type`,
   `UMask=007`, the same hardening flags. On a machine other people depend on,
   a proven unit beats a cleverer one.
3. **nginx.** Installed `deploy/forge-api.nginx`, issued the certificate with
   certbot over the webroot, then put the real TLS config in place. The
   certificate auto-renews; it expires 22 December 2026.

Secrets were generated **on the server** and never travelled from a laptop:
the Django key, the database password and a fresh Ed25519 signing key.

> The production signing key is **not** the development one. A key that has
> ever been on a laptop must not sign a document an employer relies on.
>
> Public key, for verifying exports:
> `kmhZYxs0R9651HmF3k65GuSt8UODcFjSXoDJOPeG9MU=`

## Mail

**Port 26, and this is not optional.** On this droplet, ports 25, 465, 587 and
2525 all time out — the provider filters them. A send to a filtered port does
not fail; it hangs until `EMAIL_TIMEOUT` and disappears with nothing in the
logs, which is the worst failure mode available.

```bash
make prod-mail-check          # reports which ports are actually reachable
```

Every message the platform attempts is recorded in `EmailLog`, visible at
**Administration → Email**. That is what makes "the email never arrived"
answerable.

## Rate limiting

Two layers. nginx limits at the edge (`10r/m` on the credential endpoints,
`120r/m` elsewhere, 24 connections per address) because by the time Django is
throttling a request, one of only two workers has already been occupied
parsing it. The application limits and lockouts described in
[access-and-abuse.md](access-and-abuse.md) sit behind that.

Neither is a defence against a real distributed flood. **There is no CDN or WAF
in front of this box.** That remains the largest gap.

## Operations

```bash
make prod-status       # is it running, and since when
make prod-logs         # last 120 lines from journalctl
make prod-restart      # restart gunicorn
make prod-shell        # a Django shell on the production database
make prod-ledger       # verify the contribution ledger
make prod-backup       # pg_dump to ./backups/
```

`arera` holds a scoped NOPASSWD sudo rule on this host covering `systemctl`,
`nginx`, `tee`, `ln`, `rm`, `mkdir`, `chown`, `chmod` and `su` — enough for the
whole deploy loop without handing over the machine. Note that `sudo -n true`
fails despite this, because `true` is not on the list: test with the command
you actually intend to run.

## Still to do

- **`FRONTEND_BASE_URL` is a placeholder.** It currently points at the API
  host. Verification links and portfolio URLs are built from it, so emailed
  links go nowhere useful. **Do not invite a student until the web client is
  deployed and this is corrected**, in `/var/www/forge-api/.env`, followed by
  `make prod-restart`.
- **Backups are manual.** `make prod-backup` works, but nothing runs it on a
  schedule and no restore has been tested. A backup nobody has restored is a
  hypothesis. This is the single largest operational gap.
- **No Celery worker is running.** Digests, stale-project sweeps and
  leaderboard rebuilds are therefore not happening. The Redis databases are
  reserved and the code is deployed; only the unit is missing.
- **No error reporting.** `SENTRY_DSN` is empty.
- **No CDN or WAF**, as above.

## Unrelated problems noticed on this host

Not ours to fix, but worth somebody knowing:

- `goalkeepers.edmondserenity.com` is declared in two nginx sites
  (`edmondserenity-api` and `goalkeepers-backend`); nginx warns and ignores
  the second.
- `edmondserenity-api` still uses the deprecated `listen ... http2` form.
- `proxy_headers_hash_bucket_size` is too small for the number of sites now on
  the box; nginx warns on every reload.
