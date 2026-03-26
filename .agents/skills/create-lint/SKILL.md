---
description: "Create or migrate a pre-commit lint hook in agent-guardrails; use when adding a hook, migrating an old hook to the exclude-driven model, or reviewing hook scope."
---

You are the lint hook creation specialist for `agent-guardrails`.

This skill has no external environment dependencies.

Before executing, you must read `references/pre_commit_conventions.md`.

## Step 1: Understand The Request And Boundaries

Extract the following from `$ARGUMENTS`:

- what the rule checks
- target file types
- target directory: `general/`, `python/`, or `shell/`
- whether this is a new hook or a migration of an existing hook

If the requested scope is unclear, define the scope first and only then implement the hook. Do not write the script first and backfill `exclude` later.

## Step 2: Design Hook Scope First

Using `references/pre_commit_conventions.md`, define these items first:

- hook id / name
- `language` choice and the reason
- `types` or `types_or`
- `exclude` regex
- any unavoidable exception boundary

Default requirements:

- `agent-guardrails` is a public hook repository, so design under the assumption that consumers have no preinstalled environment beyond `pre-commit`
- shared Python hooks default to `language: python`
- let pre-commit own file discovery
- scripts consume only `sys.argv[1:]`
- do not set `pass_filenames: false`

If you believe the rule cannot operate at file granularity, stop and explain why. Wait for user confirmation before keeping any exception.

## Step 3: Implement Or Migrate The Script

- Follow the Python template from the reference
- Converge logic into a file-oriented function such as `check_file(path)`
- Do not `rglob` the repository or rely on project-root discovery such as `DEV_LINT_PROJECT_ROOT`
- Add same-directory helpers only when necessary; do not abstract prematurely
- Set executable permissions with `chmod +x <script>` and `git update-index --chmod=+x <script>` when required

## Step 4: Update `.pre-commit-hooks.yaml`

- Add or update the hook definition according to the reference template
- Define `types`, `types_or`, and `exclude` explicitly
- Keep `.pre-commit-hooks.yaml` as the single source of truth for hook scope

## Step 5: Run Positive And Negative Validation

```bash
cd <target-project>
pre-commit try-repo /home/fanrui/code/agent-guardrails <hook-id> --all-files
```

Validate at least these two cases:

- positive case: an in-scope violating file fails
- negative case: excluded paths, test directories, or non-target file types are not reported

If invalid input still "passes" or excluded paths are still scanned, the scope design is invalid and you must return to Step 2.

## Step 6: Wrap Up

- Report only the necessary result: what changed, how it was validated, and whether any exception remains
- If this work reveals a reusable pitfall, update `AGENTS.md` or `references/pre_commit_conventions.md`
- Only commit, push, or update a consumer repository's `rev` when the user explicitly asks
