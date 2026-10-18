# Suppressions

Inline suppression comments or configuration that silences, disables or excludes linter, type
checker or scanner rules.

| File | Line | Rule / tool | Reason |
| --- | --- | --- | --- |
| `.github/workflows/codacy.yml` | 26 (`matrix.tool`) | Codacy tools Agentlinter, Biome, ESLint 9, Jacksonlinter, JSHint, Markdownlint, Oxlint, PMD, PMD 7, remark-lint are no longer run | Explicit user instruction after the build ("add all the tools that are in the green for the scanner", then "Run only the green tools"): these tools failed to analyse the repository in Codacy. The workflow now runs only the tools that succeeded. Recorded in tool-log T-012. |

No inline suppression comments exist in the code (checked in T-011).
