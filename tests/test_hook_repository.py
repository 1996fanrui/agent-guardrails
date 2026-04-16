from __future__ import annotations

import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

from _pep723_fixtures import (
    BAD_FILENAME as _BAD_FILENAME,
    OK_FILENAME as _OK_FILENAME,
    PEP723_BELOW_BASELINE as _PEP723_BELOW_BASELINE,
    PEP723_DOCSTRING_NO_UV_RUN as _PEP723_DOCSTRING_NO_UV_RUN,
    PEP723_INVALID_PEP440 as _PEP723_INVALID_PEP440,
    PEP723_MISSING_REQUIRES as _PEP723_MISSING_REQUIRES,
    PEP723_NO_BLOCK as _PEP723_NO_BLOCK,
    PEP723_NO_DOCSTRING as _PEP723_NO_DOCSTRING,
    PEP723_OK_BLOCK as _PEP723_OK_BLOCK,
    PEP723_OK_BLOCK_AFTER_SHEBANG as _PEP723_OK_BLOCK_AFTER_SHEBANG,
    PEP723_OK_THREE_SEGMENT as _PEP723_OK_THREE_SEGMENT,
    PEP723_OK_WITH_SPACES as _PEP723_OK_WITH_SPACES,
    PEP723_RANGE_FORM as _PEP723_RANGE_FORM,
    PEP723_UNSUPPORTED_FORM as _PEP723_UNSUPPORTED_FORM,
)


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


