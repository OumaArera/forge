#!/usr/bin/env bash
#
# The parts of the FORGE deployment that need root. Run once, on the server:
#
#     sudo bash /var/www/forge-api/deploy/bootstrap-root.sh
#
# It is deliberately re-runnable: every step checks before it acts, so a
# half-finished run can simply be repeated.
#
# What it does NOT do: touch any other site on this box. The only shared file
# it writes is a new symlink in sites-enabled, and the only service it reloads
# is nginx — after testing the config.

set -euo pipefail

# Every run is logged, and a failure names the step it died on. The first
# attempt at this produced no output anybody kept, which left "did it work?"
# unanswerable.
LOG=/var/www/forge-api/deploy/bootstrap.log
exec > >(tee -a "$LOG") 2>&1
echo "=== run started $(date -Is) by ${SUDO_USER:-$USER} ==="

STEP="startup"
trap 'rc=$?; [[ $rc -eq 0 ]] || { echo; echo "FAILED during: $STEP (exit $rc)"; echo "Full log: '"$LOG"'"; }' EXIT

APP=/var/www/forge-api
DOMAIN=forge-api.zafrika.com
DB_NAME=forge
DB_USER=forge

say() { STEP="$*"; printf '\n==> %s\n' "$*"; }

if [[ $EUID -ne 0 ]]; then
  echo "This needs root. Run it as:"
  echo "    sudo bash $0"
  exit 1
fi
[[ -d $APP ]] || { echo "$APP does not exist — copy the code first." >&2; exit 1; }

# --------------------------------------------------------------- database
say "PostgreSQL role and database"
# The password is read out of the app's own .env rather than generated here,
# so there is one source of truth for it. .env is written first, by the
# unprivileged deploy step, and is chmod 600.
[[ -f $APP/.env ]] || { echo "$APP/.env is missing — run the deploy step first." >&2; exit 1; }
DB_PASS=$(sed -n 's#^DATABASE_URL=postgres://[^:]*:\([^@]*\)@.*#\1#p' "$APP/.env")
[[ -n $DB_PASS ]] || { echo "Could not read the database password from .env." >&2; exit 1; }

if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1; then
  sudo -u postgres psql -c "ALTER ROLE $DB_USER LOGIN PASSWORD '$DB_PASS';" >/dev/null
  echo "    role $DB_USER exists — password synced with .env"
else
  sudo -u postgres psql -c "CREATE ROLE $DB_USER LOGIN PASSWORD '$DB_PASS';" >/dev/null
  echo "    created role $DB_USER"
fi

if sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1; then
  echo "    database $DB_NAME already exists"
else
  sudo -u postgres createdb -O "$DB_USER" "$DB_NAME"
  echo "    created database $DB_NAME"
fi
# Deliberately no CREATEDB: production does not need it. If you ever want to
# run the test suite on this box, grant it then and revoke it afterwards.

say "Proving the application can actually connect"
if sudo -u "${SUDO_USER:-arera}" env PGPASSWORD="$DB_PASS" \
     psql -h 127.0.0.1 -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT 1" >/dev/null 2>&1; then
  echo "    connected over TCP as $DB_USER"
else
  echo "    could NOT connect as $DB_USER over 127.0.0.1:5432."
  echo "    pg_hba.conf probably has no host entry for this role."
  echo "    Showing the relevant lines so it can be fixed:"
  grep -vE "^\s*#|^\s*$" /etc/postgresql/*/main/pg_hba.conf | sed "s/^/      /"
  exit 1
fi

# ------------------------------------------------------------------ systemd
say "systemd unit"
install -m 644 "$APP/deploy/forge-api.service" /etc/systemd/system/forge-api.service
systemctl daemon-reload
systemctl enable forge-api >/dev/null
echo "    forge-api.service installed and enabled"

# -------------------------------------------------------------------- nginx
say "nginx site"
install -m 644 "$APP/deploy/forge-api.nginx" /etc/nginx/sites-available/forge-api
ln -sfn /etc/nginx/sites-available/forge-api /etc/nginx/sites-enabled/forge-api

# The TLS block references certificates that do not exist yet, so the config
# will not validate until certbot has run. Serve plain HTTP first, let certbot
# issue, then put the real config in place.
if [[ ! -d /etc/letsencrypt/live/$DOMAIN ]]; then
  say "No certificate yet — issuing one"
  cat > /etc/nginx/sites-available/forge-api <<NGINX
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;
    location /.well-known/acme-challenge/ { root /var/www/html; }
    location / { return 200 'forge: awaiting certificate\n'; add_header Content-Type text/plain; }
}
NGINX
  nginx -t && systemctl reload nginx
  certbot certonly --webroot -w /var/www/html -d "$DOMAIN" \
    --non-interactive --agree-tos --register-unsafely-without-email
  install -m 644 "$APP/deploy/forge-api.nginx" /etc/nginx/sites-available/forge-api
fi

nginx -t
systemctl reload nginx
echo "    nginx reloaded"

say "Done. Next, as arera:"
echo "    cd $APP"
echo "    .venv/bin/python manage.py migrate"
echo "    .venv/bin/python manage.py collectstatic --noinput"
echo "    sudo systemctl start forge-api"
