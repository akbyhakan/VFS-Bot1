.PHONY: help install install-dev lint format test test-cov clean docker-test pre-commit generate-secrets validate-config security-check

help:
	@echo "Available commands:"
	@echo "  make install          - Install production dependencies"
	@echo "  make install-dev      - Install development dependencies"
	@echo "  make lint             - Run linting checks"
	@echo "  make format           - Format code with black and isort"
	@echo "  make test             - Run tests"
	@echo "  make test-cov         - Run tests with coverage report"
	@echo "  make clean            - Clean build artifacts and cache"
	@echo "  make docker-test      - Run tests in Docker"
	@echo "  make pre-commit       - Run pre-commit hooks"
	@echo "  make generate-secrets - Generate secure secrets for .env"
	@echo "  make validate-config  - Validate configuration files"
	@echo "  make security-check   - Run security checks"

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

generate-secrets:
	python scripts/generate_secrets.py

validate-config:
	python -c "from src.core.config_loader import load_config; from src.core.config_validator import ConfigValidator; c = load_config('config/config.yaml'); print('Valid' if ConfigValidator.validate(c) else 'Invalid')"

security-check:
	pip install safety bandit
	safety check
	bandit -r src/ -ll
