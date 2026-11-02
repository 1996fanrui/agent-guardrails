from __future__ import annotations

from pathlib import Path

import pytest

from agent_guardrails.python.lint_uv_long_running import check_file


def _violations(tmp_path: Path, content: str) -> list[str]:
    unit = tmp_path / "demo.service"
    unit.write_text(content, encoding="utf-8")
    return check_file(unit)


def _service(exec_start: str, *extra: str) -> str:
    lines = ["[Unit]", "Description=demo", "", "[Service]", f"ExecStart={exec_start}", *extra]
    return "\n".join(lines) + "\n"


@pytest.mark.parametrize(
    "exec_start",
    [
        "uv run app.py",
        "/home/user/.local/bin/uv run app.py",
        "%h/.local/bin/uv run app.py",
        "-/usr/bin/uv run app.py",
        "/usr/bin/flock -n -E 0 %t/app.lock /home/user/.local/bin/uv run app.py",
        "/usr/bin/flock /tmp/uv run-me uv run app.py",
        "/usr/bin/flock %t/app.lock -c 'uv run app.py'",
        "/bin/bash -lc 'cd /srv/app && exec uv run app.py'",
        "/bin/sh -c 'uv sync && uv run --no-cache a.py; uv run b.py'",
        "uv --directory /srv/app run app.py",
        "uv run --quiet app.py",
        "uv run --project /srv/app python app.py",
        # After the command starts, the flag belongs to the app rather than to uv.
        "uv run app.py --no-cache",
        "uv run -- --no-cache",
        # Fails closed: telling an option value from a command needs uv's option table.
        "uv run --project /srv/app --no-cache python app.py",
        "uv run --no-cache-dir app.py",
        "uv run -n app.py",
    ],
)
def test_long_running_without_flag_fails(tmp_path: Path, exec_start: str) -> None:
    violations = _violations(tmp_path, _service(exec_start))

    assert len(violations) == 1
    assert ":5: long-running ExecStart must use `uv run --no-cache`" in violations[0]


@pytest.mark.parametrize(
    "exec_start",
    [
        "uv run --no-cache app.py",
        "/home/user/.local/bin/uv run --no-cache app.py",
        "%h/.local/bin/uv run --no-cache --project /srv/app python app.py",
        "/usr/bin/flock -n -E 0 %t/app.lock /home/user/.local/bin/uv run --no-cache app.py",
        "/usr/bin/flock %t/app.lock -c 'uv run --no-cache app.py'",
        "/bin/bash -lc 'cd /srv/app && exec uv run --no-cache app.py'",
        "uv run --quiet --no-cache app.py",
        "uv --no-cache run app.py",
    ],
)
def test_long_running_with_flag_passes(tmp_path: Path, exec_start: str) -> None:
    assert _violations(tmp_path, _service(exec_start)) == []


@pytest.mark.parametrize("service_type", ["simple", "exec", "notify", "forking", "dbus", "idle"])
def test_non_oneshot_types_are_long_running(tmp_path: Path, service_type: str) -> None:
    assert _violations(tmp_path, _service("uv run app.py", f"Type={service_type}"))


@pytest.mark.parametrize(
    "extra",
    [
        ("Type=oneshot",),
        ("Type = oneshot",),
        ("Type=simple", "Type=oneshot"),
    ],
)
def test_oneshot_passes(tmp_path: Path, extra: tuple[str, ...]) -> None:
    assert _violations(tmp_path, _service("uv run app.py", *extra)) == []


def test_last_type_wins(tmp_path: Path) -> None:
    assert _violations(tmp_path, _service("uv run app.py", "Type=oneshot", "Type=simple"))


def test_oneshot_outside_service_section_does_not_count(tmp_path: Path) -> None:
    content = "[Install]\nType=oneshot\n\n[Service]\nExecStart=uv run app.py\n"
    assert _violations(tmp_path, content)


@pytest.mark.parametrize(
    "exec_start",
    [
        "/usr/bin/python3 app.py",
        "/usr/bin/uvicorn app:app",
        "/opt/uv/bin/tool run app.py",
        "uv sync",
        "uv pip install run",
        "/usr/bin/flock /tmp/uv.lock /usr/bin/python3 run.py",
    ],
)
def test_service_not_running_uv_run_passes(tmp_path: Path, exec_start: str) -> None:
    assert _violations(tmp_path, _service(exec_start)) == []


def test_only_exec_start_is_checked(tmp_path: Path) -> None:
    content = (
        "[Service]\n"
        "# ExecStart=uv run commented.py\n"
        "; ExecStart=uv run commented.py\n"
        "ExecStartPre=uv run migrate.py\n"
        "Environment=NOTE=uv run app.py\n"
        "ExecStart=/usr/bin/python3 app.py\n"
    )
    assert _violations(tmp_path, content) == []


def test_exec_start_outside_service_section_is_ignored(tmp_path: Path) -> None:
    assert _violations(tmp_path, "[Unit]\nExecStart=uv run app.py\n") == []


def test_line_continuation_is_joined_and_reported_at_its_first_line(tmp_path: Path) -> None:
    content = "[Service]\nExecStart=/usr/bin/flock %t/app.lock \\\n  # comment\n  uv run \\\n  app.py\n"
    violations = _violations(tmp_path, content)

    assert len(violations) == 1
    assert violations[0].startswith(f"{tmp_path / 'demo.service'}:2:")

    fixed = content.replace("uv run", "uv run --no-cache")
    assert _violations(tmp_path, fixed) == []


def test_empty_exec_start_resets_earlier_entries(tmp_path: Path) -> None:
    content = "[Service]\nExecStart=uv run old.py\nExecStart=\nExecStart=uv run --no-cache new.py\n"
    assert _violations(tmp_path, content) == []


def test_every_offending_exec_start_is_reported(tmp_path: Path) -> None:
    content = "[Service]\nExecStart=uv run a.py\nExecStart=uv run --no-cache b.py\nExecStart=uv run c.py\n"
    assert len(_violations(tmp_path, content)) == 2


def test_unparseable_exec_start_fails(tmp_path: Path) -> None:
    violations = _violations(tmp_path, _service("/bin/sh -c 'uv run app.py"))

    assert len(violations) == 1
    assert "cannot parse ExecStart" in violations[0]
