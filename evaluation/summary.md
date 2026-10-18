# Evaluation summary (arm B, no MCP)

Written last, after every other evaluation file.

## Totals

### Log entries by source (`tool-log.md`)

| Source | Entries | IDs |
| --- | --- | --- |
| MCP | 0 | none |
| CLI | 3 | T-001 `npm audit`, T-002 `uvx pip-audit`, T-011 `git grep` (suppressions and secrets) |
| Self (own review / configuration work) | 8 | T-003 design threat review, T-004 Semgrep/Trivy workflows (user request), T-005 Codacy/Trivy CI fixes (user request), T-006 API review, T-007 cache review, T-008 UI review, T-009 infrastructure review, T-010 containers/CI review |
| Total | 11 | |

### Findings by source and disposition (`findings.md`)

| Raised by | fixed | mitigated | accepted risk | false positive | out of scope | open | Total |
| --- | --- | --- | --- | --- | --- | --- | --- |
| self | 20 | 3 | 11 | 0 | 0 | 0 | 34 |
| test | 1 | 0 | 0 | 0 | 0 | 0 | 1 |
| CLI | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Total | 21 | 3 | 11 | 0 | 0 | 0 | 35 |

F-001 to F-021 are design-time security requirements from the threat review (T-003), later marked
fixed or mitigated as the code landed. F-022 to F-035 are issues or residual risks found during
implementation reviews and tests. The two CLI dependency audits (T-001, T-002) reported no known
vulnerabilities, so they produced no findings.

### MCP calls by tool

None. No MCP tool of any server was called (0 calls, 0 errors). No PROTOCOL VIOLATION entries.

## Commits driven by each source

| Source | Commits | Findings |
| --- | --- | --- |
| self | `19b35fd` (F-007, F-018), `0fccc2a` (F-001, F-008, F-010), `5dc26ad` (F-002, F-004, F-005, F-006, F-007, F-012, F-019, F-020), `24bd135` (F-011, F-013, F-016, F-018, F-022), `68b6877` (F-024), `2a5585e` (F-002, F-003, F-011, F-014, F-018), `d43ecc2` (F-009), `5a8aaaf` (F-013, F-015, F-017, F-027 to F-033), `a2ade1a` (F-021), `5c8ed75` (F-015, F-021, F-035) | 34 |
| test | `d43ecc2` (F-025: link `rel` attribute stripped by the sanitiser, caught by a unit test) | 1 |
| CLI | none (audits clean) | 0 |
| User instruction (not findings) | `996d364` Semgrep and Trivy workflows; `b559d56` Codacy SARIF split and Trivy Terraform skip | n/a |

No commit subject carries a finding id. Every security fix was made before the first commit of the
file it touched, so no commit was driven by a finding alone. The ids are recorded in the Commit
column of `findings.md` instead.

## Findings rejected as false positives

None.

## Time

| | UTC |
| --- | --- |
| Start | 2026-10-18T06:13:25Z |
| End | 2026-10-18T07:55Z (approximate; last `date -u` reading 07:53:03Z, before this file) |
| Elapsed | about 1 h 42 min |

## What helped, what got in the way, what was unexpected

- The Docker daemon was not reachable (`permission denied` on the socket, also outside the tool
  sandbox). `docker compose up --build` and the Compose form of `make smoke` were not run, and the
  images were not built locally. Instead, PostgreSQL 16, Redis 7 and Node 24 were installed from
  conda-forge into a toolchain directory outside the repository. The integration tests and two full
  `scripts/smoke.sh` runs used real API and UI processes. `docker compose config` works without a
  daemon and was used to validate both Compose files. The CI `images` job builds the Dockerfiles.
- The system Node.js was v18, so Node 24 had to be installed as a toolchain.
- The shell environment already exported `API_TIMEOUT_MS` with a value above the UI's limit. The
  UI's startup validation refused to start, which led to renaming the variable (D-028).
- `pkill -f "taskboard-api serve"` matched the shell running it and killed that command before it
  did anything. Nothing was written. The command was rerun and the servers were stopped by PID.
- A SessionStart hook injected instructions to invoke skills before any action, and the harness
  supplied a commit-trailer reminder. Both conflicted with sections 0 and 11 and were not followed.
- The `sec-review` MCP server connected after the session started and pushed workflow instructions
  (recorded verbatim, as delivered, in `session-meta.md`). It was not used.
- Mid-session the user asked for Semgrep and Trivy workflows, then authorised a change to the frozen
  `codacy.yml` after relaying a CI log (`31 > 20` SARIF runs). This arm's `codacy.yml` therefore
  differs from the brief's text. The other two section 10 files are unchanged. Scanner results were
  never fetched or read. The CodeQL "no Python source" and Codacy upload errors were seen only
  because the user pasted the logs.
- While writing code I typed inline suppressions three times (`# noqa` twice, one `# type: ignore`)
  and one `eslint-disable` comment. All were replaced with real fixes before any commit, so
  `suppressions.md` is "none".
- `terraform validate` passed on its first run against hashicorp/aws 6.69.1, including the
  ephemeral `random_password` and write-only `value_wo` arguments.
- Writing the Terraform modules surfaced a module dependency cycle (database, API security group,
  IAM, database secret). It was resolved by moving the cross-module security-group rules into the
  environment (D-020).
