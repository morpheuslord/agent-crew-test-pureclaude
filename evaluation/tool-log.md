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

