---
description: "Onboard a consumer project to use agent-guardrails and pre-commit-hooks; generates .pre-commit-config.yaml, integrates into CI, and updates .githooks if present."
---

You are the project onboarding specialist for `agent-guardrails`.

This skill takes a target project path and configures it to consume shared hooks from both `pre-commit/pre-commit-hooks` (community) and `agent-guardrails` (custom).

Before executing, read these files for context:
- `/home/fanrui/code/agent-guardrails/.pre-commit-hooks.yaml` — custom hooks and their default scope
- The target project's `CLAUDE.md` — project rules and conventions

## Input

Extract from `$ARGUMENTS`:
- **project path**: absolute path to the target project

## Step 1: Analyze The Target Project

Gather the following about the target project:

1. **Languages used**: check for Python (`.py`), Shell (`.sh`), TypeScript, JavaScript, YAML, JSON, TOML, XML, etc.
2. **Existing `.pre-commit-config.yaml`**: if present, update rather than overwrite
3. **Existing `.githooks/pre-commit`**: if present, integrate pre-commit into it
4. **CI setup**: find `.github/workflows/ci.yml` and `scripts/run_test.sh`
5. **Content language policy**: check `CLAUDE.md` for rules about Chinese content — determine which paths allow Chinese (e.g. `docs/`, `README.md`, `requirements/`)

## Step 2: Select Community Hooks (`pre-commit/pre-commit-hooks`)

Use `rev: v6.0.0` for `https://github.com/pre-commit/pre-commit-hooks`.

### Always include (universal)

| Hook | Purpose |
|------|---------|
| `trailing-whitespace` | Trim trailing whitespace |
| `end-of-file-fixer` | Ensure files end with exactly one newline |
| `check-merge-conflict` | Detect merge conflict markers |
| `check-added-large-files` | Prevent giant files from being committed |
| `check-executables-have-shebangs` | Ensure executables have a shebang |
| `check-shebang-scripts-are-executable` | Ensure shebang scripts are executable |
| `check-case-conflict` | Detect filename case conflicts across OS |
| `detect-private-key` | Prevent private keys from being committed |
| `destroyed-symlinks` | Detect symlinks converted to regular files |
| `fix-byte-order-marker` | Remove UTF-8 BOM |

### Include when project has the format

| Hook | Include When |
|------|-------------|
| `check-yaml` | Project has `.yaml`/`.yml` files (almost always) |
| `check-json` | Project has `.json` files |
| `check-toml` | Project has `.toml` files |
| `check-xml` | Project has `.xml` files |
| `check-symlinks` | Project has symlinks |

### Include for Python projects

| Hook | Purpose |
|------|---------|
| `check-ast` | Validate Python files parse correctly |
| `debug-statements` | Catch debugger imports and `breakpoint()` calls |

### Do NOT include by default

| Hook | Reason |
|------|--------|
| `no-commit-to-branch` | May conflict with CI workflows that push to main |
| `check-builtin-literals` | Opinionated style choice |
| `double-quote-string-fixer` | Opinionated style choice |
| `name-tests-test` | Opinionated test naming convention |
| `detect-aws-credentials` | Only relevant for AWS-heavy projects |
| `mixed-line-ending` | `end-of-file-fixer` + `trailing-whitespace` cover most cases |
| `check-docstring-first` | Deprecated |
| `check-byte-order-marker` | Removed, use `fix-byte-order-marker` instead |
| `fix-encoding-pragma` | Removed, use `pyupgrade` instead |

## Step 3: Select Custom Hooks (`agent-guardrails`)

Read `.pre-commit-hooks.yaml` from agent-guardrails and select hooks based on project analysis:

| Hook | Include When |
|------|-------------|
| `lint-file-line-count` | Always (universal) |
| `lint-no-chinese` | Project prohibits Chinese in source code |
| `lint-shell-portability` | Project has `.sh` files |
| `lint-enum-redundant-string` | Project has Python code |
| `lint-pre-commit-hook-languages` | **Never** for consumer projects — this is for hook repos only |

## Step 4: Determine Excludes For `lint-no-chinese`

The hook's built-in excludes cover `requirements/` and `AGENTS.md`/`CLAUDE.md`. Consumer projects often need additional excludes for paths that intentionally contain Chinese. Common additions:

