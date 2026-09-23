# FORGE — common tasks.
#
# `make dev` is the one to remember: it brings up the API and the web client
# together. Everything else is here so that a new maintainer does not have to
# find the right incantation in a README.

VENV := .venv/bin
MANAGE := $(VENV)/python manage.py

.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install: ## Install backend and frontend dependencies
	python3 -m venv .venv
	$(VENV)/pip install -r requirements.txt
	cd web && npm install

.PHONY: dev
dev: ## Run the API and the web client together
	@trap 'kill 0' EXIT; \
	$(MANAGE) runserver & \
	(cd web && npm run dev) & \
	wait

.PHONY: api
api: ## Run the API only
	$(MANAGE) runserver

.PHONY: web
web: ## Run the web client only
	cd web && npm run dev

.PHONY: migrate
migrate: ## Apply database migrations
	$(MANAGE) migrate

.PHONY: seed
seed: ## Seed reference data (schools, levels, badges, skills)
	$(MANAGE) seed_reference_data

.PHONY: demo
demo: ## Fill a development instance with believable data
	$(MANAGE) seed_demo

.PHONY: demo-wipe
demo-wipe: ## Remove the demo data again
	$(MANAGE) seed_demo --wipe

.PHONY: test
test: ## Run the backend test suite
	$(VENV)/python -m pytest -q

.PHONY: check
check: ## Everything CI would run
	$(VENV)/ruff check .
	$(MANAGE) makemigrations --check --dry-run
	$(VENV)/python -m pytest -q
	cd web && npm run build

.PHONY: types
types: ## Regenerate the frontend's API types from the backend
	cd web && npm run api:types

.PHONY: ledger
ledger: ## Verify the contribution ledger's hash chain
	$(MANAGE) verify_ledger

.PHONY: mail
mail: ## Diagnose outbound email (add TO=someone@example.com to send)
	@if [ -n "$(TO)" ]; then $(MANAGE) check_email --to $(TO); else $(MANAGE) check_email; fi

.PHONY: admin
admin: ## Create or update the founding student-administrator account
	$(MANAGE) bootstrap_admin --email $(EMAIL) --name "$(NAME)"

.PHONY: reset
reset: ## Wipe and rebuild a development database with demo data
	$(MANAGE) flush --noinput
	$(MANAGE) seed_reference_data
	$(MANAGE) seed_demo

# ---------------------------------------------------------------- deployment

HOST ?= arera@159.89.235.222
REMOTE ?= /var/www/forge-api
RUN = ssh $(HOST) 'cd $(REMOTE) && DJANGO_SETTINGS_MODULE=config.settings.prod .venv/bin/python manage.py

.PHONY: deploy
deploy: ## Deploy the API to forge-api.zafrika.com
	./scripts/deploy.sh

.PHONY: deploy-fast
deploy-fast: ## Deploy without reinstalling dependencies
	./scripts/deploy.sh --no-deps

.PHONY: prod-logs
prod-logs: ## Tail the production service log
	ssh $(HOST) 'sudo -n /usr/bin/journalctl -u forge-api -n 120 --no-pager'

.PHONY: prod-status
prod-status: ## Is it running, and since when
	ssh $(HOST) 'sudo -n /usr/bin/systemctl status forge-api --no-pager | head -12'

.PHONY: prod-restart
prod-restart: ## Restart gunicorn on the server
	ssh $(HOST) 'sudo -n /usr/bin/systemctl restart forge-api && sleep 3 && \
	  sudo -n /usr/bin/systemctl is-active forge-api'

.PHONY: prod-shell
prod-shell: ## A Django shell on the production database
	$(RUN) shell'

.PHONY: prod-mail-check
prod-mail-check: ## Diagnose outbound mail from the server (ports, config)
	$(RUN) check_email'

.PHONY: prod-ledger
prod-ledger: ## Verify the production contribution ledger
	$(RUN) verify_ledger'

.PHONY: prod-backup
prod-backup: ## Dump the production database to ./backups/
	@mkdir -p backups
	ssh $(HOST) 'sudo -n /usr/bin/su - postgres -c "pg_dump -Fc forge"' \
	  > backups/forge-$$(date +%Y%m%d-%H%M%S).dump
	@ls -lh backups/ | tail -1
