from __future__ import annotations

import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(part for part in (result.stdout, result.stderr) if part).strip()


@pytest.fixture(scope="session")
def exported_hook_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    exported_repo = tmp_path_factory.mktemp("exported-hook-repo")
    shutil.copytree(
        REPO_ROOT,
        exported_repo,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(".git", ".tox", ".pytest_cache", "__pycache__"),
    )
    _init_git_repo(exported_repo)
    subprocess.run(["git", "add", "-A", "--", "."], cwd=exported_repo, check=True)
    subprocess.run(
        ["git", "commit", "-qm", "Export hook repo for try-repo tests"],
        cwd=exported_repo,
        check=True,
    )
    return exported_repo


@pytest.fixture(scope="session")
def pre_commit_home(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("pre-commit-home")


def _run_try_repo(
    *,
    exported_hook_repo: Path,
    pre_commit_home: Path,
    tmp_path: Path,
    hook_id: str,
    files: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    _init_git_repo(tmp_path)
    file_paths: list[str] = []
    for relative_path, content in files.items():
        target = tmp_path / relative_path
        _write_file(target, content)
        file_paths.append(relative_path)

    subprocess.run(["git", "add", "--", *file_paths], cwd=tmp_path, check=True)

    env = os.environ.copy()
    env["PRE_COMMIT_HOME"] = str(pre_commit_home)
    return _run(
        ["pre-commit", "try-repo", str(exported_hook_repo), hook_id, "--files", *file_paths],
        cwd=tmp_path,
        env=env,
    )


def test_lint_no_chinese_validates_scope(
    exported_hook_repo: Path,
    pre_commit_home: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    failing_repo = tmp_path_factory.mktemp("lint-no-chinese-fail")
    failing_result = _run_try_repo(
        exported_hook_repo=exported_hook_repo,
        pre_commit_home=pre_commit_home,
        tmp_path=failing_repo,
        hook_id="lint-no-chinese",
        files={"src/app.py": 'print("\u4e2d\u6587")\n'},
    )
    assert failing_result.returncode == 1, _combined_output(failing_result)
    assert "contains Chinese characters" in _combined_output(failing_result)

    passing_repo = tmp_path_factory.mktemp("lint-no-chinese-pass")
    passing_result = _run_try_repo(
        exported_hook_repo=exported_hook_repo,
        pre_commit_home=pre_commit_home,
        tmp_path=passing_repo,
        hook_id="lint-no-chinese",
        files={"AGENTS.md": "\u4e2d\u6587\n"},
    )
    assert passing_result.returncode == 0, _combined_output(passing_result)


def test_lint_shell_portability_validates_scope(
    exported_hook_repo: Path,
    pre_commit_home: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    failing_repo = tmp_path_factory.mktemp("lint-shell-portability-fail")
    failing_result = _run_try_repo(
        exported_hook_repo=exported_hook_repo,
        pre_commit_home=pre_commit_home,
        tmp_path=failing_repo,
        hook_id="lint-shell-portability",
        files={"scripts/build.sh": "sed -i 's/a/b/' file.txt\n"},
    )
    assert failing_result.returncode == 1, _combined_output(failing_result)
    assert "SHP002" in _combined_output(failing_result)

    passing_repo = tmp_path_factory.mktemp("lint-shell-portability-pass")
    passing_result = _run_try_repo(
        exported_hook_repo=exported_hook_repo,
        pre_commit_home=pre_commit_home,
        tmp_path=passing_repo,
        hook_id="lint-shell-portability",
        files={"frontend/dist/build.sh": "sed -i 's/a/b/' file.txt\n"},
    )
    assert passing_result.returncode == 0, _combined_output(passing_result)


def test_lint_backend_bare_dict_validates_scope(
    exported_hook_repo: Path,
    pre_commit_home: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    failing_repo = tmp_path_factory.mktemp("lint-backend-bare-dict-fail")
    failing_result = _run_try_repo(
        exported_hook_repo=exported_hook_repo,
        pre_commit_home=pre_commit_home,
        tmp_path=failing_repo,
        hook_id="lint-backend-bare-dict",
        files={"app/service.py": 'payload = {"name": "demo"}\n'},
    )
    assert failing_result.returncode == 1, _combined_output(failing_result)
    assert "bare dict literal is forbidden" in _combined_output(failing_result)

    passing_repo = tmp_path_factory.mktemp("lint-backend-bare-dict-pass")
    passing_result = _run_try_repo(
        exported_hook_repo=exported_hook_repo,
        pre_commit_home=pre_commit_home,
        tmp_path=passing_repo,
        hook_id="lint-backend-bare-dict",
        files={"tests/test_service.py": 'payload = {"name": "demo"}\n'},
    )
    assert passing_result.returncode == 0, _combined_output(passing_result)


def test_lint_pre_commit_hook_languages_validates_scope(
    exported_hook_repo: Path,
    pre_commit_home: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    failing_repo = tmp_path_factory.mktemp("lint-hook-language-fail")
    failing_result = _run_try_repo(
        exported_hook_repo=exported_hook_repo,
        pre_commit_home=pre_commit_home,
        tmp_path=failing_repo,
        hook_id="lint-pre-commit-hook-languages",
        files={
            ".pre-commit-hooks.yaml": """
                - id: bad-python-hook
                  name: Bad Python hook
                  entry: python -m tools.check
                  language: script
            """,
        },
    )
    assert failing_result.returncode == 1, _combined_output(failing_result)
    assert "language is 'script'" in _combined_output(failing_result)

    passing_repo = tmp_path_factory.mktemp("lint-hook-language-pass")
    passing_result = _run_try_repo(
        exported_hook_repo=exported_hook_repo,
        pre_commit_home=pre_commit_home,
        tmp_path=passing_repo,
        hook_id="lint-pre-commit-hook-languages",
        files={
            ".pre-commit-hooks.yaml": """
                - id: shellcheck-wrapper
                  name: Shell wrapper
                  entry: shellcheck
                  language: system
            """,
        },
    )
    assert passing_result.returncode == 0, _combined_output(passing_result)
