# Security Policy

## Supported Versions

We release patches for security vulnerabilities. Which versions are eligible for receiving such patches depends on the CVSS v3.0 Rating:

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

Please report (suspected) security vulnerabilities through [GitHub Security Advisories](https://github.com/akbyhakan/VFS-Bot1/security/advisories/new) or contact the repository owner directly. You will receive a response from us within 48 hours. If the issue is confirmed, we will release a patch as soon as possible depending on complexity.

### What to include in your report

- Type of issue (e.g. buffer overflow, SQL injection, cross-site scripting, etc.)
- Full paths of source file(s) related to the manifestation of the issue
- The location of the affected source code (tag/branch/commit or direct URL)
- Any special configuration required to reproduce the issue
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue, including how an attacker might exploit it

### Security Best Practices for Users

1. **Never commit credentials**: Always use `.env` file (gitignored)
2. **Use app passwords**: For Gmail, generate app-specific password
3. **Secure API keys**: Don't share captcha API keys publicly
4. **Update regularly**: Keep dependencies up to date
5. **Run in isolated environment**: Use Docker for isolation
6. **Enable 2FA**: Use two-factor authentication where possible

## Known Security Considerations

- **Credential Storage**: All sensitive data must be stored in `.env` file
- **API Keys**: Captcha solver API keys should be kept private
- **Browser Automation**: Bot runs with real browser, avoid running on untrusted networks
- **Rate Limiting**: VFS Global may implement rate limiting or CAPTCHA challenges

## Disclosure Policy

When we receive a security bug report, we will:

1. Confirm the problem and determine affected versions
2. Audit code to find similar problems
3. Prepare fixes for all supported releases
4. Release new security fix versions
