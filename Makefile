.PHONY: help install install-dev lint format test test-cov clean docker-test pre-commit db-init db-migrate db-upgrade db-downgrade db-history db-current lock verify-lock security

help:
	@echo "Available commands:"
	@echo "  make install      - Install production dependencies"
	@echo "  make install-dev  - Install development dependencies"
	@echo "  make lint         - Run linting checks"
	@echo "  make format       - Format code with black and isort"
	@echo "  make test         - Run tests"
	@echo "  make test-cov     - Run tests with coverage report"
	@echo "  make clean        - Clean build artifacts and cache"
	@echo "  make docker-test  - Run tests in Docker"
	@echo "  make pre-commit   - Run pre-commit hooks"
	@echo "  make db-init      - Initialize database (first time setup via Alembic)"
	@echo "  make db-migrate   - Generate new migration (usage: make db-migrate msg='description')"
	@echo "  make db-upgrade   - Apply pending migrations"
	@echo "  make db-downgrade - Rollback last migration"
	@echo "  make db-history   - Show migration history"
	@echo "  make db-current   - Show current migration version"
	@echo "  make lock         - Generate requirements.lock for reproducible deployments"
	@echo "  make verify-lock  - Verify requirements.lock is consistent with requirements.txt"
	@echo "  make security     - Run security scans (bandit + safety)"

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
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
	pip freeze > requirements.lock
	@echo "✅ requirements.lock regenerated from requirements.txt"

verify-lock:  ## Verify requirements.lock consistency with requirements.txt
	@echo "🔍 Verifying requirements.lock against requirements.txt..."
	@python3 -c "\
import re; \
import sys; \
\
# Read requirements.txt and extract main packages with their constraints \
with open('requirements.txt') as f: \
    req_lines = [l.strip() for l in f if l.strip() and not l.startswith('#')]; \
\
# Parse package names and version constraints from requirements.txt \
req_packages = {}; \
for line in req_lines: \
    if '[' in line:  # Handle extras like sqlalchemy[asyncio] \
        pkg = line.split('[')[0].lower(); \
        constraint = line.split(']')[1] if ']' in line else ''; \
    else: \
        match = re.match(r'^([a-zA-Z0-9_-]+)', line); \
        if match: \
            pkg = match.group(1).lower(); \
            constraint = line[len(match.group(1)):]; \
        else: \
            continue; \
    req_packages[pkg] = constraint.strip(); \
\
# Read requirements.lock and extract versions \
with open('requirements.lock') as f: \
    lock_lines = [l.strip() for l in f if l.strip() and not l.startswith('#') and '==' in l]; \
\
lock_packages = {}; \
for line in lock_lines: \
    pkg, version = line.split('=='); \
    lock_packages[pkg.lower()] = version; \
\
# Check critical packages from requirements.txt \
errors = []; \
for pkg, constraint in req_packages.items(): \
    pkg_norm = pkg.replace('_', '-').replace('.', '-'); \
    lock_pkg = None; \
    for lpkg in lock_packages: \
        if lpkg.replace('_', '-').replace('.', '-') == pkg_norm: \
            lock_pkg = lpkg; \
            break; \
    \
    if not lock_pkg: \
        errors.append(f'❌ {pkg} missing from requirements.lock'); \
        continue; \
    \
    lock_version = lock_packages[lock_pkg]; \
    \
    # Validate version constraints \
    if '==' in constraint: \
        expected = constraint.replace('==', ''); \
        if lock_version != expected: \
            errors.append(f'❌ {pkg}: expected {expected}, got {lock_version}'); \
    elif '~=' in constraint: \
        expected_base = constraint.replace('~=', '').strip(); \
        # Compatible release: should match major.minor \
        if not lock_version.startswith(expected_base.rsplit('.', 1)[0]): \
            errors.append(f'❌ {pkg}: ~={expected_base} not compatible with {lock_version}'); \
\
if errors: \
    print('\\n'.join(errors)); \
    sys.exit(1); \
else: \
    print('✅ All package versions in requirements.lock are consistent with requirements.txt'); \
"

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
