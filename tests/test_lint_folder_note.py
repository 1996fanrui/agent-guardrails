from __future__ import annotations

from pathlib import Path

import pytest

from agent_guardrails.general import lint_folder_note


def _write(root: Path, relative_paths: list[str]) -> None:
    for relative_path in relative_paths:
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("note\n", encoding="utf-8")


def _run_main(monkeypatch: pytest.MonkeyPatch, files: list[str], *options: str) -> int:
    monkeypatch.setattr("sys.argv", ["lint-folder-note", *options, *files])
    return lint_folder_note.main()


def test_passes_when_every_directory_has_a_folder_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = ["README.md", "Kafka/Kafka.md", "Kafka/Broker/Broker.md", "Kafka/Broker/design.md"]
    _write(tmp_path, files)
    monkeypatch.chdir(tmp_path)

    assert _run_main(monkeypatch, files) == 0


def test_reports_every_directory_missing_its_folder_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    files = ["README.md", "Kafka/Kafka.md", "Kafka/Broker/design.md", "Flink/state.md", "Flink/sql.md"]
    _write(tmp_path, files)
    monkeypatch.chdir(tmp_path)

    assert _run_main(monkeypatch, files) == 1
    output = capsys.readouterr().out
    assert "Flink/ is missing its folder note Flink/Flink.md" in output
    assert "Kafka/Broker/ is missing its folder note Kafka/Broker/Broker.md" in output
    # Each directory is reported once, and directories with a folder note are not reported.
    assert output.count("Flink/ is missing") == 1
    assert "  - Kafka/ is missing" not in output


def test_root_level_files_are_not_checked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(tmp_path, ["README.md", "CHANGELOG.md"])
    monkeypatch.chdir(tmp_path)

    assert _run_main(monkeypatch, ["README.md", "CHANGELOG.md"]) == 0


def test_reports_category_directory_that_only_holds_subdirectories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    files = ["engineering/Kafka/Kafka.md"]
    _write(tmp_path, files)
    monkeypatch.chdir(tmp_path)

    assert _run_main(monkeypatch, files) == 1
    output = capsys.readouterr().out
    assert "engineering/ is missing its folder note engineering/engineering.md" in output
    assert "engineering/Kafka/ is missing" not in output


TOP_LEVEL_OPTION = "--top-level-folder-note-only"


def test_top_level_option_passes_when_top_level_holds_only_its_folder_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = ["README.md", "engineering/engineering.md", "engineering/Kafka/Kafka.md", "engineering/Kafka/broker.md"]
    _write(tmp_path, files)
    monkeypatch.chdir(tmp_path)

    assert _run_main(monkeypatch, files, TOP_LEVEL_OPTION) == 0


def test_top_level_option_reports_other_notes_in_top_level_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    files = ["engineering/engineering.md", "engineering/kafka-tips.md", "engineering/Kafka/Kafka.md"]
    _write(tmp_path, files)
    monkeypatch.chdir(tmp_path)

    assert _run_main(monkeypatch, files, TOP_LEVEL_OPTION) == 1
    output = capsys.readouterr().out
    assert "engineering/kafka-tips.md is in top-level directory engineering/" in output
    assert "engineering/engineering.md is in" not in output
    assert "engineering/Kafka/Kafka.md is in" not in output


def test_top_level_notes_are_allowed_without_the_option(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = ["engineering/engineering.md", "engineering/kafka-tips.md"]
    _write(tmp_path, files)
    monkeypatch.chdir(tmp_path)

    assert _run_main(monkeypatch, files) == 0
