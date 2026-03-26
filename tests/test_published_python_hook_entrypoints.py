from __future__ import annotations

from pathlib import Path
import tomllib

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_hook_manifest() -> list[dict[str, object]]:
    with (REPO_ROOT / ".pre-commit-hooks.yaml").open(encoding="utf-8") as file_obj:
        manifest = yaml.safe_load(file_obj)
    assert isinstance(manifest, list)
    return manifest


def _load_project_scripts() -> dict[str, str]:
    with (REPO_ROOT / "pyproject.toml").open("rb") as file_obj:
        pyproject = tomllib.load(file_obj)
    return pyproject["project"]["scripts"]


def test_published_python_hooks_use_project_scripts_entrypoints() -> None:
    manifest = _load_hook_manifest()
    project_scripts = _load_project_scripts()

    python_hooks = [hook for hook in manifest if hook["language"] == "python"]
    assert python_hooks, "Expected at least one published Python hook."

    for hook in python_hooks:
        hook_id = hook["id"]
        entry = hook["entry"]
        assert isinstance(entry, str), f"Hook '{hook_id}' has a non-string entry."
        assert entry in project_scripts, (
            f"Hook '{hook_id}' must use a command declared in [project.scripts]. "
            f"Found entry '{entry}'."
        )
        assert "python -m" not in entry, (
            f"Hook '{hook_id}' must not use a python -m entry. "
            f"Found entry '{entry}'."
        )
        assert "/" not in entry, (
            f"Hook '{hook_id}' must not use a repo-relative path entry. "
            f"Found entry '{entry}'."
        )
        assert "\\" not in entry, (
            f"Hook '{hook_id}' must not use a path entry. Found entry '{entry}'."
        )
        assert " " not in entry, (
            f"Hook '{hook_id}' must use a console_scripts command name, not a shell command. "
            f"Found entry '{entry}'."
        )
