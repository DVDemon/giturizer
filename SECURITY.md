# Security Policy

## Reporting a vulnerability

Please report security issues privately via **GitHub Security Advisories**
("Report a vulnerability" in the Security tab) rather than a public issue.

## Secrets and credentials

- The repository must never contain real GitLab/GitHub tokens, private keys or
  production credentials.
- GitLab access tokens entered in the UI are stored **encrypted** (Fernet) and are
  never returned by the API; clone errors are redacted.
- Values in `.env.example` and `docker-compose.yml` (`archdiscovery` passwords,
  `dev-insecure-change-me` key) are **development defaults only**. Set strong
  values via `.env` before any non-local deployment.
- If a token is exposed, revoke it in GitLab/GitHub, rotate `TOKEN_ENCRYPTION_KEY`
  (existing project tokens become unreadable — recreate projects) and follow the
  runbook.

## Supported versions

The latest `main` branch is supported with security fixes.