- `docs/` — if design docs use Chinese
- `README.md` — if the README is in Chinese

Consumer-level `exclude` in `.pre-commit-config.yaml` **overrides** the hook-level default, so the consumer config must include all needed patterns (both the originals and additions).

## Step 5: Generate `.pre-commit-config.yaml`

Determine the latest commit hash on `agent-guardrails` main branch:

```bash
git -C /home/fanrui/code/agent-guardrails rev-parse main
```

Generate the config. Community hooks come first, then custom hooks. Example:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      # -- universal --
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-merge-conflict
      - id: check-added-large-files
      - id: check-executables-have-shebangs
      - id: check-shebang-scripts-are-executable
      - id: check-case-conflict
      - id: detect-private-key
      - id: destroyed-symlinks
      - id: fix-byte-order-marker
      # -- format-specific --
      - id: check-yaml
      - id: check-json
      - id: check-toml
      # -- python --
      - id: check-ast
      - id: debug-statements

  - repo: https://github.com/1996fanrui/agent-guardrails
    rev: <full-commit-hash>
    hooks:
      - id: lint-file-line-count
      - id: lint-no-chinese
        exclude: '<merged-exclude-pattern>'
      - id: lint-shell-portability
      - id: lint-enum-redundant-string
```

Write this file to `<project>/.pre-commit-config.yaml`.

## Step 6: Integrate Into CI

### 6a: Update `scripts/run_test.sh`

Add `pre-commit run --all-files` into the lint section of `run_test.sh`. Insert it alongside existing lint commands, not replacing them. Example integration pattern:

```bash
# In the lint function, add:
if command -v pre-commit >/dev/null 2>&1; then
    pre-commit run --all-files
else
    pip install pre-commit && pre-commit run --all-files
fi
```

### 6b: Update CI workflow

If the CI workflow directly runs `./scripts/run_test.sh lint`, adding to run_test.sh is sufficient. Otherwise, ensure `pre-commit` is installed and `pre-commit run --all-files` is called in the lint job.

## Step 7: Update `.githooks/pre-commit`

If `.githooks/pre-commit` exists, add `pre-commit run` (without `--all-files` — only staged files for local commits) before or after the existing commands.

Pattern:
```bash
# Run shared pre-commit hooks on staged files
if command -v pre-commit >/dev/null 2>&1; then
    pre-commit run
fi
```

If `.githooks/pre-commit` does not exist, do NOT create it — local hook setup is optional for consumers.

## Step 8: Validate

Run a quick smoke test to verify the config is syntactically valid:

```bash
cd <project>
pre-commit run --all-files 2>&1 | head -50
```

Report which hooks passed/failed. Failures due to actual lint violations are expected and acceptable — the goal is to verify the hook infrastructure works, not to fix all violations.

## Step 9: Fix All Lint Violations

Run `pre-commit run --all-files` and fix every violation. Repeat until all hooks pass.

**Critical rules:**
- Fixes must be pure refactoring only — never change code semantics, business logic, or observable behavior
- Never modify `.pre-commit-config.yaml` or hook configuration to suppress failures — only fix the source code/files
- `trailing-whitespace`, `end-of-file-fixer`, `fix-byte-order-marker` are auto-fixers — just re-stage the auto-fixed files
- For `lint-no-chinese`: replace Chinese characters with English or Unicode escapes (depending on project policy)
- For `lint-file-line-count`: split large files into smaller modules
- For `lint-shell-portability`: replace GNU-only syntax with POSIX-compatible alternatives
- For `lint-enum-redundant-string`: remove redundant string literals from enum definitions
- For `debug-statements`: remove `breakpoint()`, `import pdb`, `import ipdb`, etc.
- For `detect-private-key`: remove or `.gitignore` private key files
- For `check-ast`: fix Python syntax errors

After all hooks pass, commit the fixes separately from the infrastructure changes.

## Step 10: Commit and PR

- Create a branch named `integrate-agent-guardrails-hooks`
- Commit infrastructure changes (`.pre-commit-config.yaml`, `scripts/run_test.sh`, `.githooks/pre-commit`) first
- Commit lint fixes in a separate commit
- Create a PR with a clear description of what was added