def _run_exported_repo_self_check(
    *,
    exported_hook_repo: Path,
    pre_commit_home: Path,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PRE_COMMIT_HOME"] = str(pre_commit_home)
    return _run(
        ["pre-commit", "run", "--all-files", "--config", ".pre-commit-config.yaml"],
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
        files={
            "AGENTS.md": "\u4e2d\u6587\n",
            "docs/zh/design.md": "\u4e2d\u6587\n",
        },
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

    passing_lockfile_repo = tmp_path_factory.mktemp("lint-file-line-count-lockfile-pass")
    passing_lockfile_result = _run_try_repo(
        exported_hook_repo=exported_hook_repo,
        pre_commit_home=pre_commit_home,
        tmp_path=passing_lockfile_repo,
        hook_id="lint-file-line-count",
        files={"backend/uv.lock": "\n".join(f"Line {index}" for index in range(1, 1002))},
    )
    assert passing_lockfile_result.returncode == 0, _combined_output(passing_lockfile_result)


@pytest.mark.parametrize(
    ("hook_id", "expected_output"),
    (
        ("lint-enum-redundant-string", "No redundant enum string literals"),
        ("lint-no-chinese", "No Chinese characters in source"),
        ("lint-file-line-count", "File line-count limit"),
        ("lint-no-ignored-files", "No gitignored files in staging"),
        ("lint-pre-commit-hook-languages", "Pre-commit hook language selection"),
        ("lint-pep723-header", "PEP 723 header compliance"),
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


def test_repository_self_check_config_runs_current_repo_hooks(
    exported_hook_repo: Path,
    pre_commit_home: Path,
) -> None:
    result = _run_exported_repo_self_check(
        exported_hook_repo=exported_hook_repo,
        pre_commit_home=pre_commit_home,
    )
    assert result.returncode == 0, _combined_output(result)

    output = _combined_output(result)
    assert "Shell portability (no GNU-only syntax)" in output
    assert "No Chinese characters in source" in output
    assert "File line-count limit" in output
    assert "No bare dict in backend Python" in output
    assert "No redundant enum string literals" in output
    assert "No gitignored files in staging" in output
    assert "Pre-commit hook language selection" in output
    assert "PEP 723 header compliance" in output


def test_lint_enum_redundant_string_validates_scope(
    exported_hook_repo: Path,
    pre_commit_home: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    failing_repo = tmp_path_factory.mktemp("lint-enum-redundant-string-fail")
    failing_result = _run_try_repo(
        exported_hook_repo=exported_hook_repo,
        pre_commit_home=pre_commit_home,
        tmp_path=failing_repo,
        hook_id="lint-enum-redundant-string",
        files={
            "src/models.py": """
                from enum import StrEnum


                class LegacyEnum(StrEnum):
                    @staticmethod
                    def _generate_next_value_(name, start, count, last_values):
                        return name


                class SomeAction(StrEnum):
                    CONTINUE = "continue"
            """,
        },
    )
    assert failing_result.returncode == 1, _combined_output(failing_result)
    assert "LegacyEnum defines _generate_next_value_" in _combined_output(failing_result)
    assert "SomeAction.CONTINUE repeats string literal" in _combined_output(failing_result)

    passing_tests_repo = tmp_path_factory.mktemp("lint-enum-redundant-string-tests-pass")
    passing_tests_result = _run_try_repo(
        exported_hook_repo=exported_hook_repo,
        pre_commit_home=pre_commit_home,
        tmp_path=passing_tests_repo,
        hook_id="lint-enum-redundant-string",
        files={
            "tests/test_models.py": """
                from enum import StrEnum


                class SomeAction(StrEnum):
                    CONTINUE = "continue"
            """,
        },
    )
    assert passing_tests_result.returncode == 0, _combined_output(passing_tests_result)

    passing_noqa_repo = tmp_path_factory.mktemp("lint-enum-redundant-string-noqa-pass")
    passing_noqa_result = _run_try_repo(
        exported_hook_repo=exported_hook_repo,
        pre_commit_home=pre_commit_home,
        tmp_path=passing_noqa_repo,
        hook_id="lint-enum-redundant-string",
        files={
            "pkg/common/enum_utils.py": """
                from enum import StrEnum


                class _UpperNameStrEnum(StrEnum):
                    @staticmethod
                    def _generate_next_value_(name, start, count, last_values):
                        return name
            """,
            "pkg/models.py": """
                from enum import StrEnum


                class SomeAction(StrEnum):
                    CONTINUE = "continue"  # noqa: enum-string


                class LocalEnum(StrEnum):
                    @staticmethod
                    def _generate_next_value_(name, start, count, last_values):  # noqa: enum-base
                        return name
            """,
        },
    )
    assert passing_noqa_result.returncode == 0, _combined_output(passing_noqa_result)

    failing_spoofed_shared_base_repo = tmp_path_factory.mktemp(
        "lint-enum-redundant-string-spoofed-shared-base-fail"
    )
    failing_spoofed_shared_base_result = _run_try_repo(
        exported_hook_repo=exported_hook_repo,
        pre_commit_home=pre_commit_home,
        tmp_path=failing_spoofed_shared_base_repo,
        hook_id="lint-enum-redundant-string",
        files={
            "nested/pkg/common/enum_utils.py": """
                from enum import StrEnum


                class _UpperNameStrEnum(StrEnum):
                    @staticmethod
                    def _generate_next_value_(name, start, count, last_values):
                        return name
            """,
        },
    )
    assert (
        failing_spoofed_shared_base_result.returncode == 1
    ), _combined_output(failing_spoofed_shared_base_result)
    assert (
        "_UpperNameStrEnum defines _generate_next_value_"
        in _combined_output(failing_spoofed_shared_base_result)
    )

    failing_aliased_enum_repo = tmp_path_factory.mktemp("lint-enum-redundant-string-aliased-fail")
    failing_aliased_enum_result = _run_try_repo(
        exported_hook_repo=exported_hook_repo,
        pre_commit_home=pre_commit_home,
        tmp_path=failing_aliased_enum_repo,
        hook_id="lint-enum-redundant-string",
        files={
            "src/aliased_models.py": """
                from enum import Enum as E
                from enum import StrEnum as S


                class LegacyEnum(S):
                    @staticmethod
                    def _generate_next_value_(name, start, count, last_values):
                        return name


                class SomeAction(S):
                    CONTINUE = "continue"


                class Status(E):
                    READY = "ready"
            """,
        },
    )
    assert failing_aliased_enum_result.returncode == 1, _combined_output(failing_aliased_enum_result)
    aliased_output = _combined_output(failing_aliased_enum_result)
    assert "LegacyEnum defines _generate_next_value_" in aliased_output
    assert "SomeAction.CONTINUE repeats string literal" in aliased_output
    assert "Status.READY repeats string literal" in aliased_output


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


def test_lint_no_ignored_files_validates_scope(
    exported_hook_repo: Path,
    pre_commit_home: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    # Positive case: a gitignored file that is force-staged must fail.
    failing_repo = tmp_path_factory.mktemp("lint-no-ignored-files-fail")
    _init_git_repo(failing_repo)
    _write_file(failing_repo / ".gitignore", "*.log\n")
    subprocess.run(["git", "add", ".gitignore"], cwd=failing_repo, check=True)
    subprocess.run(["git", "commit", "-qm", "add gitignore"], cwd=failing_repo, check=True)
    _write_file(failing_repo / "debug.log", "some log output\n")
    subprocess.run(["git", "add", "-f", "debug.log"], cwd=failing_repo, check=True)

    env = os.environ.copy()
    env["PRE_COMMIT_HOME"] = str(pre_commit_home)
    failing_result = _run(
        [
            "pre-commit", "try-repo", str(exported_hook_repo),
            "lint-no-ignored-files", "--files", "debug.log",
        ],
        cwd=failing_repo,
        env=env,
    )
    assert failing_result.returncode == 1, _combined_output(failing_result)
    assert "Ignored files must not be committed" in _combined_output(failing_result)

    # Negative case: a normal (non-ignored) file must pass.
    passing_repo = tmp_path_factory.mktemp("lint-no-ignored-files-pass")
    passing_result = _run_try_repo(
        exported_hook_repo=exported_hook_repo,
        pre_commit_home=pre_commit_home,
        tmp_path=passing_repo,
        hook_id="lint-no-ignored-files",
        files={"src/main.py": "print('hello')\n"},
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


def test_lint_pep723_header_passes_when_header_and_docstring_are_valid(
    exported_hook_repo: Path,
    pre_commit_home: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    passing_repo = tmp_path_factory.mktemp("lint-pep723-pass")
    # Each file is written under the canonical _OK_FILENAME so the docstring's
    # `uv run ok.py` line matches the on-disk filename.
    passing_result = _run_try_repo(
        exported_hook_repo=exported_hook_repo,
        pre_commit_home=pre_commit_home,
        tmp_path=passing_repo,
        hook_id="lint-pep723-header",
        files={_OK_FILENAME: _PEP723_OK_BLOCK},
    )
    assert passing_result.returncode == 0, _combined_output(passing_result)

    for label, body in (
        ("after-shebang", _PEP723_OK_BLOCK_AFTER_SHEBANG),
        ("three-segment", _PEP723_OK_THREE_SEGMENT),
        ("with-spaces", _PEP723_OK_WITH_SPACES),
    ):
        repo = tmp_path_factory.mktemp(f"lint-pep723-pass-{label}")
        result = _run_try_repo(
            exported_hook_repo=exported_hook_repo,
            pre_commit_home=pre_commit_home,
            tmp_path=repo,
            hook_id="lint-pep723-header",
            files={_OK_FILENAME: body},
        )
        assert result.returncode == 0, _combined_output(result)


def test_lint_pep723_header_rejects_missing_block(
    exported_hook_repo: Path,
    pre_commit_home: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Strict mode: a `.py` without a `# /// script` block is itself a violation."""
    failing_repo = tmp_path_factory.mktemp("lint-pep723-no-block")
    failing_result = _run_try_repo(
        exported_hook_repo=exported_hook_repo,
        pre_commit_home=pre_commit_home,
        tmp_path=failing_repo,
        hook_id="lint-pep723-header",
        files={_BAD_FILENAME: _PEP723_NO_BLOCK},
    )
    assert failing_result.returncode == 1, _combined_output(failing_result)
    assert "missing PEP 723 inline metadata block" in _combined_output(failing_result)


def test_lint_pep723_header_rejects_missing_requires_python(
    exported_hook_repo: Path,
    pre_commit_home: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    failing_repo = tmp_path_factory.mktemp("lint-pep723-missing-requires")
    failing_result = _run_try_repo(
        exported_hook_repo=exported_hook_repo,
        pre_commit_home=pre_commit_home,
        tmp_path=failing_repo,
        hook_id="lint-pep723-header",
        files={_BAD_FILENAME: _PEP723_MISSING_REQUIRES},
    )
    assert failing_result.returncode == 1, _combined_output(failing_result)
    assert "missing 'requires-python'" in _combined_output(failing_result)


def test_lint_pep723_header_rejects_non_pep440(
    exported_hook_repo: Path,
    pre_commit_home: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    failing_repo = tmp_path_factory.mktemp("lint-pep723-invalid-pep440")
    failing_result = _run_try_repo(
        exported_hook_repo=exported_hook_repo,
        pre_commit_home=pre_commit_home,
        tmp_path=failing_repo,
        hook_id="lint-pep723-header",
        files={_BAD_FILENAME: _PEP723_INVALID_PEP440},
    )
    assert failing_result.returncode == 1, _combined_output(failing_result)
    assert "not a valid PEP 440 specifier" in _combined_output(failing_result)


def test_lint_pep723_header_rejects_unsupported_forms(
    exported_hook_repo: Path,
    pre_commit_home: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    for label, body in (("eq", _PEP723_UNSUPPORTED_FORM), ("range", _PEP723_RANGE_FORM)):
        repo = tmp_path_factory.mktemp(f"lint-pep723-form-{label}")
        result = _run_try_repo(
            exported_hook_repo=exported_hook_repo,
            pre_commit_home=pre_commit_home,
            tmp_path=repo,
            hook_id="lint-pep723-header",
            files={_BAD_FILENAME: body},
        )
        assert result.returncode == 1, _combined_output(result)
        assert "unsupported form" in _combined_output(result)


def test_lint_pep723_header_enforces_default_baseline(
    exported_hook_repo: Path,
    pre_commit_home: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    failing_repo = tmp_path_factory.mktemp("lint-pep723-below-baseline")
    failing_result = _run_try_repo(
        exported_hook_repo=exported_hook_repo,
        pre_commit_home=pre_commit_home,
        tmp_path=failing_repo,
        hook_id="lint-pep723-header",
        files={_BAD_FILENAME: _PEP723_BELOW_BASELINE},
    )
    assert failing_result.returncode == 1, _combined_output(failing_result)
    output = _combined_output(failing_result)
    assert "'>=3.8'" in output
    assert 'below baseline ">=3.10"' in output


def test_lint_pep723_header_rejects_missing_docstring(
    exported_hook_repo: Path,
    pre_commit_home: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    failing_repo = tmp_path_factory.mktemp("lint-pep723-no-docstring")
    failing_result = _run_try_repo(
        exported_hook_repo=exported_hook_repo,
        pre_commit_home=pre_commit_home,
        tmp_path=failing_repo,
        hook_id="lint-pep723-header",
        files={_BAD_FILENAME: _PEP723_NO_DOCSTRING},
    )
    assert failing_result.returncode == 1, _combined_output(failing_result)
    assert "missing module docstring" in _combined_output(failing_result)


def test_lint_pep723_header_rejects_docstring_without_uv_run_example(
    exported_hook_repo: Path,
    pre_commit_home: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    failing_repo = tmp_path_factory.mktemp("lint-pep723-no-uv-run")
    failing_result = _run_try_repo(
        exported_hook_repo=exported_hook_repo,
        pre_commit_home=pre_commit_home,
        tmp_path=failing_repo,
        hook_id="lint-pep723-header",
        files={_BAD_FILENAME: _PEP723_DOCSTRING_NO_UV_RUN},
    )
    assert failing_result.returncode == 1, _combined_output(failing_result)
    output = _combined_output(failing_result)
    assert f"`uv run {_BAD_FILENAME}` invocation example" in output


def test_lint_pep723_header_accepts_consumer_override(
    exported_hook_repo: Path,
    pre_commit_home: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    # --min-python=3.9 lets the body's ">=3.8" still fail (below baseline).
    below_repo = tmp_path_factory.mktemp("lint-pep723-override-below")
    below_result = _run_with_repo_config(
        exported_hook_repo=exported_hook_repo,
        pre_commit_home=pre_commit_home,
        tmp_path=below_repo,
        hook_id="lint-pep723-header",
        hook_args=["--min-python=3.9"],
        files={_BAD_FILENAME: _PEP723_BELOW_BASELINE},
    )
    assert below_result.returncode == 1, _combined_output(below_result)

    # Raising the floor to 3.12 must reject the default ">=3.10" sample.
    strict_repo = tmp_path_factory.mktemp("lint-pep723-override-strict")
    strict_result = _run_with_repo_config(
        exported_hook_repo=exported_hook_repo,
        pre_commit_home=pre_commit_home,
        tmp_path=strict_repo,
        hook_id="lint-pep723-header",
        hook_args=["--min-python=3.12"],
        files={_OK_FILENAME: _PEP723_OK_BLOCK},
    )
    assert strict_result.returncode == 1, _combined_output(strict_result)
    assert 'below baseline ">=3.12"' in _combined_output(strict_result)
