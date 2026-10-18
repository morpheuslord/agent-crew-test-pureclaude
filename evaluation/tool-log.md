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
- Changes: docs/ARCHITECTURE.md, docs/DECISIONS.md (commit filled in below)
- Notes: none

### T-004 | 2026-10-18T06:28:39Z | phase 3
- Source: Self
- Why: user instruction mid-session: add Semgrep and Trivy workflows that scan all code, with a dedicated Terraform scan, and record everything in GitHub code scanning
- Input: user message; pins looked up with `git ls-remote` (actions/checkout v6.1.0 = d23441a48e516b6c34aea4fa41551a30e30af803, github/codeql-action v4.39.0 = 6f2ac81f5cd81fe351a197ba0b00d91d03cd2aee) and the Docker Hub tags API (semgrep/semgrep 1.181.0, aquasec/trivy 0.76.0 digests); Semgrep registry packs checked with `curl https://semgrep.dev/c/p/<pack>` (all 200 except `p/bash`, 404, not used); Semgrep docs checked for the default ignore list (it includes `test/` and `tests/`)
- Output: `.github/workflows/semgrep.yml` (18 rule packs incl. p/terraform, SARIF category `semgrep`), `.github/workflows/trivy.yml` (filesystem scan with vuln+secret+misconfig incl. dev dependencies, category `trivy-fs`; Terraform config scan of `infra/`, category `trivy-terraform`), `.semgrepignore` (no patterns, replaces Semgrep's default ignore list so tests are scanned)
- Interpretation: own configuration work. The scanners were not run locally and their results were not read.
- Findings: none
- Action: applied. Scanner images pinned by digest and run with `docker run` instead of `aquasecurity/trivy-action`, whose tags were hijacked in a 2026 supply-chain incident (own knowledge); actions pinned by commit SHA.
- Changes: .github/workflows/semgrep.yml, .github/workflows/trivy.yml, .semgrepignore, docs/DECISIONS.md D-016 (commit filled in below)
- Notes: Trivy reports Terraform misconfigurations in both categories (the filesystem job includes misconfig); the dedicated category is what the user asked for.

