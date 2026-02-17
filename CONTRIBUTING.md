# Contributing to VFS-Bot

First off, thank you for considering contributing to VFS-Bot! 🎉

## Code of Conduct

This project and everyone participating in it is governed by respect and professionalism. By participating, you are expected to uphold this standard.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check existing issues. When creating a bug report, include:

- **Use a clear and descriptive title**
- **Describe the exact steps to reproduce the problem**
- **Provide specific examples**
- **Describe the behavior you observed**
- **Explain which behavior you expected to see**
- **Include screenshots if relevant**
- **Include your environment details** (OS, Python version, etc.)

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion:

- **Use a clear and descriptive title**
- **Provide a detailed description of the suggested enhancement**
- **Provide specific examples to demonstrate the enhancement**
- **Describe the current behavior and expected behavior**

### Pull Requests

1. **Fork the repo** and create your branch from `main`
2. **Install dependencies**: `pip install -r requirements-dev.txt`
3. **Install pre-commit hooks**: `pre-commit install`
4. **Make your changes**
5. **Add tests** if applicable
6. **Ensure the test suite passes**: `pytest tests/`
7. **Ensure code is formatted**: `black .`
8. **Ensure linting passes**: `flake8 .`
9. **Update documentation** if needed
10. **Commit your changes** using meaningful commit messages
11. **Push to your fork** and submit a pull request

#### Commit Message Guidelines

- Use present tense ("Add feature" not "Added feature")
- Use imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit first line to 72 characters
- Reference issues and pull requests liberally

Examples:
```
feat: Add support for multiple VFS centres
fix: Resolve captcha timeout issue
docs: Update installation instructions
test: Add tests for notification module
```

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR-USERNAME/VFS-Bot1.git
cd VFS-Bot1

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies (Option 1: Using requirements.txt)
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install dependencies (Option 2: Using pyproject.toml - PEP 517/518 compliant)
pip install -e ".[dev]"

# Alternative: Install without dev dependencies
pip install -e .

# After adding/changing dependencies in requirements.txt:
make lock

# Install Playwright browsers
playwright install chromium

# Install pre-commit hooks
pre-commit install

# Run tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

**Note:** When adding or changing dependencies:
- Update both `pyproject.toml` and `requirements.txt` to keep them synchronized
- Run `make lock` to regenerate `requirements.lock`
- Run `make verify-lock` to verify consistency

## Code Style

- Follow PEP 8 guidelines
- Use Black for code formatting
- Use type hints where applicable
- Write docstrings for functions and classes
- Keep functions focused and small
- Write meaningful variable names

## Testing

- Write tests for new features
- Maintain test coverage above 80%
- Use pytest fixtures for common setup
- Mock external dependencies (Playwright, API calls)

## Documentation

- Update README.md if needed
- Add docstrings to new functions/classes
- Update configuration examples
- Add inline comments for complex logic

## Questions?

Feel free to open an issue with the `question` label.

Thank you for your contributions! 🚀
