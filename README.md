# 🤖 VFS-Bot - Automated VFS Appointment Booking

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Playwright](https://img.shields.io/badge/automation-Playwright-green.svg)](https://playwright.dev/)
[![CI](https://github.com/akbyhakan/VFS-Bot1/workflows/CI/badge.svg)](https://github.com/akbyhakan/VFS-Bot1/actions)
[![codecov](https://codecov.io/gh/akbyhakan/VFS-Bot1/branch/main/graph/badge.svg)](https://codecov.io/gh/akbyhakan/VFS-Bot1)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)

An advanced, modern automated bot for checking and booking VFS Global visa appointment slots. Built with **Python 3.11+**, **Playwright**, and **FastAPI** for a robust, efficient, and user-friendly experience.

## ✨ Features

- 🎯 **Automated Slot Checking** - Continuously monitors available appointment slots
- 🚀 **Playwright Automation** - Faster and more reliable than Selenium with stealth mode
- 📊 **Web Dashboard** - Real-time monitoring and control via browser
- 🔔 **Multi-Channel Notifications** - Telegram and Email alerts
- 🧩 **Multiple Captcha Solvers** - Support for 2captcha, anticaptcha, nopecha, and manual solving
- 👥 **Multi-User Support** - Handle multiple users and centres simultaneously
- 🗄️ **SQLite Database** - Track users, appointments, and logs
- 🐳 **Docker Support** - Easy deployment with Docker and Docker Compose
- ⚙️ **YAML Configuration** - Simple configuration with environment variable support
- 🔒 **Secure** - Credentials stored in environment variables

## 🛡️ Anti-Detection Features

### TLS Fingerprinting Bypass
- Uses curl-cffi to mimic real Chrome TLS handshake
- Bypasses JA3 fingerprint detection
- Playwright stealth mode enabled

### Browser Fingerprinting Protection
- **Canvas**: Noise injection to randomize fingerprint
- **WebGL**: Vendor/renderer spoofing
- **Audio Context**: Timing randomization
- **Navigator**: WebDriver flag hidden

### Human Behavior Simulation
- **Mouse**: Bézier curve movements (15-30 steps)
- **Typing**: Variable speed (40-80 WPM)
- **Clicking**: Random delays (0.1-0.5s) and position variance
- **Scrolling**: Natural chunked scrolling

### Cloudflare Bypass
- Automatic Waiting Room handling (max 30s)
- Turnstile challenge support
- Browser check auto-pass
- 403/503 error recovery with exponential backoff

### Session & Token Management
- JWT token auto-capture and refresh
- Session persistence (data/session.json)
- Token expiry prediction (5-min buffer)

### Proxy Support (Optional)
- Multi-proxy rotation from file
- Automatic failover on errors
- Supports http/socks5 with auth

## 📋 Requirements

- Python 3.11 or higher
- Modern web browser (Chromium installed automatically by Playwright)
- Internet connection
- VFS Global account

## 🚀 Quick Start

### Option 1: Using pip (Local Installation)

1. **Clone the repository**
   ```bash
   git clone https://github.com/akbyhakan/VFS-Bot1.git
   cd VFS-Bot1
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

4. **Configure the bot**
   ```bash
   cp config/config.example.yaml config/config.yaml
   cp .env.example .env
   ```
   
   Edit `config/config.yaml` and `.env` with your details.

5. **Run the bot**
   ```bash
   # Run with web dashboard (recommended)
   python main.py --mode web
   
   # Run in automated mode only
   python main.py --mode bot
   
   # Run both
   python main.py --mode both
   ```

6. **Access the dashboard**
   
   Open your browser and navigate to: `http://localhost:8000`

### Option 2: Using Docker

1. **Clone and configure**
   ```bash
   git clone https://github.com/akbyhakan/VFS-Bot1.git
   cd VFS-Bot1
   cp .env.example .env
   ```
   
   Edit `.env` with your credentials.

2. **Run with Docker Compose**
   ```bash
   docker-compose up -d
   ```

3. **Access the dashboard**
   
   Open your browser: `http://localhost:8000`

4. **View logs**
   ```bash
   docker-compose logs -f vfs-bot
   ```

## ⚙️ Configuration

### Environment Variables (.env)

```env
# VFS Credentials
VFS_EMAIL=your_email@example.com
VFS_PASSWORD=your_password

# Telegram Notifications (optional)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Email Notifications (optional)
EMAIL_SENDER=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
EMAIL_RECEIVER=receiver@example.com

# Captcha Service (optional)
CAPTCHA_API_KEY=your_captcha_api_key
```

### Configuration File (config/config.yaml)

```yaml
vfs:
  base_url: "https://visa.vfsglobal.com"
  country: "tur"  # Country code
  mission: "deu"  # Mission code
  centres:
    - "Istanbul"
    - "Ankara"
  category: "Schengen Visa"
  subcategory: "Tourism"

bot:
  check_interval: 30  # Seconds between checks
  headless: false     # Run browser in background
  screenshot_on_error: true
  max_retries: 3

captcha:
  provider: "manual"  # Options: 2captcha, anticaptcha, nopecha, manual
  manual_timeout: 120

notifications:
  telegram:
    enabled: true
  email:
    enabled: false

anti_detection:
  enabled: true  # Master switch
  tls_bypass: true
  fingerprint_bypass: true
  human_simulation: true

cloudflare:
  enabled: true
  max_wait_time: 30  # seconds
  
proxy:
  enabled: false  # Set true to use proxies
  file: "config/proxies.txt"
```

All anti-detection features are configurable via `config/config.yaml`:

```yaml
anti_detection:
  enabled: true  # Master switch
  tls_bypass: true
  fingerprint_bypass: true
  human_simulation: true
  stealth_mode: true

cloudflare:
  enabled: true
  max_wait_time: 30
  max_retries: 3
  manual_captcha: false

proxy:
  enabled: false
  file: "config/proxies.txt"
  rotate_on_error: true

human_behavior:
  mouse_movement_steps: 20
  typing_wpm_range: [40, 80]
  click_delay_range: [0.1, 0.5]
  random_actions: true

session:
  save_file: "data/session.json"
  token_refresh_buffer: 5
```

## 📊 Web Dashboard

The web dashboard provides:

- **Real-time Status** - See bot running status
- **Statistics** - Slots found, appointments booked
- **Live Logs** - Monitor bot activity in real-time
- **Controls** - Start/Stop bot with one click

## 🔧 Usage Examples

### Using the Command Line

```bash
# Run with web dashboard on custom port
python main.py --mode web

# Run in bot-only mode with debug logging
python main.py --mode bot --log-level DEBUG

# Use custom config file
python main.py --config /path/to/config.yaml
```

### Using the API

The web dashboard exposes a REST API:

- `GET /api/status` - Get current bot status
- `POST /api/bot/start` - Start the bot
- `POST /api/bot/stop` - Stop the bot
- `GET /api/logs` - Get recent logs
- `WebSocket /ws` - Real-time updates

Example:
```bash
# Get status
curl http://localhost:8000/api/status

# Start bot
curl -X POST http://localhost:8000/api/bot/start

# Stop bot
curl -X POST http://localhost:8000/api/bot/stop
```

## 🏥 Health & Monitoring

### Health Check
The web dashboard exposes a health check endpoint for container orchestration:

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2026-01-09T15:30:00Z",
  "version": "2.0.0",
  "components": {
    "database": true,
    "bot": true,
    "notifications": true
  }
}
```

### Metrics
Monitor bot performance via metrics endpoint:

```bash
curl http://localhost:8000/metrics
```

### Structured Logging
Enable JSON logging for production:

```bash
export JSON_LOGGING=true
python main.py
```

Logs are written to `logs/vfs_bot.jsonl` in JSON format for easy parsing.

### Rate Limiting
Global rate limiting prevents overloading VFS servers:
- Default: 60 requests per 60 seconds
- Automatic backoff when limit reached
- Configurable via `RateLimiter` class
```

## 🧪 Testing

Run the test suite:

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/test_bot.py -v
```

## 📁 Project Structure

```
VFS-Bot1/
├── src/                      # Core bot modules
│   ├── bot.py               # Main bot logic with Playwright
│   ├── captcha_solver.py    # Captcha solving
│   ├── notification.py      # Telegram & Email notifications
│   ├── database.py          # SQLite operations
│   ├── centre_fetcher.py    # Auto-fetch centres
│   └── config_loader.py     # YAML config loader
├── web/                      # Web dashboard
│   ├── app.py               # FastAPI application
│   ├── static/              # CSS, JavaScript
│   └── templates/           # HTML templates
├── config/                   # Configuration files
├── tests/                    # Test suite
├── logs/                     # Log files (gitignored)
├── screenshots/             # Screenshots (gitignored)
├── main.py                  # Entry point
├── requirements.txt         # Python dependencies
├── Dockerfile               # Docker configuration
└── docker-compose.yml       # Docker Compose setup
```

## 🔐 Security Best Practices

1. **Never commit credentials** - Use `.env` file (gitignored)
2. **Use app passwords** - For Gmail, generate an app-specific password
3. **Secure your API keys** - Don't share captcha API keys
4. **Run in Docker** - Isolate the bot environment
5. **Update regularly** - Keep dependencies up to date

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

```
MIT License

Copyright (c) 2025 akbyhakan

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
```

## 📧 Contact & Support

- **Author**: akbyhakan
- **GitHub**: [akbyhakan/VFS-Bot1](https://github.com/akbyhakan/VFS-Bot1)
- **Issues**: [Report a bug](https://github.com/akbyhakan/VFS-Bot1/issues)

## ⚠️ Disclaimer

This bot is for educational purposes only. Use at your own risk. The authors are not responsible for any misuse or damage caused by this program. Always comply with VFS Global's terms of service.

## 🙏 Acknowledgments

- [Playwright](https://playwright.dev/) - Modern browser automation
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - Telegram API wrapper

---

**Star ⭐ this repository if you find it helpful!**
