# VU Study Support Pro

Responsive public site + SQLite-powered administration with CRUD for services, packages, FAQs, testimonials, inquiries, and site settings. Built with Python standard library; no third-party dependencies.

## Start locally

Python 3.10+ required. In the project folder:

```bash
export ADMIN_USER=admin
export ADMIN_PASSWORD='replace-with-a-long-random-password'
python app.py
```

Windows PowerShell:

```powershell
$env:ADMIN_USER='admin'
$env:ADMIN_PASSWORD='replace-with-a-long-random-password'
python app.py
```

Open http://127.0.0.1:8000 and http://127.0.0.1:8000/admin.

## Deployment and security

This is a working MVP, **not a security-audited production service**. Use HTTPS and a persistent disk for SQLite; do not deploy to ephemeral serverless storage. Configure `HOST=0.0.0.0`, `PORT`, `SECURE_COOKIES=1`, and `ADMIN_PASSWORD_HASH` (preferred) via secret environment variables. Generate the hash using:

```bash
python -c "import secrets,hashlib,getpass; s=secrets.token_bytes(16);p=getpass.getpass();print(s.hex()+':'+hashlib.pbkdf2_hmac('sha256',p.encode(),s,310000).hex())"
```

Sessions are in process memory and reset on restart. Run **one process**. Use a reverse proxy for HTTPS, IP-based rate limiting, request logging, backups, and operational monitoring. Do not publicly launch with real student data before adding persistent sessions, admin login rate limiting, privacy notice and consent, retention controls, and comprehensive security review. The inquiry endpoint uses a honeypot but requires external rate limiting to prevent spam. Testimonials must only be published with permission.

## ISO/IEC 9126 quality mapping

- Functionality: CRUD APIs, validated inquiries, site configuration.
- Reliability: SQLite transactions, WAL, basic health endpoint.
- Usability: responsive layout, keyboard focus, semantic labels.
- Efficiency: dependency-free app, small static assets, limited query sizes.
- Maintainability: separate data, API, JS and CSS; unit tests.
- Portability: Python 3.10+, SQLite, Docker or VM hosting.

**This mapping is not ISO/IEC 9126 certification or proof of full compliance.** The standard is superseded by the ISO/IEC 25010 quality model. Formal accessibility, security, load, browser, recovery and maintainability testing remains necessary.

## Tests

`python -m unittest discover -s tests -v`
