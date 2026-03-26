# agent-guardrails

AI coding agents write fast but ignore conventions. `agent-guardrails` enforces the rules they skip.

A [pre-commit](https://pre-commit.com/) hook repository providing custom lints that no single-language tool covers — designed to work uniformly across multi-language, multi-repo setups.

## Usage

### As pre-commit hooks

Add to your project's `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/1996fanrui/agent-guardrails
    rev: v1.0.0
    hooks:
      - id: lint-no-chinese
      - id: lint-shell-portability
      - id: lint-backend-bare-dict
```

Install pre-commit (recommended via `uv tool`):

```bash
uv tool install pre-commit
pre-commit install
```

Run all hooks manually:

```bash
pre-commit run --all-files
```

## Maintainer Workflow

When adding or migrating a hook in this repository, treat `.pre-commit-hooks.yaml` as the source of truth for scope selection:

- define `types` or `types_or` first
- narrow the runtime surface with `exclude`
- keep `pass_filenames` at its default behavior
- make the script consume only `sys.argv[1:]`

Do not write hooks that rediscover project roots, walk the repository with `rglob`, or duplicate ignore rules inside Python. If a rule cannot run on a file list and truly needs global context, document the exception explicitly before implementing it.

Repository-local skill:

- use `.agents/skills/create-lint/` to create or migrate hooks in this repo
- `.claude` is a symlink to `.agents`, so maintain the skill in `.agents` only
