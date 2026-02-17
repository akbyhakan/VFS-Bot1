.PHONY: help install install-editable install-dev install-dev-editable lint format test test-cov clean docker-test pre-commit db-init db-migrate db-upgrade db-downgrade db-history db-current lock verify-lock security

help:
	@echo "Available commands:"
	@echo "  make install             - Install production dependencies from requirements.txt"
	@echo "  make install-editable    - Install as editable package using pyproject.toml (alternative to 'install')"
	@echo "  make install-dev         - Install development dependencies from requirements*.txt"
	@echo "  make install-dev-editable - Install as editable package with dev deps using pyproject.toml (alternative to 'install-dev')"
	@echo "  make lint                - Run linting checks"
	@echo "  make format              - Format code with black and isort"
	@echo "  make test                - Run tests"
	@echo "  make test-cov            - Run tests with coverage report"
	@echo "  make clean               - Clean build artifacts and cache"
	@echo "  make docker-test         - Run tests in Docker"
	@echo "  make pre-commit          - Run pre-commit hooks"
	@echo "  make db-init             - Initialize database (first time setup via Alembic)"
	@echo "  make db-migrate          - Generate new migration (usage: make db-migrate msg='description')"
	@echo "  make db-upgrade          - Apply pending migrations"
	@echo "  make db-downgrade        - Rollback last migration"
	@echo "  make db-history          - Show migration history"
	@echo "  make db-current          - Show current migration version"
	@echo "  make lock                - Generate requirements.lock for reproducible deployments"
	@echo "  make verify-lock         - Verify requirements.lock is consistent with requirements.txt"
	@echo "  make security            - Run security scans (bandit + safety)"

install:
	pip install -r requirements.txt

install-editable:  ## Install as editable package (alternative to 'install')
	pip install -e .

install-dev:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
	playwright install chromium
	pre-commit install

install-dev-editable:  ## Install as editable package with dev deps (alternative to 'install-dev')
	pip install -e ".[dev]"
	playwright install chromium
	pre-commit install

lint:
	black --check .
	flake8 .
	mypy src/

format:
	black .
	isort .

test:
	pytest tests/

test-cov:
	pytest tests/ --cov=src --cov-report=xml --cov-report=html --cov-report=term-missing

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf htmlcov coverage.xml .coverage
	rm -rf dist build *.egg-info

docker-test:
	docker-compose -f docker-compose.dev.yml run --rm vfs-bot-test

pre-commit:
	pre-commit run --all-files

# Database migration commands (Alembic)
db-init:
	@echo "Initializing database schema via Alembic..."
	alembic upgrade head
	@echo "Database schema initialized successfully."

db-migrate:
	alembic revision --autogenerate -m "$(msg)"

db-upgrade:
	alembic upgrade head

db-downgrade:
	alembic downgrade -1

db-history:
	alembic history --verbose

db-current:
	alembic current

lock:  ## Regenerate requirements.lock from requirements.txt
	pip install -r requirements.txt
	@echo "# Auto-generated lock file - DO NOT EDIT MANUALLY" > requirements.lock
	@echo "# Generated from requirements.txt for reproducible builds" >> requirements.lock
	@echo "# To regenerate: make lock" >> requirements.lock
	@echo "# To verify: make verify-lock" >> requirements.lock
	@echo "" >> requirements.lock
	@echo "# Core packages from requirements.txt (pinned versions)" >> requirements.lock
	pip freeze >> requirements.lock
	@echo "✅ requirements.lock regenerated from requirements.txt"

verify-lock:  ## Verify requirements.lock consistency with requirements.txt
	@echo "🔍 Verifying requirements.lock against requirements.txt..."
	@python3 scripts/verify_lock.py

security:  ## Run security scans (bandit + safety)
	@echo "🔒 Running security scans..."
	@echo "\n=== Bandit Static Analysis ==="
	@bandit -r src/ --severity-level medium; \
	BANDIT_EXIT=$$?; \
	if [ $$BANDIT_EXIT -eq 0 ]; then \
		echo "✅ Bandit: No issues found"; \
	elif [ $$BANDIT_EXIT -eq 1 ]; then \
		echo "⚠️  Bandit: Security issues detected (see above)"; \
	else \
		echo "❌ Bandit: Scan failed with exit code $$BANDIT_EXIT"; \
	fi
	@echo "\n=== Safety Vulnerability Check ==="
	@safety check; \
	SAFETY_EXIT=$$?; \
	if [ $$SAFETY_EXIT -eq 0 ]; then \
		echo "✅ Safety: No vulnerabilities found"; \
	elif [ $$SAFETY_EXIT -eq 64 ]; then \
		echo "⚠️  Safety: Vulnerabilities detected (see above)"; \
	else \
		echo "❌ Safety: Check failed with exit code $$SAFETY_EXIT"; \
	fi
	@echo "\n✅ Security scan complete"
