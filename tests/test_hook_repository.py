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


def _run_try_repo_against_exported_repo(
    *,
    exported_hook_repo: Path,
    pre_commit_home: Path,
    hook_id: str,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PRE_COMMIT_HOME"] = str(pre_commit_home)
    return _run(
        ["pre-commit", "try-repo", str(exported_hook_repo), hook_id, "--all-files"],
        cwd=exported_hook_repo,
        env=env,
    )


def _run_with_repo_config(
    *,
    exported_hook_repo: Path,
    pre_commit_home: Path,
    tmp_path: Path,
    hook_id: str,
    files: dict[str, str],
    hook_args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    _init_git_repo(tmp_path)
    file_paths: list[str] = []
    for relative_path, content in files.items():
        target = tmp_path / relative_path
        _write_file(target, content)
        file_paths.append(relative_path)

    config_lines = [
        "repos:",
        f"  - repo: {exported_hook_repo}",
        "    rev: HEAD",
        "    hooks:",
        f"      - id: {hook_id}",
    ]
    if hook_args:
        config_lines.append("        args:")
        config_lines.extend(f"          - {arg}" for arg in hook_args)

    _write_file(
        tmp_path / ".pre-commit-config.yaml",
        "\n".join(config_lines) + "\n",
    )

    subprocess.run(["git", "add", "--", ".pre-commit-config.yaml", *file_paths], cwd=tmp_path, check=True)

    env = os.environ.copy()
    env["PRE_COMMIT_HOME"] = str(pre_commit_home)
    return _run(
        ["pre-commit", "run", hook_id, "--all-files", "--config", ".pre-commit-config.yaml"],
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
        files={"scripts/build.sh": "echo 'hello world'\n"},
    )
    assert passing_result.returncode == 0, _combined_output(passing_result)


def test_lint_file_line_count_validates_scope(
    exported_hook_repo: Path,
    pre_commit_home: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    failing_repo = tmp_path_factory.mktemp("lint-file-line-count-fail")
    failing_result = _run_try_repo(
        exported_hook_repo=exported_hook_repo,
        pre_commit_home=pre_commit_home,
        tmp_path=failing_repo,
        hook_id="lint-file-line-count",
        files={"docs/guide.md": "\n".join(f"Line {index}" for index in range(1, 802))},
    )
    assert failing_result.returncode == 1, _combined_output(failing_result)
    assert "exceeds the maximum of 800" in _combined_output(failing_result)

    passing_repo = tmp_path_factory.mktemp("lint-file-line-count-pass")
    passing_result = _run_try_repo(
        exported_hook_repo=exported_hook_repo,
        pre_commit_home=pre_commit_home,
        tmp_path=passing_repo,
        hook_id="lint-file-line-count",
        files={"generated/client/api.md": "\n".join(f"Line {index}" for index in range(1, 802))},
    )
    assert passing_result.returncode == 0, _combined_output(passing_result)


@pytest.mark.parametrize(
    ("hook_id", "expected_output"),
    (
        ("lint-no-chinese", "No Chinese characters in source"),
        ("lint-file-line-count", "File line-count limit"),
        ("lint-pre-commit-hook-languages", "Pre-commit hook language selection"),
    ),
)
def test_repository_contents_pass_custom_hooks(
    exported_hook_repo: Path,
    pre_commit_home: Path,
    hook_id: str,
    expected_output: str,
) -> None:
    result = _run_try_repo_against_exported_repo(
        exported_hook_repo=exported_hook_repo,
        pre_commit_home=pre_commit_home,
        hook_id=hook_id,
    )
    assert result.returncode == 0, _combined_output(result)
    assert expected_output in _combined_output(result)


def test_lint_file_line_count_accepts_consumer_override(
    exported_hook_repo: Path,
    pre_commit_home: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    passing_repo = tmp_path_factory.mktemp("lint-file-line-count-override-pass")
    passing_result = _run_with_repo_config(
        exported_hook_repo=exported_hook_repo,
        pre_commit_home=pre_commit_home,
        tmp_path=passing_repo,
        hook_id="lint-file-line-count",
        hook_args=["--max-lines=1000"],
        files={"docs/guide.md": "\n".join(f"Line {index}" for index in range(1, 802))},
    )
    assert passing_result.returncode == 0, _combined_output(passing_result)

    failing_repo = tmp_path_factory.mktemp("lint-file-line-count-override-fail")
    failing_result = _run_with_repo_config(
        exported_hook_repo=exported_hook_repo,
        pre_commit_home=pre_commit_home,
        tmp_path=failing_repo,
        hook_id="lint-file-line-count",
        hook_args=["--max-lines=700"],
        files={"docs/guide.md": "\n".join(f"Line {index}" for index in range(1, 751))},
    )
    assert failing_result.returncode == 1, _combined_output(failing_result)
    assert "exceeds the maximum of 700" in _combined_output(failing_result)


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
