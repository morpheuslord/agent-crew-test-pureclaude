# Tool log

Chronological. One entry per MCP tool call (none are permitted in arm B) and one entry per
security-related operation (CLI command or own review). Format as defined in the brief, section 13.

### T-001 | 2026-10-18T06:17:34Z | phase 1
- Source: CLI `npm audit` (in `ui/`)
- Why: dependency vulnerability check after the first `npm install` of the UI dependencies
- Input: `cd ui && npm audit`
- Output: `found 0 vulnerabilities` (exit 0)
- Interpretation: the npm advisory database reports no known advisories for the locked dependency tree at this time.
- Findings: none
- Action: none needed
- Changes: none
- Notes: `npm install` also printed a warning that the `esbuild` postinstall script was not run (npm 11 install-script gating); the platform binary comes from the optional dependency, so no action.

### T-002 | 2026-10-18T06:17:35Z | phase 1
- Source: CLI `uvx pip-audit`
- Why: dependency vulnerability check of the locked API dependency set (runtime and dev groups)
- Input: `uv export --format requirements-txt --no-hashes --all-groups --no-emit-project > <scratch>/api-req.txt && uvx pip-audit -r <scratch>/api-req.txt --progress-spinner off`
- Output: `No known vulnerabilities found` (exit 0)
- Interpretation: the PyPI/OSV advisory data used by pip-audit reports no known vulnerabilities for the 65 resolved packages.
- Findings: none
- Action: none needed
- Changes: none
- Notes: none

### T-003 | 2026-10-18T06:21:14Z | phase 2
- Source: Self
- Why: design-time threat review of the architecture before writing service code (authentication, authorisation, user-supplied URLs, uploads, rendering, export, infrastructure)
- Input: the brief (sections 2 to 7) and the draft `docs/ARCHITECTURE.md`
- Output: list of security requirements, recorded as F-001 to F-021 in `evaluation/findings.md`
- Interpretation: own analysis; no external source. Each item is a requirement to build in, not a defect in existing code.
- Findings: F-001 to F-021
- Action: applied to the design (`docs/ARCHITECTURE.md`, `docs/DECISIONS.md` D-001 to D-013); implementation follows in phases 3 to 7 and dispositions are updated as each one lands
- Changes: docs/ARCHITECTURE.md, docs/DECISIONS.md (commit 3cf61bc)
- Notes: none

