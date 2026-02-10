.PHONY: help install install-dev lint format test test-cov clean docker-test pre-commit db-init db-migrate db-upgrade db-downgrade db-history db-current

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

lock:  ## Generate requirements.lock for reproducible deployments
	pip freeze > requirements.lock
	@echo "✅ requirements.lock updated"
