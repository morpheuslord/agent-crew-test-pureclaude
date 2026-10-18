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

## D-017 Codacy SARIF split into uploads of at most 20 runs

- Decision: after the brief's jq step, `codacy.yml` splits `results.sarif` into files of at most 20
  runs and uploads each under its own category (`codacy-1`, `codacy-2`, `codacy-3`). The Trivy Terraform
  job skips with a notice when `infra/` has no Terraform files, and every SARIF upload runs only when
  its file exists.
- Reason: GitHub code scanning rejected the single upload (`31 > 20` runs), so no Codacy result reached
  the Security tab.
- Driver: tool output (CI logs pasted by the user) and an explicit user instruction to change the
  otherwise frozen file.

## D-018 Internal load balancer in front of the API instances in AWS

- Decision: the `api` module also creates an internal ALB in the private subnets; the UI calls it
  over HTTP on port 80 and it forwards to the API instances on 8000, health checking `/readyz`.
- Reason: the brief asks for several API instances; something must spread UI calls across them and
  stop sending to unhealthy instances. The brief's module list has no internal load balancer module,
  so it lives with the API it serves.
- Driver: brief (sections 2 and 6); own judgment.

## D-019 Configuration and secrets fetched at boot, not baked into user_data

- Decision: `user_data` contains only URLs and parameter/secret names. At boot it reads the service
  token and UI secret from SSM SecureStrings and the database credentials (RDS-managed) and cache
  token from Secrets Manager, writes a 0600 env file and starts the container with it. The service
  token and UI secret are ephemeral random values written with write-only arguments, so they are not
  in Terraform state.
- Reason: user_data is readable through the EC2 API and IMDS; images are shared across environments.
- Driver: brief (section 6 leaves this open); own judgment.

## D-020 Cross-module security group rules live in the environment

- Decision: each module creates its own security group; the rules connecting groups are in
  `infra/envs/dev/security_rules.tf`.
- Reason: passing groups between modules created a cycle (database needs the API group, the API
  needs the IAM profile, IAM needs the database secret ARN). Keeping the rules together also makes
  the whole traffic path reviewable in one file.
- Driver: own judgment (found while writing the modules).

## D-021 Request and response schemas are the domain models

- Decision: routers use the Pydantic commands in `domain/commands.py` as request bodies and the DTOs
  in `domain/dtos.py` as responses instead of duplicating them in `api/`.
- Reason: one definition of each shape and its validation, shared by services, cache serialisation
  and OpenAPI; the `api` layer still owns routing, parameters, errors and HTTP specifics.
- Driver: own judgment.

## D-022 Webhooks signed with a per-project secret

- Decision: when a webhook URL is set, the project gets a random signing secret, shown only to the
  owner and admins; deliveries carry `X-Taskboard-Signature: sha256=<HMAC of the body>`.
- Reason: lets receivers reject forged calls; per project so a leaked secret affects one project.
- Driver: own judgment.

## D-023 No client-side JavaScript in the UI

- Decision: every page is server-rendered HTML with plain forms; the CSP sets `script-src 'none'`.
- Reason: removes a whole class of XSS impact and keeps the UI small; nothing in the brief needs
  client-side behaviour.
- Driver: own judgment.

## D-024 Random UUID identifiers

- Decision: every primary key is a random UUID (v4).
- Reason: ids can not be enumerated or used to estimate counts, which complements the 404-for-
  unreadable rule (D-004).
- Driver: own judgment.

## D-025 Email bodies logged only when MAILER_LOG_BODY is true

- Decision: the outbox mailer always writes the email to the `outbox` table and logs that it did;
  the body (which may contain a reset link) is logged only when `MAILER_LOG_BODY=true`, the default
  for local development. Terraform sets it to false in AWS.
- Reason: the brief requires emails in the API log for development, but reset links in production
  logs would let anyone with log access take over accounts.
- Driver: brief (section 4.1); own judgment.

## D-026 Idempotent admin bootstrap that never resets passwords

- Decision: `taskboard-api create-admin` creates the admin from `ADMIN_EMAIL`/`ADMIN_PASSWORD`, or
  promotes and reactivates an existing account without touching its password.
- Reason: safe to re-run from automation; an attacker who can set the environment variables still
  can not silently change an existing admin's password.
- Driver: brief (section 4.1); own judgment.

## D-027 Separate Compose file for test databases

- Decision: `docker-compose.test.yml` runs throwaway PostgreSQL and Redis (tmpfs, loopback-only ports)
  for the API integration tests; the application stack in `docker-compose.yml` publishes only the UI.
- Reason: tests need direct database access; the application stack must not expose it.
- Driver: brief (section 7); own judgment.

## D-028 UI timeout variable named API_REQUEST_TIMEOUT_MS

- Decision: the UI's API timeout setting is `API_REQUEST_TIMEOUT_MS`, not `API_TIMEOUT_MS`.
- Reason: `API_TIMEOUT_MS` was already exported in the build environment by another tool with a value
  the validation rejects; a more specific name avoids such collisions.
- Driver: tool output (the UI's startup validation error during the local end-to-end run).

## D-029 Codacy runs only the tools that analyse this repository successfully

- Decision: `codacy.yml` runs the Codacy Analysis CLI once per tool in a matrix (Bandit, Checkov,
  Lizard, Opengrep, Prospector, Pylint, Pylint (Python 3), Ruff, Spectral), each uploading SARIF under
  `codacy-<tool>`. Agentlinter, Biome, ESLint 9, Jacksonlinter, JSHint, Markdownlint, Oxlint, PMD,
  PMD 7 and remark-lint are not run.
- Reason: those ten tools failed in every Codacy run; one upload per tool also isolates failures and
  stays under the 20-runs-per-upload limit without splitting. JavaScript/TypeScript coverage remains
  through CodeQL, Semgrep, ESLint (typescript-eslint, in CI) and Trivy.
- Driver: explicit user instruction (screenshot of the code scanning tool list); records the reduced
  Codacy coverage in `evaluation/suppressions.md`.
