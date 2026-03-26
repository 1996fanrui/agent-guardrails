# pre-commit Hook Creation And Migration Rules

## Core Principles

The standard pre-commit interaction model:

| Config | Behavior |
|------|------|
| `pass_filenames: true` (default) | pre-commit passes filtered staged file paths to the script as `sys.argv[1:]` |
| `pass_filenames: false` | pre-commit passes no filenames and the script scans on its own; `exclude` and `types` then affect only trigger conditions, not the actual files scanned by the script |

Conclusion: always use `pass_filenames: true` (the default) and let pre-commit filter files.

There are three distinct file-selection modes:

1. `pre-commit run`
   Checks staged files only.
2. `pre-commit run --all-files`
   Checks the full set of Git tracked files only; internally this is equivalent to `git ls-files` and does not automatically include untracked files or files ignored by `.gitignore`.
3. `pre-commit run --files <paths...>`
   Checks only explicitly provided paths; even untracked or `.gitignore`-ignored files are still checked if they are passed explicitly.

Decide `language` first:

- `agent-guardrails` is a public open source hook repository and must assume consumers have no preinstalled environment beyond `pre-commit`; do not assume system `python3`, a project virtualenv, or the repository's language stack.
- For Python hooks distributed across repositories, use `language: python` by default.
- You may fall back to `language: script` only when the hook has zero third-party dependencies, the execution environment is controlled, and `python3` is guaranteed.
- A `.py` filename is not a reason to choose `language: script`; the deciding factor is environment ownership, not file extension.
- If consumers may use a non-Python repository or machines without Python preinstalled, `language: python` is mandatory.

When adding or migrating a hook, use this order of decisions:

1. Define `language`
2. Define `types`, `types_or`, and `exclude` in `.pre-commit-hooks.yaml`
3. Implement the script
4. Run positive and negative validation

Do not write a repository-scanning script first and then try to patch its scope later with `exclude`.

## Python Script Template

```python
#!/usr/bin/env python3
"""Describe what this lint checks."""

from __future__ import annotations

import sys
from pathlib import Path


def check_file(path: Path) -> list[str]:
    """Return the list of violations for a single file."""
    violations = []
    # ... implement the check logic ...
    return violations


def main() -> int:
    files = [Path(f) for f in sys.argv[1:]]
    if not files:
        return 0

    violations: list[str] = []
    for path in files:
        violations.extend(check_file(path))

    if violations:
        print("Lint failed:")
        for v in violations:
            print(f"  {v}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

## `.pre-commit-hooks.yaml` Template

```yaml
- id: my-hook
  name: Human-readable hook name
  language: python
  entry: path/to/script.py          # relative to the repository root
  types: [python]                   # use types_or for multiple file classes
  exclude: '(^|/)(tests?|\.venv|node_modules|dist|build|__pycache__)/'
  # omit pass_filenames; true is the default
```

## File Type Reference

| `types` Value | Matching Files |
|-----------|---------|
| `[python]` | `.py` |
| `[shell]` | `.sh`, `.bash` |
| `[ts]` | `.ts`, `.tsx` |
| `[javascript]` | `.js`, `.jsx` |
| `[yaml]` | `.yaml`, `.yml` |
| `[json]` | `.json` |
| `types_or: [python, shell]` | `.py` or `.sh` |

## Scope Design Checklist

Before adding or migrating a hook, answer these questions:

1. Is the hook scoped by one language or a multi-language combination?
2. Which directories would be scanned by mistake without extra filtering?
3. Must test directories, generated directories, or cache directories be excluded?
4. Can the rule boundary be expressed entirely through `types`, `types_or`, and `exclude`?

Common `exclude` fragments:

- Python runtime excluding tests and caches:
  `(^|/)(tests?|\.venv|__pycache__|dist|build)/`
- General source trees excluding dependency and build outputs:
  `(^|/)(\.venv|node_modules|dist|build|__pycache__)/`
- Shell scripts excluding platform build-output directories:
  `(^|/)(\.venv|node_modules|dist|build|mobile/android|frontend/dist)/`

If a rule applies to almost all text files, such as comments, docs, and config files:

- You may omit `types` and `types_or` and rely only on `exclude` to narrow scope.
- The script must safely skip binary or undecodable files and must not crash merely because type filters were omitted.
- In an open source repository that forbids Chinese text, do not hide Chinese violations by excluding repository documents. Translate the repository documents instead and keep the hook active.
- `AGENTS.md` and `CLAUDE.md` are an explicit repository-level exception in `agent-guardrails`: they are local control documents, must stay ignored by Git, and should be excluded by default.

If a hook needs project-level semantics, such as "check backend runtime only, not tests," express that boundary in `exclude` instead of building a second discovery model in the script.

## Full Procedure For Adding Or Migrating A Hook

1. Create the script in the correct directory: `general/`, `python/`, or `shell/`, with the shebang `#!/usr/bin/env python3`
2. Decide `language` first: shared Python hooks default to `python`, and `script` is allowed only for explicit exceptions
3. Implement the script as a file-list consumer that reads only `sys.argv[1:]`
4. If `language: script` is chosen, set the executable bit with `chmod +x <script>` and `git update-index --chmod=+x <script>`
5. Add or update the hook definition in `.pre-commit-hooks.yaml`, including `language`, `types`, `types_or`, and `exclude`
6. If the script needs same-directory imports, use `sys.path.insert(0, str(Path(__file__).parent))`
7. Run positive validation: an in-scope violation must fail
8. Run negative validation: excluded paths, test directories, or non-target file types must not be reported
9. If `language: python` is used, validate that pre-commit can create the runtime environment successfully
10. Prefer `pre-commit try-repo /home/fanrui/code/agent-guardrails <hook-id> --all-files` for realistic hook validation
11. Only commit, push, or update the consumer repository `rev` when the user explicitly asks

## Extra Requirements For Migrating Legacy Hooks

If the legacy hook still uses any of these patterns:

- `pass_filenames: false`
- `Path.cwd()` / `DEV_LINT_PROJECT_ROOT` / hand-written project-root discovery
- `rglob("*")` or any other repository-wide scan
- hard-coded ignore directories inside the script

When migrating, complete all four actions together:

1. Remove repository scanning and consume `sys.argv[1:]` instead
2. Move scope control into `.pre-commit-hooks.yaml` via `types`, `types_or`, and `exclude`
3. Remove helpers or environment variables that exist only for the old scan model
4. Validate with both positive and negative examples to ensure there is no over-scan or under-scan

## Forbidden Practices

- Do not treat a `.py` file extension as a reason to choose `language: script`
- Do not default shared, cross-project Python hooks to `language: script`
- Do not set `pass_filenames: false` unless the hook is inherently global and the user has explicitly accepted that exception
- Do not `rglob` the repository from the script; let pre-commit discover files
- Do not reimplement exclude logic inside the script; use `.pre-commit-hooks.yaml`
- Do not maintain one ignore list in `.pre-commit-hooks.yaml` and another inside the script
- Do not validate only positive cases; negative validation is required too
- Do not forget `git update-index --chmod=+x` when a `language: script` entrypoint must be executable