### T-004 | 2026-10-18T06:28:39Z | phase 3
- Source: Self
- Why: user instruction mid-session: add Semgrep and Trivy workflows that scan all code, with a dedicated Terraform scan, and record everything in GitHub code scanning
- Input: user message; pins looked up with `git ls-remote` (actions/checkout v6.1.0 = d23441a48e516b6c34aea4fa41551a30e30af803, github/codeql-action v4.39.0 = 6f2ac81f5cd81fe351a197ba0b00d91d03cd2aee) and the Docker Hub tags API (semgrep/semgrep 1.181.0, aquasec/trivy 0.76.0 digests); Semgrep registry packs checked with `curl https://semgrep.dev/c/p/<pack>` (all 200 except `p/bash`, 404, not used); Semgrep docs checked for the default ignore list (it includes `test/` and `tests/`)
- Output: `.github/workflows/semgrep.yml` (18 rule packs incl. p/terraform, SARIF category `semgrep`), `.github/workflows/trivy.yml` (filesystem scan with vuln+secret+misconfig incl. dev dependencies, category `trivy-fs`; Terraform config scan of `infra/`, category `trivy-terraform`), `.semgrepignore` (no patterns, replaces Semgrep's default ignore list so tests are scanned)
- Interpretation: own configuration work. The scanners were not run locally and their results were not read.
- Findings: none
- Action: applied. Scanner images pinned by digest and run with `docker run` instead of `aquasecurity/trivy-action`, whose tags were hijacked in a 2026 supply-chain incident (own knowledge); actions pinned by commit SHA.
- Changes: .github/workflows/semgrep.yml, .github/workflows/trivy.yml, .semgrepignore, docs/DECISIONS.md D-016 (commit 996d364)
- Notes: Trivy reports Terraform misconfigurations in both categories (the filesystem job includes misconfig); the dedicated category is what the user asked for.

### T-005 | 2026-10-18T06:31:21Z | phase 3
- Source: Self
- Why: the user pasted two CI failures and explicitly authorised fixing them, including the frozen `codacy.yml` ("fix it and fix this also"): (1) Codacy upload rejected with `more runs than allowed (31 > 20)`; (2) the Trivy Terraform job failed with `lstat infra: no such file or directory` because `infra/` has no files until phase 6
- Input: the two pasted logs; local test of the new split step with jq 1.8.2 on a synthetic 31-run SARIF file
- Output: local test printed `SARIF has 31 runs, writing 2 file(s)`, `codacy-1.sarif runs=20 first=codacy/tool0/0 last=codacy/tool5/19`, `codacy-2.sarif runs=11 first=codacy/tool6/20 last=codacy/tool2/30`
- Interpretation: splitting keeps every run and its per-run automation id, with each upload under the 20-run limit.
- Findings: none
- Action: applied. `codacy.yml`: the original upload step is replaced by a split step plus three upload steps (`codacy-1` to `codacy-3`, each only if its file exists); checkout, the Codacy CLI step and the jq category step are unchanged. `trivy.yml`: the Terraform job exits 0 with a notice when `infra/` has no `.tf` files; both Trivy uploads and the Semgrep upload run only when their SARIF file exists.
- Changes: .github/workflows/codacy.yml, .github/workflows/trivy.yml, .github/workflows/semgrep.yml (commit b559d56)
- Notes: modifying `codacy.yml` deviates from section 10; done only on the user's explicit instruction, recorded in session-meta.md and DECISIONS D-017. Scanner findings in the pasted logs were not read or acted on.

### T-006 | 2026-10-18T07:00:50Z | phase 3
- Source: Self
- Why: security review of the API code written in phase 3 against the design requirements F-001 to F-021, before committing
- Input: `api/src/taskboard_api/**` and the unit/integration tests in `api/tests/`
- Output: own review notes:
  1. Passwords: Argon2id, length 10..128, never stripped; dummy verify for unknown emails. OK.
  2. Sessions: 256-bit tokens, SHA-256 stored, absolute expiry, deleted on logout; other sessions deleted on password change; all on reset and deactivation; lookup uncached and checks is_active. OK.
  3. Rate limits on register/login/forgot/reset/password-change; Redis keys hold a hash of the email, not the email. OK. Forgot-password still differs slightly in work done for existing vs unknown accounts (one insert); accepted, rate limited.
  4. Reset link built from PUBLIC_UI_URL; tokens hashed, single use, 30 min, older ones invalidated. OK.
  5. Object-level authorisation: every service entry point goes through AccessPolicy; cached task detail is re-authorised against its project before returning. 404 for non-readable. Tests cover cross-team access to teams, projects, tasks, comments, attachments, search.
  6. Mass assignment: all commands extra="forbid"; role/is_active only via admin endpoint; admins can not demote/deactivate themselves.
  7. Injection: sort column from an enum-keyed allow-list; search text bound and LIKE-escaped; no string-built SQL outside the test TRUNCATE.
  8. SSRF: scheme/credential/port checks at save time; at send time every resolved address must be global unicast, connection pinned to the vetted IP with SNI/Host of the original name, no redirects, trust_env=False, 5 s timeout. IP literals, IPv4-mapped IPv6, link-local metadata address covered by tests.
  9. Uploads: random 32-hex storage keys validated by regex and path containment; size counted while reading; body-size middleware; download as octet-stream attachment + nosniff; Content-Disposition reduced to safe ASCII plus RFC 5987 filename*.
  10. FOUND: a chunked request body (no Content-Length) that exceeds the limit raised a plain exception inside receive(); FastAPI's form/body parsing converts unknown exceptions into a generic 400, so the client got 400 instead of 413 (the body was still not accepted). Recorded as F-022 and fixed by making the error an HTTPException(413).
  11. CSV export prefixes = + - @ tab CR LF cells with an apostrophe.
  12. Logs: access log has path only (no query string); validation errors return messages without input values; email bodies (with reset links) are logged only when MAILER_LOG_BODY=true.
  13. Not covered by any limit: number/total size of attachments per user or task. Recorded as F-023, accepted risk for an internal tool.
- Interpretation: own analysis. Item 10 confirmed by the new integration test `test_chunked_upload_over_limit_is_rejected_with_413` (failed before the change would have returned 400; the test was written together with the fix, so the pre-fix 400 was inferred from FastAPI's routing code, not observed in a test run).
- Findings: F-022, F-023; dispositions of F-001, F-004 to F-008, F-010, F-012, F-016, F-018 to F-020 updated
- Action: applied (F-022 fixed); F-023 accepted risk
- Changes: api/src/taskboard_api/api/middleware.py, api/src/taskboard_api/api/errors.py, api/tests/integration/test_edges.py (fix in commit 24bd135; tests in the following test commit)
- Notes: while writing the code I twice typed inline `# noqa` comments (SIM115 in services/files.py, N803 in a test fake) and one `# type: ignore`; all three were removed and the code restructured instead, before any commit. `evaluation/suppressions.md` stays "none".

### T-007 | 2026-10-18T07:05:02Z | phase 4
- Source: Self
- Why: security review of the caching layer added in phase 4
- Input: `api/src/taskboard_api/cache/*.py`, `composition.py`, `tests/integration/test_cache_api.py`, `tests/unit/test_redis_cache.py`
- Output: own review notes:
  1. Serialisation is JSON validated by Pydantic TypeAdapters; nothing is unpickled, so a poisoned cache entry can at worst be discarded as undecodable (tested), not executed.
  2. Keys are per object (task), per project+filter fingerprint (same result for every member), or per user (own profile, own lists). No key mixes data visible to different users.
  3. Authorisation always uses the database: session lookup is uncached; cached task detail and task lists are only returned after the membership check.
  4. Redis URL (may contain the AUTH token) is a SecretStr; warnings log only the operation and the exception type.
  5. FOUND (limitation): while Redis is unreachable, writes cannot delete the keys they affect. When Redis comes back, entries written before the outage may be served until their TTL (300 s default) expires. Impact is stale display data only (e.g. a removed member still sees the team in their dashboard list); access checks are not affected. Recorded as F-024, mitigated by the TTL backstop.
  6. Dev Redis has no AUTH and is reachable only on the Compose network; AWS uses ElastiCache with TLS and an auth token (tracked under F-017).
- Interpretation: own analysis; item 5 is inferred from the code (invalidation goes through the same degraded-mode guard), not reproduced in a test.
- Findings: F-024
- Action: none needed beyond the TTL backstop and documentation (F-024 mitigated)
- Changes: none for the finding; feature commit 68b6877
- Notes: none

