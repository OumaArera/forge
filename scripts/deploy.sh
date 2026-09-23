#!/usr/bin/env bash
#
# Redeploy the FORGE API to forge-api.zafrika.com.
#
# Idempotent. Syncs code, installs any new dependencies, migrates, collects
# static files and restarts gunicorn. It does NOT touch the database contents,
# the .env, nginx or the TLS certificate — those were set up once and are
# described in docs/deployment.md.
#
#   ./scripts/deploy.sh              # full redeploy
#   ./scripts/deploy.sh --no-deps    # skip pip install (faster, code only)
#
set -euo pipefail

HOST="${FORGE_HOST:-arera@159.89.235.222}"
REMOTE="${FORGE_REMOTE:-/var/www/forge-api}"
URL="${FORGE_URL:-https://forge-api.zafrika.com}"

SKIP_DEPS=0
[[ "${1:-}" == "--no-deps" ]] && SKIP_DEPS=1

say() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }

say "Checking the tree is clean enough to ship"
if git rev-parse --git-dir >/dev/null 2>&1; then
  if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "    warning: uncommitted changes will be deployed" >&2
  fi
  git --no-pager log --oneline -1 2>/dev/null || echo "    (no commits yet)"
else
  echo "    not a git repository — shipping the working tree as-is" >&2
fi

say "Running the test suite before shipping"
# A deploy that skips the tests is a deploy that eventually ships the bug the
# tests would have caught. --no-deps skips dependencies, never this.
.venv/bin/python -m pytest -q 2>&1 | tail -2

say "Syncing code to ${HOST}:${REMOTE}"
# .env, media/, staticfiles/ and the venv live on the server and are never
# overwritten from a laptop. The web client deploys separately.
rsync -az --delete \
  --exclude '.venv/' \
  --exclude '.git/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude 'media/' \
  --exclude 'staticfiles/' \
  --exclude '.env' \
  --exclude '.pytest_cache/' \
  --exclude '.ruff_cache/' \
  --exclude 'web/' \
  --exclude '*.docx' \
  ./ "${HOST}:${REMOTE}/"

say "Running remote steps"
ssh "$HOST" "export LC_ALL=C; set -e
  cd ${REMOTE}
  export DJANGO_SETTINGS_MODULE=config.settings.prod

  if [ ${SKIP_DEPS} -eq 0 ]; then
    echo '--- dependencies ---'
    .venv/bin/python -m pip install --quiet -r requirements.txt
  fi

  echo '--- checks ---'
  .venv/bin/python manage.py check --deploy --fail-level WARNING

  echo '--- migrate ---'
  .venv/bin/python manage.py migrate --noinput

  echo '--- static ---'
  .venv/bin/python manage.py collectstatic --noinput | tail -1

  # Recognition is derived from the ledger and is cheap to recompute. A
  # weighting change between releases would otherwise leave every member's
  # standing quietly wrong until somebody noticed.
  echo '--- standings ---'
  .venv/bin/python manage.py rebuild_standings | tail -1

  echo '--- restart ---'
  sudo -n /usr/bin/systemctl restart forge-api
  sleep 4
  sudo -n /usr/bin/systemctl is-active forge-api
"

say "Verifying the chain survived the deploy"
# The ledger is the thing this platform exists to protect. If a migration ever
# disturbs it, the deploy should say so rather than leave it to be discovered.
ssh "$HOST" "cd ${REMOTE} && DJANGO_SETTINGS_MODULE=config.settings.prod \
  .venv/bin/python manage.py verify_ledger" | tail -3

say "Verifying ${URL}"
for path in /healthz/ /readyz/ /api/v1/accounts/reference/ \
            /api/v1/contributions/ledger/verify/ /api/v1/portfolio/verification-key/; do
  code=$(curl -s -o /dev/null -m 20 -w '%{http_code}' "${URL}${path}")
  printf '    %-46s %s\n' "$path" "$code"
  [[ "$code" == "200" ]] || { echo "    FAILED" >&2; exit 1; }
done

say "Deployed"
