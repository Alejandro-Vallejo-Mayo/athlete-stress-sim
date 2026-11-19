# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| `1.0.x` | Yes |
| `< 1.0` | No |

## Reporting a vulnerability

Please report security issues privately through
[GitHub Security Advisories](https://github.com/Alejandro-Vallejo-Mayo/athlete-stress-sim/security/advisories/new).

Do not open a public issue for a vulnerability, and do not include real tokens,
credentials, FIT files or personal biometric data in a report. Use synthetic
examples or redact sensitive values.

## Deployment model and scope

Athlete Stress Sim is a single-user, local-first application:

- The API and dashboard have no authentication, TLS or multi-user isolation.
- The deployment assumes localhost or a trusted local network.
- Do not expose ports `8000` or `8050` to the public internet.
- DuckDB is a single local file with a single-writer model.

If the service is moved off localhost, add authentication, TLS, a reverse proxy
and a shared-state design before exposing it.

## Secrets and data

- `.env`, OAuth tokens, raw FIT files, the DuckDB database and real biometric
  captures must never be committed.
- OAuth tokens are stored in plaintext in DuckDB. Protect the `data/` directory
  and `.env` with appropriate filesystem permissions.
- The repository uses synthetic FIT fixtures and temporary databases for tests.
- Dashboard screenshots published in the documentation must be reviewed and
  sanitized before release.

## Out of scope

The following are outside the current security model:

- Attacks that require access to an already-trusted local machine.
- Multi-tenant authorization or tenant isolation.
- Denial-of-service protection on the local API.
- Clinical, medical or injury-prevention claims.
