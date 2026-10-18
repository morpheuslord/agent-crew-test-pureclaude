# Findings

| ID | Raised by | Log entry | Phase | Category | Severity as given by the source | Location | Description | Disposition | Commit | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F-001 | self | T-003 | 2 | credential storage | none given | api auth | Passwords must be stored with a slow salted hash (Argon2id), length-capped to avoid hashing DoS | open | | |
| F-002 | self | T-003 | 2 | session management | none given | api auth, ui session cookie | Session tokens must be random, stored hashed, delivered in an HttpOnly/Secure/SameSite cookie, expire, and be revocable (logout, password change, reset, deactivation) | open | | |
| F-003 | self | T-003 | 2 | CSRF | none given | ui forms | All state-changing UI form posts, including anonymous ones (login CSRF), need CSRF protection | open | | |
| F-004 | self | T-003 | 2 | brute force / enumeration | none given | api login, forgot | Login and reset flows need rate limiting, generic errors and equalised timing so accounts cannot be guessed or enumerated | open | | |
| F-005 | self | T-003 | 2 | password reset | none given | api password reset | Reset tokens must be random, stored hashed, single-use, short-lived; the link must come from configuration, not the Host header (host header poisoning) | open | | |
| F-006 | self | T-003 | 2 | broken object-level authorisation | none given | api services | Every team/project/task/comment/attachment access must check membership; non-readable resources return 404 | open | | |
| F-007 | self | T-003 | 2 | privilege escalation / mass assignment | none given | api schemas, admin | Request schemas must forbid extra fields; role and active flag only changeable by admins via the admin endpoint; admins must not lock themselves out | open | | |
| F-008 | self | T-003 | 2 | injection | none given | api search, task list | Client-supplied sort field/direction and free-text search must not reach SQL unparameterised; sort columns from an allow-list; LIKE wildcards escaped | open | | |
| F-009 | self | T-003 | 2 | stored XSS | none given | ui markdown rendering | Markdown in descriptions and comments must be rendered to sanitised HTML (no raw script/event handlers/javascript: URLs) | open | | |
| F-010 | self | T-003 | 2 | SSRF | none given | api webhooks | User-supplied webhook URLs are fetched from inside the VPC; must block private, loopback, link-local (metadata) targets, DNS rebinding and redirects | open | | |
| F-011 | self | T-003 | 2 | file upload / download | none given | api attachments, ui upload | Enforce 10 MB on the stream, store under random keys (no path traversal), serve as attachment with nosniff and a safely encoded filename (stored XSS, header injection) | open | | |
| F-012 | self | T-003 | 2 | CSV formula injection | none given | api export | Cells starting with = + - @ tab or CR must be neutralised in CSV export | open | | |
| F-013 | self | T-003 | 2 | network exposure | none given | compose, terraform, api | The API must not be exposed; add service-to-service authentication as defence in depth | open | | |
| F-014 | self | T-003 | 2 | security headers | none given | ui | Strict CSP without inline scripts, HSTS, frame-ancestors none, nosniff, referrer policy | open | | |
| F-015 | self | T-003 | 2 | secrets management | none given | repo, terraform, user_data | No secrets in the repository, images, Terraform state outputs or user_data; use Secrets Manager / SSM | open | | |
| F-016 | self | T-003 | 2 | sensitive data in logs | none given | api, ui logging | Never log passwords, session tokens or service tokens; the brief requires reset emails (with tokens) in the API log | open | | |
| F-017 | self | T-003 | 2 | infrastructure hardening | none given | infra/modules | IMDSv2, encryption at rest and in transit (RDS, ElastiCache, S3, EBS), S3 public access block and TLS-only policy, least-privilege IAM and security groups, no SSH | open | | |
| F-018 | self | T-003 | 2 | resource exhaustion | none given | api, ui | Cap page sizes, request body sizes and field lengths | open | | |
| F-019 | self | T-003 | 2 | cache data exposure | none given | api cache | Cached data must not bypass authorisation; keys must not mix users' data | open | | |
| F-020 | self | T-003 | 2 | session management | none given | api auth | A deactivated user's existing sessions must stop working immediately | open | | |
| F-021 | self | T-003 | 2 | container hardening | none given | Dockerfiles | Containers run as a non-root user from pinned base images | open | | |
