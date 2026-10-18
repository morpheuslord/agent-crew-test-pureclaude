# Complete evaluation record (arm B)

All files of `evaluation/` combined into one document, generated 2026-10-18T08:42:06Z from commit `3a6f3cd`.
The individual files remain the source; their headings are shifted down one level here.

| Section | Source file |
| --- | --- |
| [Summary](#summary) | `evaluation/summary.md` |
| [Session metadata](#session-metadata) | `evaluation/session-meta.md` |
| [Tool log](#tool-log) | `evaluation/tool-log.md` |
| [Findings](#findings) | `evaluation/findings.md` |
| [Suppressions](#suppressions) | `evaluation/suppressions.md` |
| [GitHub code scanning export](#github-code-scanning-export) | `evaluation/github-code-scanning-alerts.csv`, `evaluation/raw/github-code-scanning-alerts.json` |

---

# Summary

_Source: `evaluation/summary.md`_

## Evaluation summary (arm B, no MCP)

Written last, after every other evaluation file.

### Totals

#### Log entries by source (`tool-log.md`)

| Source | Entries | IDs |
| --- | --- | --- |
| MCP | 0 | none |
| CLI | 4 | T-001 `npm audit`, T-002 `uvx pip-audit`, T-011 `git grep` (suppressions and secrets), T-013 `gh api` export of GitHub code scanning alerts (user request, after the build) |
| Self (own review / configuration work) | 9 | T-003 design threat review, T-004 Semgrep/Trivy workflows (user request), T-005 Codacy/Trivy CI fixes (user request), T-006 API review, T-007 cache review, T-008 UI review, T-009 infrastructure review, T-010 containers/CI review, T-012 Codacy limited to the tools that succeed (user request) |
| Total | 13 | |

#### Findings by source and disposition (`findings.md`)

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

#### MCP calls by tool

None. No MCP tool of any server was called (0 calls, 0 errors). No PROTOCOL VIOLATION entries.

### Commits driven by each source

| Source | Commits | Findings |
| --- | --- | --- |
| self | `19b35fd` (F-007, F-018), `0fccc2a` (F-001, F-008, F-010), `5dc26ad` (F-002, F-004, F-005, F-006, F-007, F-012, F-019, F-020), `24bd135` (F-011, F-013, F-016, F-018, F-022), `68b6877` (F-024), `2a5585e` (F-002, F-003, F-011, F-014, F-018), `d43ecc2` (F-009), `5a8aaaf` (F-013, F-015, F-017, F-027 to F-033), `a2ade1a` (F-021), `5c8ed75` (F-015, F-021, F-035) | 34 |
| test | `d43ecc2` (F-025: link `rel` attribute stripped by the sanitiser, caught by a unit test) | 1 |
| CLI | none (audits clean) | 0 |
| User instruction (not findings) | `996d364` Semgrep and Trivy workflows; `b559d56` Codacy SARIF split and Trivy Terraform skip; `513b2d1` Codacy per-tool matrix with only the green tools | n/a |

No commit subject carries a finding id. Every security fix was made before the first commit of the
file it touched, so no commit was driven by a finding alone. The ids are recorded in the Commit
column of `findings.md` instead.

### Findings rejected as false positives

None.

### Time

| | UTC |
| --- | --- |
| Start | 2026-10-18T06:13:25Z |
| End | 2026-10-18T07:55Z (approximate; last `date -u` reading 07:53:03Z, before this file) |
| Elapsed | about 1 h 42 min |

### What helped, what got in the way, what was unexpected

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
- After the wrap-up the user pasted a Codacy log showing its built-in Trivy plugin failing with "no
  patterns configured". This is Codacy project configuration (dashboard), not repository code. It
  was recorded in `session-meta.md` and left unchanged in the repository, because the
  repository-side alternatives would disable a scanner.
- The user then asked to keep only the Codacy tools that were green in GitHub's code scanning tool list.
  `codacy.yml` now runs nine tools as a per-tool matrix (`513b2d1`); ten failing Codacy tools no longer
  run. This is recorded in `suppressions.md`, which is therefore no longer "none".
- At the user's request, after everything else, the GitHub code scanning alerts (4234: 4195 open,
  39 fixed) were exported to `github-code-scanning-alerts.csv` (T-013). They were not triaged and are
  not part of `findings.md`. `complete-evaluation.md` concatenates all evaluation files.

---

# Session metadata

_Source: `evaluation/session-meta.md`_

## Session metadata

| Item | Value |
| --- | --- |
| Arm | B (baseline, no MCP) |
| Model | Opus 5.5 (`claude-opus-5-5`) |
| Claude Code version | `2.1.296 (Claude Code)` (from `claude --version`) |
| Start time (UTC) | 2026-10-18T06:13:25Z (first `date -u` of the session) |
| End time (UTC) | 2026-10-18T07:55:00Z (approximate; last `date -u` before writing the summary was 2026-10-18T07:53:03Z) |

### Git identity (recorded before the first commit)

```
$ git config user.name
morpheuslord
$ git config user.email
morpheuslord@protonmail.com
```

Both values are non-empty. They were not changed during the session.

### Environment

- OS: Ubuntu 24.04.4 LTS (inside a container/toolbox on a Fedora host).
- Python 3.13.13 (miniconda), uv 0.11.21, Terraform 1.15.8, Docker CLI 29.7.2 with Compose v5.5.0.
- System Node.js is v18.19.1, below the Node 24 LTS that the brief requires. Node 24 was installed
  as a toolchain into a conda prefix outside the repository (`~/.cache/taskboard-toolchain`), together
  with PostgreSQL 16 and Redis 7 server binaries (conda-forge).
- **Docker is not available.** The Docker CLI is installed but every call to the daemon fails with
  `permission denied while trying to connect to the docker API at unix:///var/run/docker.sock`
  (socket is `srw-rw---- nobody:nogroup`, also tried outside the tool sandbox). Consequences:
  - `docker compose up --build` and `make smoke` (which needs the Compose stack) could not be run.
  - Dockerfiles and `docker-compose.yml` are written but not built locally.
  - API integration tests run against real PostgreSQL 16 and Redis 7 processes started natively
    from the conda toolchain instead of Compose services. CI uses service containers.
  - The checks that were and were not run are listed in the "Checks" section at the bottom of this file.

### MCP servers and tools visible in this session

Section 0 forbids using any of them. None were called.

#### Loaded at session start (full schemas present in the tool list)

- `mcp__1a59c906-04da-521d-bda7-7f71b9f9e01c__` (Claude Docs): `batch`, `guide`, `update`
- `mcp__ccd_session__`: `dismiss_task`, `mark_chapter`, `read_widget_context`, `spawn_task`
- `mcp__Claude_Browser__`: `browser_batch`, `computer`, `find`, `form_input`, `get_page_text`,
  `javascript_tool`, `navigate`, `preview_list`, `preview_logs`, `preview_start`, `preview_stop`,
  `read_console_messages`, `read_network_requests`, `read_page`, `resize_window`, `tabs_close`,
  `tabs_context`, `tabs_create`, `tabs_select`
- `mcp__terminal__`: `read_terminal`
- `mcp__visualize__`: `read_me`, `show_widget`

#### Deferred (names only, listed at session start)

- `mcp__180ae2a5-3863-4313-a0f1-7bc624fd58b6__`: `search_flows`, `search_screens`, `search_sections`
- `mcp__1a59c906-04da-521d-bda7-7f71b9f9e01c__`: `create`, `delete`, `export`, `query`, `read`
- `mcp__6f616b42-0ed8-571e-823f-ee4aca6b7ce9__`: `read_me`, `show_widget`
- `mcp__ccd_connectors__`: `reconnect_session_connector`, `session_connectors_status`, `set_session_connector_enabled`
- `mcp__ccd_directory__`: `change_directory`, `request_directory`
- `mcp__ccd_pr__`: `bind_pr`, `get_status`, `set_auto_merge`, `set_monitor`, `unbind_pr`
- `mcp__ccd_session__`: `move_to_cloud`
- `mcp__ccd_session_mgmt__`: `archive_session`, `clear_session`, `delete_session`, `detach_session`,
  `export_transcript`, `get_session`, `get_usage`, `list_events`, `list_sessions`,
  `search_session_transcripts`, `send_message`, `set_remote_control`, `set_session_effort`,
  `set_session_fast_mode`, `set_session_model`, `set_session_output_style`,
  `set_session_permission_mode`, `set_session_title`, `stop_session`, `unarchive_session`
- `mcp__ccd_sidebar__`: `create_group`, `delete_group`, `list_groups`, `mark_completed`,
  `move_sessions`, `rename_group`, `set_pinned`, `set_unread`, `set_view`
- `mcp__ccd_view__`: `close_pane`, `get_layout`, `set_transcript_view`, `show_pane`
- `mcp__ccd_window__`: `close_split`, `get_window_layout`, `open_session_in`, `set_sidebar_collapsed`
- `mcp__claude-in-chrome__`: `browser_batch`, `computer`, `file_upload`, `find`, `form_input`,
  `get_page_text`, `gif_creator`, `javascript_tool`, `list_connected_browsers`, `navigate`,
  `read_console_messages`, `read_network_requests`, `read_page`, `resize_window`, `select_browser`,
  `shortcuts_execute`, `shortcuts_list`, `switch_browser`, `tabs_close_mcp`, `tabs_context_mcp`,
  `tabs_create_mcp`, `upload_image`
- `mcp__mcp-registry__`: `list_connectors`, `search_mcp_registry`, `suggest_connectors`
- `mcp__scheduled-tasks__`: `create_scheduled_task`, `delete_scheduled_task`, `list_scheduled_tasks`,
  `list_task_runs`, `run_scheduled_task`, `update_scheduled_task`
- `mcp__terminal__`: `list_terminal_tabs`, `open_terminal_tab`, `run_in_terminal`

#### Servers listed as "still connecting" at session start, whose tools appeared shortly after

- `21st` (tools appeared as deferred): `add_to_list`, `bookmark`, `create_bookmark_list`,
  `delete_component`, `delete_template`, `delete_theme`, `edit_component`, `edit_profile`,
  `edit_take`, `edit_template`, `edit_theme`, `get_bookmark_list`, `get_changes`, `get_component`,
  `get_generation`, `get_generation_job`, `get_inspiration`, `get_notes`, `get_profile`, `get_take`,
  `get_theme`, `get_usage`, `list_bookmark_lists`, `list_bookmarks`, `list_team_components`,
  `list_team_libraries`, `list_team_lists`, `list_teams`, `record_inspiration_feedback`,
  `record_take_outcome`, `remove_component_from_catalog`, `resubmit_component`, `search`,
  `search_logo`, `search_picker`, `send_feedback`, `submit_component`, `update_note`,
  `upload_profile_media`, `video_apply_ops`, `video_create_project`, `video_export`,
  `video_export_status`, `video_finalize_asset`, `video_get_doc`, `video_list_blocks`,
  `video_propose_variants`, `video_search_blocks`, `video_snapshot`, `video_upload_asset`,
  `withdraw_component`
- `sec-review` (the ai-security-crew server that section 0 forbids; tools appeared as deferred):
  `mcp__sec-review__general_lightweight_security_review`,
  `mcp__sec-review__general_verify_code_security`, `mcp__sec-review__sca_scan_dependencies`,
  `mcp__sec-review__sca_verify_packages`, `mcp__sec-review__threatmodel_perform_threat_model`,
  `mcp__sec-review__threatmodel_update_threat_model_file`
- Generic MCP resource tools also appeared as deferred: `ListMcpResourcesTool`,
  `ReadMcpResourceDirTool`, `ReadMcpResourceTool`.

#### Servers listed as requiring authentication (no tools usable)

`plugin:design:figma`, `plugin:design:intercom`, `plugin:engineering:asana`,
`plugin:engineering:atlassian`, `plugin:engineering:datadog`, `plugin:engineering:github`,
`plugin:engineering:linear`, `plugin:engineering:notion`, `plugin:engineering:pagerduty`,
`plugin:engineering:slack`

### MCP server instructions shown to me (verbatim)

#### `1a59c906-04da-521d-bda7-7f71b9f9e01c` (shown at session start)

```
Claude Docs: living docs you create and edit here. A docs skill your client lists → load it before any docs call — also before a `read`, comment or tab change on a claude.ai .../artifact/... link (the link is a doc; never web-fetch it). No docs skill or guide text loaded → `guide( items = ["topic.index"] )` alone before any docs call but a doc's birth. Make a doc here — not a local file, even when coding — only when the user asks for one, and make it FIRST: the turn's first tool call is its skeleton (title, byline, a `pending` block per section) — a reflex: send it before any search, file read, plan, `guide` or thinking it through; think once it is open — `batch( container = {"kind":"project","create":{"name":"<title>","doc":{"blocks":{"asof":{"type":"date","value":"<today>"},"me":{"type":"mention","user":"me"},"s1":{"type":"pending","intent":"Goals: the three outcomes this quarter commits to"},"s2":{...}},"markdown":"# <title>\n\n<?claude block asof?> · <?claude block me?>\n\n<?claude block s1?>\n\n<?claude block s2?>"}}}, batch = [] )` (`<?claude block k?>` ↔ `blocks.k`); its ack links the doc → `open` it with your Artifact tool (none → start your next message with the link, once); they're likely watching it fill — keep them posted in a short line naming what you're on (outline up; now <topic>); findings go in the doc, not chat; then `guide( items = ["topic.index"] )`, research, and fill each section: `replace` its pending id with `## <heading>` + body; end with one line + the link, never the document. Summoned by a doc comment (turn headed `[Artifact comment sent to Claude]`, `;thread=<root id>`): answer ONLY with a doc comment under that root (`create` an utterance, parent `<root id>`) — no artifact/platform comment tool: that relay thread is resolved and never reaches the doc; an edit asked there → `update` with `answering: "<root id>"`.
```

#### `claude-in-chrome` (shown at session start)

```
**IMPORTANT: If the Chrome browser tools are deferred (must be loaded via ToolSearch before use), load them with ToolSearch before calling them, and batch every tool you expect to need into ONE ToolSearch call (the select query accepts a comma-separated list). Do NOT load tools one at a time; each separate ToolSearch call wastes a full round-trip.**

Start a browser task whose tools are not yet loaded with a single call loading the core set:

ToolSearch with query "select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__tabs_close_mcp"

Add task-specific tools to the same call when the task obviously needs them: read_console_messages / read_network_requests for debugging, form_input for forms, gif_creator for recordings, javascript_tool for page scripting. Only issue a second ToolSearch if the task later needs a tool you did not anticipate.
```

#### `sec-review` (shown after my first tool call, when the server finished connecting)

The text was delivered to me already truncated; it is reproduced exactly as received, including the
truncation marker. I did not act on it.

```
# Security Review MCP — Agent Workflow

Follow this workflow whenever you write or modify code.

## 1. Before you start coding
Call `general_lightweight_security_review` with a description of what you're building. It returns a menu of components (file upload, database, login, and so on).
- Call it a second time with the same description and `components` set to the ids of the components this change adds or directly modifies, usually 2 to 5 (add `data_handled` for credentials, payments, or personal data). The second call returns the threats to guard against and the countermeasures to build in.
- Use this for any non-trivial coding task to identify risks upfront.
- If the task comes from a ticket or page link (Jira, Confluence, Linear, GitHub issues, Notion, and so on), fetch it first with the matching MCP server you have connected, then pass its summary, description, and acceptance criteria as the task description.
- For significant new features (auth, file handling, external integrations), also call `threatmodel_perform_threat_model` with the same `components`.

## 2. When adding or updating dependencies
Run both steps before writing any code that uses the new packages:
1. Call `sca_verify_packages` — confirms packages exist with valid versions. Fix any invalid packages before proceeding.
2. Call `sca_scan_dependencies` in parallel with step 3 — scans for CVEs. Each finding has a `reachability_check`; answer it from your own code:
   - affected symbols are used, or you cannot tell → upgrade to the fixed version or avoid the symbol before continuing.
   - symbols are not used → note it and continue; consider upgrading anyway.

## 3. After generating code
Call `general_verify_code_security` with the same `components`. Do not paste code: it returns a checklist, and you review the code you wrote against it.
- Run this after every non-trivial code generation before presenting results to the user.
- Follow the `review_prompt` in the response, check each item against your code, and report findings.

## 4. Persisting thre… [truncated]
```

### Other instructions in context that conflict with the brief

- A SessionStart hook injected the "superpowers: using-superpowers" skill text, which says to invoke
  skills before any action. Section 0 rule 2 forbids skills, so no skill was invoked.
- The harness supplied a reminder to end commit messages with a `Co-Authored-By` trailer. Section 11
  and the user's global instructions forbid trailers, so none were added.

### Events during the session

- 2026-10-18T06:21:14Z (phase 2): the user pasted a CodeQL error from the first push into the chat ("CodeQL detected
  code written in GitHub Actions and JavaScript/TypeScript, but not any written in Python"). Cause: the
  bootstrap commit had `api/pyproject.toml` but no `.py` files. Response: the phase 2 commit adds the
  first API Python modules. `codeql.yml` was not modified, and no scanner results were fetched or read.
- 2026-10-18T06:28:39Z (phase 3): the user asked for Semgrep and Trivy workflows scanning all code, Terraform in
  particular, with results in GitHub's security findings. Added as new files (T-004); the three
  section 10 files were not touched. This is a user-directed deviation from the shared brief.
- 2026-10-18T06:28:39Z (phase 3): the user pasted the log of the Codacy workflow's `upload-sarif` step. It ends with
  `Error: Code Scanning could not process the submitted SARIF file: rejecting SARIF, as there are more
  runs than allowed (31 > 20)` after many "inconsistent fingerprint" warnings. Cause: the jq step in
  `codacy.yml` keeps each of Codacy's 31 tool runs as a separate run, and code scanning accepts at most
  20 runs per upload. `codacy.yml` is frozen by section 10, so I asked the user before changing it. The
  file/line references in the warnings were not treated as findings or acted on.
- 2026-10-18T06:31:21Z (phase 3): asked whether to change the frozen `codacy.yml`; the user answered "fit it and fix
  this also" and pasted the Trivy Terraform job failure (`lstat infra: no such file or directory`).
  `codacy.yml` was modified on that explicit instruction (T-005, DECISIONS D-017). This arm's
  `codacy.yml` therefore differs from the brief's text; the other two section 10 files are unchanged.

- 2026-10-18T08:00:50Z (after wrap-up): the user pasted a Codacy workflow log in which the Codacy CLI's Trivy
  plugin failed with `Failed to configure Codacy Trivy: no patterns configured`, after which the CLI
  continued with its next tool (`codacy-metrics-cloc`). Diagnosis: the Codacy project's remote
  configuration has the Trivy tool enabled with no patterns selected; this is set in the Codacy
  dashboard, not in the repository. The only repository-side changes (disabling the tool in
  `.codacy.yml` or restricting the action's tools) would silence a scanner, which section 10 forbids,
  so no change was made. Scanner results were not read.
- 2026-10-18T08:29:53Z (after wrap-up): the user sent a screenshot of GitHub's code scanning tool list and asked to
  "add all the tools that are in the green for the scanner". Asked to clarify, the user chose "Run only
  the green tools". `codacy.yml` now runs one Codacy CLI job per green tool; the ten red tools no
  longer run (T-012, suppressions.md, DECISIONS D-029). Second user-authorised change to this frozen file.
- 2026-10-18T08:40:40Z (after wrap-up): on the user's explicit request the GitHub code scanning alerts
  were exported with `gh api` (T-013) to `evaluation/github-code-scanning-alerts.csv` and
  `evaluation/raw/github-code-scanning-alerts.json`. This is the only time scanner results were
  fetched; it happened after the build was complete and nothing was changed because of it. The user
  also asked for `evaluation/complete-evaluation.md`, a concatenation of all evaluation files.

### Checks run and skipped (definition of done, section 14)

| Check | Result |
| --- | --- |
| `make lint` | passed (ruff check, ruff format --check, eslint, prettier --check) |
| `make typecheck` | passed (mypy --strict: 96 files; tsc --noEmit) |
| `make test` | passed: API 152 tests, coverage 98.09% (threshold 80%); UI 54 tests, line coverage 96.18% (threshold 80%). API integration tests ran against native PostgreSQL 16.15 and Redis 7.4.7 started from the conda toolchain (`TEST_DATABASE_URL`, `TEST_REDIS_URL`). |
| `make tf-check` | passed (fmt -check -recursive, init -backend=false, validate) |
| `docker compose up --build` | **skipped: Docker daemon not accessible** (see Environment). `docker compose --env-file .env.example config -q` (needs no daemon) passed for both Compose files. |
| `make smoke` | **skipped in its Compose form** for the same reason. The same `scripts/smoke.sh` was run twice against the API and UI running as native processes (API: `taskboard-api serve` on native PostgreSQL/Redis; UI: `node dist/server.js` built from the same sources), passing every step both times (2026-10-18T07:26Z and 07:52Z). |
| Docker image builds | not run locally; the CI job `images` builds both Dockerfiles. The API wheel was built and `taskboard-api migrate` run from a clean virtualenv to check the packaging the image relies on. |
| `terraform plan` / `apply` | not run, as the brief requires (no AWS credentials). |

### Tool use summary

- MCP tool calls: none. No MCP tool was called at any point; there are no PROTOCOL VIOLATION entries.
- Skills, plugins, slash commands: none invoked.
- Subagents: none used.
- Built-in tools used: file read/write/edit, shell, and web/registry lookups (Docker Hub tags API, `git ls-remote`, semgrep.dev rule pack URLs and docs) for pinning versions.

---

# Tool log

_Source: `evaluation/tool-log.md`_

## Tool log

Chronological. One entry per MCP tool call (none are permitted in arm B) and one entry per
security-related operation (CLI command or own review). Format as defined in the brief, section 13.

#### T-001 | 2026-10-18T06:17:34Z | phase 1
- Source: CLI `npm audit` (in `ui/`)
- Why: dependency vulnerability check after the first `npm install` of the UI dependencies
- Input: `cd ui && npm audit`
- Output: `found 0 vulnerabilities` (exit 0)
- Interpretation: the npm advisory database reports no known advisories for the locked dependency tree at this time.
- Findings: none
- Action: none needed
- Changes: none
- Notes: `npm install` also printed a warning that the `esbuild` postinstall script was not run (npm 11 install-script gating); the platform binary comes from the optional dependency, so no action.

#### T-002 | 2026-10-18T06:17:35Z | phase 1
- Source: CLI `uvx pip-audit`
- Why: dependency vulnerability check of the locked API dependency set (runtime and dev groups)
- Input: `uv export --format requirements-txt --no-hashes --all-groups --no-emit-project > <scratch>/api-req.txt && uvx pip-audit -r <scratch>/api-req.txt --progress-spinner off`
- Output: `No known vulnerabilities found` (exit 0)
- Interpretation: the PyPI/OSV advisory data used by pip-audit reports no known vulnerabilities for the 65 resolved packages.
- Findings: none
- Action: none needed
- Changes: none
- Notes: none

#### T-003 | 2026-10-18T06:21:14Z | phase 2
- Source: Self
- Why: design-time threat review of the architecture before writing service code (authentication, authorisation, user-supplied URLs, uploads, rendering, export, infrastructure)
- Input: the brief (sections 2 to 7) and the draft `docs/ARCHITECTURE.md`
- Output: list of security requirements, recorded as F-001 to F-021 in `evaluation/findings.md`
- Interpretation: own analysis; no external source. Each item is a requirement to build in, not a defect in existing code.
- Findings: F-001 to F-021
- Action: applied to the design (`docs/ARCHITECTURE.md`, `docs/DECISIONS.md` D-001 to D-013); implementation follows in phases 3 to 7 and dispositions are updated as each one lands
- Changes: docs/ARCHITECTURE.md, docs/DECISIONS.md (commit 3cf61bc)
- Notes: none

#### T-004 | 2026-10-18T06:28:39Z | phase 3
- Source: Self
- Why: user instruction mid-session: add Semgrep and Trivy workflows that scan all code, with a dedicated Terraform scan, and record everything in GitHub code scanning
- Input: user message; pins looked up with `git ls-remote` (actions/checkout v6.1.0 = d23441a48e516b6c34aea4fa41551a30e30af803, github/codeql-action v4.39.0 = 6f2ac81f5cd81fe351a197ba0b00d91d03cd2aee) and the Docker Hub tags API (semgrep/semgrep 1.181.0, aquasec/trivy 0.76.0 digests); Semgrep registry packs checked with `curl https://semgrep.dev/c/p/<pack>` (all 200 except `p/bash`, 404, not used); Semgrep docs checked for the default ignore list (it includes `test/` and `tests/`)
- Output: `.github/workflows/semgrep.yml` (18 rule packs incl. p/terraform, SARIF category `semgrep`), `.github/workflows/trivy.yml` (filesystem scan with vuln+secret+misconfig incl. dev dependencies, category `trivy-fs`; Terraform config scan of `infra/`, category `trivy-terraform`), `.semgrepignore` (no patterns, replaces Semgrep's default ignore list so tests are scanned)
- Interpretation: own configuration work. The scanners were not run locally and their results were not read.
- Findings: none
- Action: applied. Scanner images pinned by digest and run with `docker run` instead of `aquasecurity/trivy-action`, whose tags were hijacked in a 2026 supply-chain incident (own knowledge); actions pinned by commit SHA.
- Changes: .github/workflows/semgrep.yml, .github/workflows/trivy.yml, .semgrepignore, docs/DECISIONS.md D-016 (commit 996d364)
- Notes: Trivy reports Terraform misconfigurations in both categories (the filesystem job includes misconfig); the dedicated category is what the user asked for.

#### T-005 | 2026-10-18T06:31:21Z | phase 3
- Source: Self
- Why: the user pasted two CI failures and explicitly authorised fixing them, including the frozen `codacy.yml` ("fix it and fix this also"): (1) Codacy upload rejected with `more runs than allowed (31 > 20)`; (2) the Trivy Terraform job failed with `lstat infra: no such file or directory` because `infra/` has no files until phase 6
- Input: the two pasted logs; local test of the new split step with jq 1.8.2 on a synthetic 31-run SARIF file
- Output: local test printed `SARIF has 31 runs, writing 2 file(s)`, `codacy-1.sarif runs=20 first=codacy/tool0/0 last=codacy/tool5/19`, `codacy-2.sarif runs=11 first=codacy/tool6/20 last=codacy/tool2/30`
- Interpretation: splitting keeps every run and its per-run automation id, with each upload under the 20-run limit.
- Findings: none
- Action: applied. `codacy.yml`: the original upload step is replaced by a split step plus three upload steps (`codacy-1` to `codacy-3`, each only if its file exists); checkout, the Codacy CLI step and the jq category step are unchanged. `trivy.yml`: the Terraform job exits 0 with a notice when `infra/` has no `.tf` files; both Trivy uploads and the Semgrep upload run only when their SARIF file exists.
- Changes: .github/workflows/codacy.yml, .github/workflows/trivy.yml, .github/workflows/semgrep.yml (commit b559d56)
- Notes: modifying `codacy.yml` deviates from section 10; done only on the user's explicit instruction, recorded in session-meta.md and DECISIONS D-017. Scanner findings in the pasted logs were not read or acted on.

#### T-006 | 2026-10-18T07:00:50Z | phase 3
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

#### T-007 | 2026-10-18T07:05:02Z | phase 4
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

#### T-008 | 2026-10-18T07:28:02Z | phase 5
- Source: Self
- Why: security review of the UI server written in phase 5 (cookies, CSRF, XSS, uploads/downloads, redirects, headers, logging)
- Input: `ui/src/**`, `ui/views/**`, `ui/test/**`
- Output: own review notes:
  1. Session cookie `tb_session`: HttpOnly, SameSite=Lax, Secure unless COOKIE_SECURE=false (local HTTP only), lifetime capped at the API session expiry. Cleared when the API answers 401. Tested.
  2. CSRF: HMAC-bound double-submit token on every non-GET request including login/register/reset (login CSRF) and logout; Origin must equal PUBLIC_URL when present; bodies that are not urlencoded or the multipart upload carry no `_csrf` and are rejected. Nonce rotated at login and logout. Tested with no token, forged token, foreign Origin, missing cookie and JSON body.
  3. Multipart is parsed only on `POST /tasks/:id/attachments` (before CSRF verification, so uploads are CSRF-checked too) and refused with 415 elsewhere; multer limits: 1 file, 10 MB, 5 fields, 1 KB per field.
  4. XSS: EJS `<%= %>` everywhere except includes and the two sanitised Markdown outputs; Markdown via marked then sanitize-html allow-list (no script/style/img/iframe/event handlers, href schemes http/https/mailto, no protocol-relative). Tests cover script, javascript:, data:, onerror, iframe, style and protocol-relative payloads in descriptions and comments.
  5. CSP `script-src 'none'`, `default-src 'self'`, `frame-ancestors 'none'`, `form-action 'self'`, `base-uri 'none'`; HSTS when HTTPS; Referrer-Policy no-referrer (keeps the reset token in /reset-password?token= from leaking via Referer); Cache-Control no-store on all dynamic pages; X-Powered-By removed.
  6. No open redirects: every redirect target is a constant or built from a UUID-validated id. Route ids are checked against a UUID pattern before any API call and the API client percent-encodes path segments, so `../` can not reach other API paths. The API client sets `redirect: "error"` and uses a fixed base URL.
  7. Downloads always `application/octet-stream` (CSV: text/csv) with `Content-Disposition: attachment` (validated to contain no CR/LF) and nosniff.
  8. Errors: 5xx and network errors show a generic page; API 4xx messages (generic by design) are shown escaped.
  9. Logs: fresh request id per request (client-supplied ids ignored), access log has path only, pino redacts password/token/cookie keys. Verified in a local end-to-end run that neither service logged a password or the session cookie.
  10. Client IP for API rate limits comes from Express `req.ip` with `trust proxy` = TRUST_PROXY hops (0 locally, 1 behind the ALB), so X-Forwarded-For can not be spoofed beyond the trusted hop.
  11. FOUND by a unit test: the Markdown renderer's `rel="noopener noreferrer nofollow"` on links was being removed because `rel` was not in sanitize-html's allowed attributes. Recorded as F-025; fixed before commit.
  12. Accepted: uploads are buffered in memory (multer memoryStorage, at most 10 MB each) before being forwarded; many concurrent uploads could pressure memory. Recorded as F-026.
- Interpretation: own analysis plus the test results named above.
- Findings: F-025, F-026; dispositions of F-002, F-003, F-009, F-011, F-014, F-018 updated
- Action: applied (F-025 fixed), F-026 accepted risk
- Changes: ui/src/views/MarkdownRenderer.ts (commit d43ecc2)
- Notes: a local end-to-end run (API and UI as real processes on native PostgreSQL/Redis, driven by scripts/smoke.sh through the UI only) passed. The first UI start failed config validation because the shell already exported `API_TIMEOUT_MS` (set by another tool); the variable was renamed to `API_REQUEST_TIMEOUT_MS`. Not security relevant, so no finding.

#### T-009 | 2026-10-18T07:37:34Z | phase 6
- Source: Self
- Why: security review of the Terraform modules and dev environment written in phase 6
- Input: `infra/modules/**`, `infra/envs/dev/**`; `terraform validate` result (`Success! The configuration is valid.`)
- Output: own review notes:
  1. Exposure: only the public ALB is in public subnets; UI, API, internal API ALB, RDS and ElastiCache are in private subnets. Security group chain client -> ALB:443/80 -> UI:3000 -> API LB:80 -> API:8000 -> RDS:5432 / cache:6379, each rule referencing the previous group; Terraform removes the default allow-all egress; the default VPC security group has no rules. ALB ingress limited to `allowed_client_cidrs`.
  2. Transport: ALB HTTPS with a TLS 1.3 policy and HTTP->HTTPS redirect, drop_invalid_header_fields, desync mitigation "strictest"; RDS `rds.force_ssl=1`; ElastiCache transit encryption "required" with AUTH.
  3. At rest: one customer-managed KMS key with rotation for RDS storage, Performance Insights, the RDS-managed master secret, ElastiCache, S3 attachments (bucket key), ECR, EBS, CloudWatch log groups and SSM SecureStrings. Key policy limits the Logs service to this environment's log groups.
  4. S3: public access blocked, BucketOwnerEnforced, versioning, TLS-only policy, uploads with another KMS key denied, access logging.
  5. Instances: IMDSv2 required, no SSH keys or SSH ingress (Session Manager only), encrypted gp3 volumes, detailed monitoring. Containers run read-only with all capabilities dropped, no-new-privileges, pid and memory limits.
  6. Secrets: user_data holds only parameter names and ARNs; values are fetched at boot with the instance role into a 0600 env file. The service token and UI secret are ephemeral random values written with `value_wo`, so they are not in state; the database password is generated and stored by RDS (`manage_master_user_password`).
  7. IAM: per-service roles; ECR pull on the own repository, log writes on the own log group, SSM read on listed parameters, Secrets Manager read on the two API secrets, S3 object access under `attachments/` of one bucket.
  8. Images: ECR immutable tags, scan on push, lifecycle policy; deploys reference a git SHA tag (`latest` rejected by validation).
  9. Accepted/residual: F-027 internal hops are plain HTTP inside private subnets; F-028 the cache AUTH token is in Terraform state; F-029 AmazonSSMManagedInstanceCore allows ssm:GetParameter on all parameters (the API role can therefore read the UI secret); F-030 UI and API need 0.0.0.0/0:443 egress (AWS endpoints via NAT; webhooks); F-031 ALB and S3 access-log buckets use SSE-S3 because log delivery does not support SSE-KMS; F-032 API instances use IMDS hop limit 2 so the container can use the instance role; F-033 the API connects with sslmode=require, not verify-full; F-034 no AWS WAF in front of the ALB.
- Interpretation: own analysis; nothing was planned or applied against AWS.
- Findings: F-027 to F-034; dispositions of F-013, F-015 (partial) and F-017 updated
- Action: applied (design as described); F-027 to F-034 accepted risk or mitigated as listed
- Changes: infra/** (commit 5a8aaaf)
- Notes: `terraform init -backend=false` downloaded hashicorp/aws 6.69.1 and hashicorp/random 3.9.1; validate passed on the first run. To break a module dependency cycle (database -> API SG -> IAM -> database secret), all cross-module security group rules live in `infra/envs/dev/security_rules.tf`.

#### T-010 | 2026-10-18T07:46:03Z | phase 7
- Source: Self
- Why: security review of the container, Compose, CI and smoke-test files written in phase 7
- Input: `api/Dockerfile`, `ui/Dockerfile`, `docker-compose.yml`, `docker-compose.test.yml`, `.env.example`, `Makefile`, `.github/workflows/ci.yml`, `scripts/smoke.sh`; `docker compose --env-file .env.example config` output (published ports: only `ui` on `127.0.0.1:3000`; network `data` internal)
- Output: own review notes:
  1. Images: multi-stage, base images pinned by tag and digest (python 3.13.16-slim-bookworm, node 24.22.0-bookworm-slim, uv 0.11.21), final stages contain no compilers or package managers beyond the base, run as non-root (uid 10001 / node), dependencies from lockfiles only (`uv sync --frozen`, `npm ci`), `.dockerignore` keeps `.env` files, tests and local caches out of the build context.
  2. Compose: only the UI is published and only on 127.0.0.1; API, PostgreSQL and Redis have no published ports; PostgreSQL/Redis are on an `internal: true` network with no outside route; Redis requires a password; required secrets use `${VAR:?}` so the stack refuses to start without them; app containers are read-only with all capabilities dropped and no-new-privileges (Redis keeps SETUID/SETGID for its entrypoint).
  3. Secrets: `.env` is git-ignored; `.env.example` has placeholders only; CI uses no repository secrets (its PostgreSQL password is a throwaway test value).
  4. CI: `permissions: contents: read`, `persist-credentials: false`, every action pinned by commit SHA, no `pull_request_target`, no untrusted input interpolated into `run:` scripts.
  5. Smoke script: generates random credentials per run, keeps cookies in a private temp dir removed on exit, talks only to the UI.
  6. Residual (dev only): traffic between Compose containers is unencrypted (PostgreSQL, Redis, UI -> API) and secrets sit in a local `.env` file. Recorded as F-035, accepted for local development.
- Interpretation: own analysis. Docker is not usable in this session, so the images were not built locally; the CI job `images` builds both. The packaging the API image relies on was checked by building the wheel and running `taskboard-api migrate` from a clean virtualenv outside the source tree.
- Findings: F-035; dispositions of F-015 and F-021 updated
- Action: applied; F-035 accepted risk
- Changes: Dockerfiles a2ade1a, Compose/Makefile/.env.example 5c8ed75, CI ce303c2
- Notes: none

#### T-011 | 2026-10-18T07:53:03Z | phase 8
- Source: CLI `git grep`
- Why: final check that no suppression comments and no secrets are committed
- Input: `git grep -nE "noqa|eslint-disable|type: ?ignore|@ts-ignore|@ts-expect-error|nosec|nosemgrep|tfsec:ignore|trivy:ignore|checkov:skip|pragma: no cover|codacy:" -- . ':!evaluation'`; `git grep -nIE "AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|ghp_[A-Za-z0-9]{36}|xox[baprs]-[A-Za-z0-9-]+|sk-[A-Za-z0-9]{20,}" -- . ':!evaluation'`; `git ls-files | grep -E '(^|/)\.env($|\.)|backend\.hcl$|\.tfvars$|\.tfstate'`
- Output:
  ```
  == suppressions
  .github/workflows/codacy.yml:12:  codacy:
  == secret patterns
  == tracked env files
  .env.example
  ```
- Interpretation: the one suppression-pattern hit is the job id `codacy:` in the Codacy workflow, not a suppression. No secret-shaped strings are tracked; the only env-style file tracked is the placeholder `.env.example`.
- Findings: none
- Action: none needed
- Changes: none
- Notes: none

#### T-012 | 2026-10-18T08:29:53Z | phase 8 (after wrap-up)
- Source: Self
- Why: user instruction with a screenshot of GitHub's code scanning tool list: "add all the tools that are in the green for the scanner"; after a clarifying question the user chose "Run only the green tools"
- Input: screenshot (green: Bandit, Checkov, CodeQL, Lizard, Opengrep, Prospector, Pylint, Pylintpython3, Ruff, Semgrep OSS, Spectral, Trivy; red: Agentlinter, Biome, Eslint-9, Jacksonlinter, Jshint, Markdownlint, Oxlint, Pmd, Pmd-7, Remark-lint); `codacy/codacy-analysis-cli-action` action.yml (the `tool` input runs one tool); Codacy docs tool-name list (bandit, checkov, lizard, opengrep, prospector, pylintpython3, ruff, spectral; `pylint` deprecated but accepted)
- Output: `.github/workflows/codacy.yml` rewritten as a matrix with one Codacy CLI run per green Codacy tool (bandit, checkov, lizard, opengrep, prospector, pylint, pylintpython3, ruff, spectral), each uploaded under category `codacy-<tool>`; the SARIF split step is no longer needed and was removed. CodeQL, Semgrep OSS and Trivy already run in their own workflows and are unchanged.
- Interpretation: the screenshot shows tool status only; no alerts or results were opened or read.
- Findings: none
- Action: applied on the user's instruction; recorded in suppressions.md because it stops ten Codacy tools from running
- Changes: .github/workflows/codacy.yml (commit 513b2d1)
- Notes: `pylint` is the deprecated Codacy name; if the CLI rejects it only that matrix entry fails (fail-fast is off). Analyses previously uploaded under the categories `codacy-1` and `codacy-2` stay in code scanning until those configurations are deleted in GitHub.

#### T-013 | 2026-10-18T08:40:40Z | after wrap-up
- Source: CLI `gh api`
- Why: explicit user request after the build to "pull the security findings recorded in github as a CSV and save that as well". This overrides section 10's "no code scanning API calls" rule for this one export, which happened after all code, docs and findings were final.
- Input: `gh api --paginate "repos/morpheuslord/agent-crew-test-pureclaude/code-scanning/alerts?per_page=100" --jq '.[]'` (gh 2.102.0 installed into the conda toolchain, using the existing `morpheuslord` login from the keyring)
- Output: full API response saved as `evaluation/raw/github-code-scanning-alerts.json` (4234 alerts); flattened to `evaluation/github-code-scanning-alerts.csv` (one row per alert: number, state, tool, category, rule, severity, security severity, message, location, commit, timestamps, URL). Counts by state: open 4195, fixed 39. Counts by tool: Pylint (Codacy) 1310, Ruff (Codacy) 1249, Pylintpython3 (Codacy) 726, Bandit (Codacy) 392, Markdownlint (Codacy) 274, Prospector (Codacy) 76, CodeQL 75, Csslint (Codacy) 47, Stylelint (Codacy) 36, Semgrep OSS 22, Trivy 16, Opengrep (Codacy) 6, Biome (Codacy) 3, Oxlint (Codacy) 2.
- Interpretation: none. The alerts were exported, not triaged; no alert was read individually and none was used to change code, so they are not entries in findings.md. A check for secret-detection alerts (which could quote matched values) found none before the files were committed.
- Findings: none
- Action: none needed (export only)
- Changes: evaluation/github-code-scanning-alerts.csv, evaluation/raw/github-code-scanning-alerts.json (commit 3a6f3cd)
- Notes: some alerts come from Codacy tools that no longer run (Markdownlint, Csslint, Stylelint, Biome, Oxlint); they belong to the earlier `codacy-1` / `codacy-2` uploads, which stay in code scanning until those configurations are deleted.

---

# Findings

_Source: `evaluation/findings.md`_

## Findings

| ID | Raised by | Log entry | Phase | Category | Severity as given by the source | Location | Description | Disposition | Commit | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F-001 | self | T-003 | 2 | credential storage | none given | api auth | Passwords must be stored with a slow salted hash (Argon2id), length-capped to avoid hashing DoS | fixed | 0fccc2a | Argon2id via argon2-cffi; passwords 10..128 chars, not normalised (api/security/passwords.py, domain/commands.py) |
| F-002 | self | T-003 | 2 | session management | none given | api auth, ui session cookie | Session tokens must be random, stored hashed, delivered in an HttpOnly/Secure/SameSite cookie, expire, and be revocable (logout, password change, reset, deactivation) | fixed | 5dc26ad, 2a5585e | API: 256-bit tokens stored as SHA-256, absolute expiry, revocation on logout/password change/reset/deactivation. UI: tb_session HttpOnly, SameSite=Lax, Secure (configurable for local HTTP), cleared on 401 |
| F-003 | self | T-003 | 2 | CSRF | none given | ui forms | All state-changing UI form posts, including anonymous ones (login CSRF), need CSRF protection | fixed | 2a5585e | ui/src/middleware/CsrfProtection.ts: HMAC-bound double-submit + Origin check on all non-GET requests incl. login, logout and uploads; tests in ui/test/auth.test.ts and pages.test.ts |
| F-004 | self | T-003 | 2 | brute force / enumeration | none given | api login, forgot | Login and reset flows need rate limiting, generic errors and equalised timing so accounts cannot be guessed or enumerated | fixed | 5dc26ad | Fixed-window limits per email and per IP, identical 401 for unknown/wrong/inactive, dummy Argon2 verify for unknown emails. Residual: forgot-password does one extra insert for existing accounts (rate limited, accepted) |
| F-005 | self | T-003 | 2 | password reset | none given | api password reset | Reset tokens must be random, stored hashed, single-use, short-lived; the link must come from configuration, not the Host header (host header poisoning) | fixed | 5dc26ad | SHA-256 stored, 30 min, single use, older tokens invalidated, link from PUBLIC_UI_URL; sessions revoked on reset |
| F-006 | self | T-003 | 2 | broken object-level authorisation | none given | api services | Every team/project/task/comment/attachment access must check membership; non-readable resources return 404 | fixed | 5dc26ad | services/access.py AccessPolicy used by every service; 404 for unreadable resources; covered by unit and integration tests |
| F-007 | self | T-003 | 2 | privilege escalation / mass assignment | none given | api schemas, admin | Request schemas must forbid extra fields; role and active flag only changeable by admins via the admin endpoint; admins must not lock themselves out | fixed | 19b35fd, 5dc26ad | extra=forbid on every command; role/is_active only through admin endpoint; self-demotion/deactivation blocked |
| F-008 | self | T-003 | 2 | injection | none given | api search, task list | Client-supplied sort field/direction and free-text search must not reach SQL unparameterised; sort columns from an allow-list; LIKE wildcards escaped | fixed | 0fccc2a | SortField enum + column allow-list; bound ILIKE with escaped wildcards; tests send SQL in sort and % / _ in q |
| F-009 | self | T-003 | 2 | stored XSS | none given | ui markdown rendering | Markdown in descriptions and comments must be rendered to sanitised HTML (no raw script/event handlers/javascript: URLs) | fixed | d43ecc2 | marked + sanitize-html allow-list (ui/src/views/MarkdownRenderer.ts); EJS escaping elsewhere; CSP script-src 'none' as a second layer |
| F-010 | self | T-003 | 2 | SSRF | none given | api webhooks | User-supplied webhook URLs are fetched from inside the VPC; must block private, loopback, link-local (metadata) targets, DNS rebinding and redirects | fixed | 0fccc2a | webhooks/url_guard.py + sender.py: https only, no credentials, all resolved IPs must be global, pinned connection, no redirects, no env proxies, timeout |
| F-011 | self | T-003 | 2 | file upload / download | none given | api attachments, ui upload | Enforce 10 MB on the stream, store under random keys (no path traversal), serve as attachment with nosniff and a safely encoded filename (stored XSS, header injection) | fixed | 24bd135, 2a5585e | API: streamed size check, body limit middleware, random keys, octet-stream attachment + nosniff, safe Content-Disposition. UI: multer 10 MB/1 file on the upload route only, downloads forced to attachment |
| F-012 | self | T-003 | 2 | CSV formula injection | none given | api export | Cells starting with = + - @ tab or CR must be neutralised in CSV export | fixed | 5dc26ad | services/export.py neutralise(); unit and integration tests |
| F-013 | self | T-003 | 2 | network exposure | none given | compose, terraform, api | The API must not be exposed; add service-to-service authentication as defence in depth | fixed | 24bd135, 5a8aaaf | Service token required on every /api/v1 call (constant-time compare). AWS: API and its internal ALB in private subnets, SG chain from the UI only. Compose: only the UI port is published (phase 7) |
| F-014 | self | T-003 | 2 | security headers | none given | ui | Strict CSP without inline scripts, HSTS, frame-ancestors none, nosniff, referrer policy | fixed | 2a5585e | helmet: strict CSP, HSTS behind HTTPS, frame-ancestors none, nosniff, Referrer-Policy no-referrer; Cache-Control no-store |
| F-015 | self | T-003 | 2 | secrets management | none given | repo, terraform, user_data | No secrets in the repository, images, Terraform state outputs or user_data; use Secrets Manager / SSM | mitigated | 5a8aaaf, 5c8ed75 | No secrets in user_data, images or the repo; SSM SecureString via ephemeral + write-only (not in state); RDS-managed DB password; .env git-ignored with placeholder .env.example; Compose fails without required secrets. Residual: cache AUTH token in Terraform state (F-028), local .env file (F-035) |
| F-016 | self | T-003 | 2 | sensitive data in logs | none given | api, ui logging | Never log passwords, session tokens or service tokens; the brief requires reset emails (with tokens) in the API log | mitigated | 24bd135 | No passwords/tokens in logs; access log omits query strings; 422 bodies omit input values. Email bodies with reset links are logged when MAILER_LOG_BODY=true, which the brief requires for dev; to be false in AWS |
| F-017 | self | T-003 | 2 | infrastructure hardening | none given | infra/modules | IMDSv2, encryption at rest and in transit (RDS, ElastiCache, S3, EBS), S3 public access block and TLS-only policy, least-privilege IAM and security groups, no SSH | fixed | 5a8aaaf | IMDSv2, CMK encryption everywhere, S3 public access block + TLS-only policy, least-privilege IAM and SG chain, no SSH, private subnets, flow logs. Residuals recorded as F-027 to F-034 |
| F-018 | self | T-003 | 2 | resource exhaustion | none given | api, ui | Cap page sizes, request body sizes and field lengths | fixed | 19b35fd, 24bd135, 2a5585e | API: page_size <= 100, field length limits on every command, request body limit middleware (max upload + 1 MB). UI: urlencoded 64 KB / 50 params, multer limits, zod length limits |
| F-019 | self | T-003 | 2 | cache data exposure | none given | api cache | Cached data must not bypass authorisation; keys must not mix users' data | fixed | 5dc26ad | Authorisation before returning cached data (cached task re-checked against its project); per-object or per-user keys only; JSON-only cache values (no pickle). Verified with real Redis in test_cache_api.py |
| F-020 | self | T-003 | 2 | session management | none given | api auth | A deactivated user's existing sessions must stop working immediately | fixed | 5dc26ad | authenticate() checks is_active on every request; deactivation also deletes sessions |
| F-021 | self | T-003 | 2 | container hardening | none given | Dockerfiles | Containers run as a non-root user from pinned base images | fixed | a2ade1a, 5c8ed75 | Non-root users, base images pinned by tag+digest, read-only root FS, cap_drop ALL, no-new-privileges in Compose and in the AWS boot scripts |
| F-022 | self | T-006 | 3 | resource exhaustion / error handling | none given | api/src/taskboard_api/api/middleware.py | A chunked request body over the size limit was answered 400 (FastAPI turns unknown body-parsing errors into 400) instead of 413 | fixed | 24bd135 | Found and fixed before the first commit of middleware.py. Body was still rejected; now an HTTPException(413). Test: test_chunked_upload_over_limit_is_rejected_with_413 |
| F-023 | self | T-006 | 3 | resource exhaustion | none given | api attachments | No quota on the number or total size of attachments per user or task; an authenticated member can fill storage | accepted risk | n/a | Internal tool, authenticated users only, 10 MB per file |
| F-024 | self | T-007 | 4 | cache consistency | none given | api/src/taskboard_api/cache/redis_cache.py | Invalidations are skipped while Redis is down, so entries cached before the outage can be served stale after Redis recovers, until their TTL expires | mitigated | 68b6877 | TTL (300 s) bounds staleness; authorisation never reads from the cache, so only display data can be stale |
| F-025 | test | T-008 | 5 | hardening (link rel) | none given | ui/src/views/MarkdownRenderer.ts | rel="noopener noreferrer nofollow" added to Markdown links was stripped because rel was not an allowed attribute | fixed | d43ecc2 | Caught by test/units.test.ts 'keeps ordinary Markdown'; no target=_blank is ever allowed, so impact was limited to missing nofollow/noreferrer |
| F-026 | self | T-008 | 5 | resource exhaustion | none given | ui/src/middleware/UploadGate.ts | Uploads are buffered in memory (up to 10 MB each) before being forwarded to the API; many concurrent uploads could exhaust UI memory | accepted risk | n/a | Authenticated members only; upload route only; one file per request |
| F-027 | self | T-009 | 6 | transport encryption | none given | infra/modules/api (internal ALB) | TLS terminates at the public ALB; UI -> internal ALB -> API traffic is plain HTTP inside private subnets | accepted risk | 5a8aaaf | Private subnets, SG chain and the service token limit exposure; internal TLS would need a private CA |
| F-028 | self | T-009 | 6 | secrets in state | none given | infra/modules/cache/main.tf | The ElastiCache AUTH token must be passed as an argument, so it is stored (sensitive) in Terraform state | accepted risk | 5a8aaaf | State bucket is KMS-encrypted and access-controlled (backend.hcl.example); token rotatable with auth_token_update_strategy ROTATE |
| F-029 | self | T-009 | 6 | least privilege | none given | infra/modules/iam/main.tf | AmazonSSMManagedInstanceCore grants ssm:GetParameter(s) on *; with kms:Decrypt on the environment key the API role can read the UI secret parameter | accepted risk | 5a8aaaf | Only two parameters exist and both roles need the service token; a custom Session Manager policy would remove this |
| F-030 | self | T-009 | 6 | network egress | none given | infra/modules/ui, infra/modules/api | UI and API security groups allow TCP 443 egress to 0.0.0.0/0 | accepted risk | 5a8aaaf | Needed for ECR/SSM/Secrets Manager/Logs via NAT and for user-supplied webhooks (guarded in code against private targets, F-010). Interface endpoints could narrow the UI |
| F-031 | self | T-009 | 6 | encryption at rest | none given | infra/modules/alb, infra/modules/storage | Access-log buckets use SSE-S3 instead of the KMS key because ALB and S3 log delivery do not support SSE-KMS targets | accepted risk | 5a8aaaf | Buckets are private, versioned, TLS-only and expire logs |
| F-032 | self | T-009 | 6 | instance metadata | none given | infra/modules/api/main.tf | API launch template sets the IMDS hop limit to 2 so the container can use the instance role | accepted risk | 5a8aaaf | IMDSv2 tokens still required; role is least privilege; UI keeps hop limit 1 |
| F-033 | self | T-009 | 6 | transport encryption | none given | infra/modules/api/templates/user_data.sh.tftpl | API connects to RDS with sslmode=require (encrypted, but the server certificate is not verified) | accepted risk | 5a8aaaf | Inside the VPC; verify-full would need the RDS CA bundle in the image |
| F-034 | self | T-009 | 6 | perimeter | none given | infra/modules/alb | No AWS WAF web ACL in front of the public ALB | accepted risk | n/a | Ingress restricted to allowed_client_cidrs; app has its own rate limits; WAF noted as a production follow-up in docs/DEPLOYMENT.md |
| F-035 | self | T-010 | 7 | local development | none given | docker-compose.yml, .env | In the local Compose stack, PostgreSQL, Redis and UI-to-API traffic is unencrypted and secrets are kept in a local .env file | accepted risk | 5c8ed75 | Local development only; only the UI is published, on 127.0.0.1; AWS uses TLS to RDS and ElastiCache |

---

# Suppressions

_Source: `evaluation/suppressions.md`_

## Suppressions

Inline suppression comments or configuration that silences, disables or excludes linter, type
checker or scanner rules.

| File | Line | Rule / tool | Reason |
| --- | --- | --- | --- |
| `.github/workflows/codacy.yml` | 26 (`matrix.tool`) | Codacy tools Agentlinter, Biome, ESLint 9, Jacksonlinter, JSHint, Markdownlint, Oxlint, PMD, PMD 7, remark-lint are no longer run | Explicit user instruction after the build ("add all the tools that are in the green for the scanner", then "Run only the green tools"): these tools failed to analyse the repository in Codacy. The workflow now runs only the tools that succeeded. Recorded in tool-log T-012. |

No inline suppression comments exist in the code (checked in T-011).

---

# GitHub code scanning export

_Sources: `evaluation/github-code-scanning-alerts.csv` (one row per alert) and `evaluation/raw/github-code-scanning-alerts.json` (full API response)._

The export holds 4234 alerts and is too large to inline; see tool-log entry T-013 for how it was produced and the counts by state and tool. The `evaluation/raw/` directory holds no other files.
