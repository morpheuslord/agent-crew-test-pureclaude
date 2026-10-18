# Design decisions

Short ADR-style entries. "Driver" says what drove the decision: the brief, my own judgment, or a
tool's output.

## D-001 Opaque server-side sessions, cookie held by the UI server

- Decision: the API issues a random 256-bit session token on login and stores only its SHA-256 hash.
  The UI server keeps the raw token in an `HttpOnly`, `SameSite=Lax`, `Secure` cookie and forwards it
  to the API as a bearer token.
- Reason: revocation (logout, password change, reset, deactivation) is immediate and simple, unlike
  stateless JWTs; a database leak does not expose usable tokens; the browser never talks to the API.
- Driver: brief (section 2 leaves this open); own judgment.

## D-002 Shared service token between UI and API

- Decision: every `/api/v1` call needs `X-Service-Token`, compared in constant time.
- Reason: defence in depth on top of network isolation, especially against server-side request
  forgery from inside the network reaching the API.
- Driver: own judgment.

## D-003 CSRF with an HMAC-bound double-submit cookie

- Decision: a random `tb_csrf` cookie and a hidden form field holding its HMAC with `UI_SECRET`,
  plus an `Origin` check when the header is present.
- Reason: works for anonymous forms (login CSRF) and logged-in forms without server-side session
  state in the UI server.
- Driver: own judgment.

## D-004 Admins are global superusers; non-readable resources return 404

- Decision: admins can read and manage every team, project and task. Callers that cannot read a
  resource get 404, not 403.
- Reason: the brief gives admins project management across teams and a global activity feed; 404
  avoids confirming that a guessed id exists.
- Driver: brief (sections 4.1, 4.3, 4.5); own judgment.

## D-005 Added `GET /api/v1/projects` and `GET /api/v1/admin/cache-stats`

- Decision: two endpoints beyond the minimum list: the caller's visible projects (dashboard "my
  projects", cached per user) and the cache counters (brief section 5 allows an internal stats endpoint).
- Reason: avoids N calls per dashboard render; gives an admin-only view of hit/miss counters.
- Driver: brief (sections 4.6, 5); own judgment.

## D-006 Unit of Work plus repository interfaces

- Decision: services depend on a `UnitOfWork` protocol exposing repository interfaces and
  `commit()`. The SQLAlchemy implementation wraps one session per request; tests use in-memory fakes.
- Reason: one transaction per use case, services testable without a database, concrete classes
  chosen only in `composition.py`.
- Driver: brief (section 8); own judgment.

## D-007 Synchronous SQLAlchemy with psycopg 3

- Decision: sync engine and sync FastAPI endpoints (run in the thread pool).
- Reason: simpler typing under `mypy --strict`, mature tooling; the load is small.
- Driver: own judgment.

## D-008 Cache invalidation through explicit keys and a per-project key index

- Decision: list pages per filter combination are registered in a Redis set per project, and a write
  deletes every key in the set. Single-object and per-user keys are deleted directly.
- Reason: the brief wants writes to invalidate the keys they affect, with TTL only as a backstop.
- Driver: brief (section 5).

## D-009 Cache and rate limiter fail open to degraded mode

- Decision: Redis errors are logged and treated as cache misses; after an error Redis is skipped for
  30 seconds. Rate limiting falls back to an in-process counter.
- Reason: the brief requires the API to keep working when Redis is down; the in-process fallback
  keeps brute-force protection per instance instead of dropping it.
- Driver: brief (section 5); own judgment.

## D-010 SSRF-guarded, signed, asynchronous webhooks

- Decision: deliveries run on a bounded thread pool after commit, `https` only by default, every
  resolved address must be public, connection pinned to the checked address, no redirects, 5 s timeout,
  3 attempts, HMAC-SHA256 signature with a per-project secret.
- Reason: the webhook URL is user-supplied and the API sits inside the VPC next to the database,
  Redis and the instance metadata service.
- Driver: brief (section 4.3); own judgment.

## D-011 Attachments stored under random keys and always downloaded as attachments

- Decision: the storage key is a random UUID; the original filename is sanitised and only used in
  `Content-Disposition`. Downloads are `application/octet-stream` with `attachment` and `nosniff`.
  Size is enforced while streaming, not from `Content-Length`.
- Reason: prevents path traversal, stored XSS from uploaded HTML/SVG and oversized uploads.
- Driver: brief (section 4.4); own judgment.

## D-012 Markdown rendered and sanitised in the UI server

- Decision: the API stores raw Markdown; the UI renders it with `marked` and sanitises the output
  with `sanitize-html` using an allow-list.
- Reason: rendering is presentation, so it belongs in the UI; sanitising the final HTML protects
  against raw HTML and `javascript:` links in Markdown.
- Driver: brief (section 4.4); own judgment.

## D-013 Account enumeration accepted for register and add-member

- Decision: register returns 409 for an existing email and add-member returns 404 for an unknown
  email. Login and forgot-password do not reveal account existence.
- Reason: an internal tool needs these to be usable without an email-verification flow; both are
  rate limited (register) or require a logged-in account (add-member).
- Driver: own judgment.

## D-014 Ruff rule selection without the bandit (`S`) set

- Decision: ruff selects `E, W, F, I, B, UP, N, SIM, RUF, C4, PT, RET, PIE, T20, DTZ, LOG`.
- Reason: the bandit set flags every `assert` in pytest tests, which would need per-file ignores, and
  section 10 forbids rule-silencing configuration. Security review is done by hand instead (see
  `evaluation/tool-log.md`).
- Driver: brief (section 10); own judgment.

## D-015 Toolchain without Docker in the build session

- Decision: integration tests read `TEST_DATABASE_URL` and `TEST_REDIS_URL`; locally they ran against
  native PostgreSQL 16 and Redis 7 processes, in CI against service containers.
- Reason: Docker was not usable in the build session (socket permission denied).
- Driver: environment.

## D-016 Semgrep and Trivy workflows in addition to CodeQL and Codacy

- Decision: `semgrep.yml` runs 18 Semgrep registry packs (including `p/terraform`, `p/dockerfile`,
  `p/github-actions`) over every tracked file; `trivy.yml` runs a filesystem scan (vulnerabilities in
  both lockfiles including dev dependencies, secrets, misconfiguration) and a dedicated Terraform scan
  of `infra/`. Each uploads SARIF to GitHub code scanning under its own category. Both scanners run from
  official images pinned by digest; actions are pinned by commit SHA. `.semgrepignore` exists only to
  replace Semgrep's default ignore list, which would skip `tests/`.
- Reason: broader coverage of the code, dependencies and infrastructure, visible in one place.
- Driver: user instruction during the session.
