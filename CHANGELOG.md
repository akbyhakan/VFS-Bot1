# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- TLS fingerprinting bypass using curl-cffi
- Canvas, WebGL, and Audio Context fingerprinting bypass
- Human behavior simulation with Bézier curve mouse movements
- Cloudflare challenge detection and bypass (Waiting Room, Turnstile, Browser Check)
- JWT session management with auto-refresh
- Dynamic header rotation with consistent User-Agent/Sec-CH-UA
- Proxy rotation system with failure tracking
- Anti-detection test suite
- CI/CD pipeline with GitHub Actions
- Security policy (SECURITY.md)
- Contributing guidelines (CONTRIBUTING.md)
- Issue and PR templates
- Pre-commit hooks configuration
- Development requirements (requirements-dev.txt)
- Linting and formatting configuration (pyproject.toml)
- This CHANGELOG file

### Changed
- Updated README.md with correct copyright information
- Improved project structure documentation
- Enhanced bot with anti-detection features integration

### Removed
- Removed notes.txt from repository (development notes)

## [1.0.0] - 2025-01-09

### Added
- Initial release
- Automated VFS appointment checking
- Playwright-based browser automation
- Web dashboard with FastAPI
- Multi-channel notifications (Telegram, Email)
- Multiple captcha solver support
- SQLite database for tracking
- Docker support
- Multi-user and multi-centre support

[Unreleased]: https://github.com/akbyhakan/VFS-Bot1/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/akbyhakan/VFS-Bot1/releases/tag/v1.0.0
