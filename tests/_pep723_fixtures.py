"""Shared fixtures for lint-pep723-header tests.

Lifted out of `test_hook_repository.py` to keep that file under the repo's
file-line-count limit. Importable as a sibling module from any test in this
package.

The hook enforces three things on every scanned file:
  1) a PEP 723 `# /// script` block,
  2) a single `>=X.Y` requires-python (>= baseline 3.10),
  3) a module docstring that contains `uv run <self-filename>`.

Fixtures are constructed by `pep723_fixture()` rather than indented f-strings
because `textwrap.dedent()` (used by `_write_file` in the test helpers)
collapses all whitespace whenever any embedded line is fully left-aligned,
which would mangle the multi-line docstring inside the script.
"""

from __future__ import annotations


OK_FILENAME = "ok.py"
BAD_FILENAME = "bad.py"


def ok_docstring(filename: str) -> str:
    return (
        '"""Example script.\n'
        "\n"
        "Usage:\n"
        f"    uv run {filename}\n"
        '"""'
    )


def pep723_fixture(
    filename: str,
    *,
    block_lines: list[str] | None,
    docstring: str | None = None,
    body: str = 'print("hi")',
    shebang: bool = False,
) -> str:
    """Assemble a Python source fixture as a flat, dedent-safe string.

    ``block_lines`` are the raw lines that go between ``# /// script`` and
    ``# ///`` (without the leading ``# `` prefix); pass ``None`` to omit the
    PEP 723 block entirely. ``docstring`` defaults to the canonical OK
    docstring for ``filename`` (use the empty string to opt in); pass ``None``
    to omit the module docstring entirely.
    """
    parts: list[str] = []
    if shebang:
        parts.append("#!/usr/bin/env python3")
    if block_lines is not None:
        parts.append("# /// script")
        parts.extend(f"# {line}" if line else "#" for line in block_lines)
        parts.append("# ///")
    if docstring is None:
        rendered_docstring = ""
    elif docstring == "":
        rendered_docstring = ok_docstring(filename)
    else:
        rendered_docstring = docstring
    if rendered_docstring:
        parts.append(rendered_docstring)
    parts.append(body)
    return "\n".join(parts) + "\n"


_OK_BLOCK_LINES = ['requires-python = ">=3.10"', 'dependencies = ["requests"]']
_OK_BLOCK_312 = ['requires-python = ">=3.12"', "dependencies = []"]
_OK_BLOCK_3101 = ['requires-python = ">=3.10.1"', "dependencies = []"]
_OK_BLOCK_311_SPACES = ['requires-python = ">= 3.11"', "dependencies = []"]


PEP723_OK_BLOCK = pep723_fixture(OK_FILENAME, block_lines=_OK_BLOCK_LINES, docstring="")
PEP723_OK_BLOCK_AFTER_SHEBANG = pep723_fixture(
    OK_FILENAME, block_lines=_OK_BLOCK_312, docstring="", shebang=True
)
PEP723_OK_THREE_SEGMENT = pep723_fixture(OK_FILENAME, block_lines=_OK_BLOCK_3101, docstring="")
PEP723_OK_WITH_SPACES = pep723_fixture(OK_FILENAME, block_lines=_OK_BLOCK_311_SPACES, docstring="")

PEP723_MISSING_REQUIRES = pep723_fixture(
    BAD_FILENAME, block_lines=['dependencies = ["requests"]'], docstring=""
)
PEP723_UNSUPPORTED_FORM = pep723_fixture(
    BAD_FILENAME, block_lines=['requires-python = "==3.11"', "dependencies = []"], docstring=""
)
PEP723_RANGE_FORM = pep723_fixture(
    BAD_FILENAME, block_lines=['requires-python = ">=3.10,<3.13"', "dependencies = []"], docstring=""
)
PEP723_BELOW_BASELINE = pep723_fixture(
    BAD_FILENAME, block_lines=['requires-python = ">=3.8"', "dependencies = []"], docstring=""
)
PEP723_INVALID_PEP440 = pep723_fixture(
    BAD_FILENAME, block_lines=['requires-python = "not-a-version"', "dependencies = []"], docstring=""
)

# Bare module without any PEP 723 block — the strict-mode hook must FAIL this.
PEP723_NO_BLOCK = pep723_fixture(BAD_FILENAME, block_lines=None, docstring="")

# PEP 723 block is fine but the file has no module docstring at all.
PEP723_NO_DOCSTRING = pep723_fixture(
    BAD_FILENAME,
    block_lines=['requires-python = ">=3.10"', "dependencies = []"],
    docstring=None,
)

# Docstring exists but does not show the canonical `uv run <self>` invocation.
PEP723_DOCSTRING_NO_UV_RUN = pep723_fixture(
    BAD_FILENAME,
    block_lines=['requires-python = ">=3.10"', "dependencies = []"],
    docstring='"""Example script.\n\nRun it however you like.\n"""',
)
