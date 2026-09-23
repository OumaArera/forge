#!/usr/bin/env bash
#
# The rest of the FORGE deployment, as the unprivileged app user.
#
#     bash /var/www/forge-api/deploy/finish.sh
#
# Run after bootstrap-root.sh. Re-runnable: migrations and collectstatic are
# both idempotent, and seeding checks before it writes.

set -euo pipefail
cd /var/www/forge-api
export DJANGO_SETTINGS_MODULE=config.settings.prod
PY=.venv/bin/python

say() { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }

say "Database migrations"
$PY manage.py migrate --noinput

say "Static files (the admin needs these)"
$PY manage.py collectstatic --noinput --clear | tail -2

say "Reference data — schools, programmes, levels, badges, skills"
$PY manage.py seed_reference_data | tail -8

say "Checking outbound mail"
$PY manage.py check_email 2>&1 | tail -12

say "Ledger integrity"
$PY manage.py verify_ledger

cat <<'NEXT'

==> Done. Two things left, and both need sudo:

    sudo systemctl start forge-api
    sudo systemctl status forge-api --no-pager

Then create your account:

    cd /var/www/forge-api
    DJANGO_SETTINGS_MODULE=config.settings.prod .venv/bin/python manage.py \
      bootstrap_admin --email st02353422025@students.ouk.ac.ke \
                      --name "John Ouma" --programme BSC-CSDF --year 3 \
                      --slug john-ouma

It prints a generated password once. Change it after the first sign-in.
NEXT
