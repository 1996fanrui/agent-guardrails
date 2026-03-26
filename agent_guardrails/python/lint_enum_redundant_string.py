"""Lint rule: disallow redundant enum string literals."""

from __future__ import annotations

import ast
import sys
from pathlib import Path


NOQA_ENUM_STRING = "noqa: enum-string"
NOQA_ENUM_BASE = "noqa: enum-base"
SHARED_BASE_RELATIVE_PATH = ("common", "enum_utils.py")
ENUM_BASE_NAMES = frozenset({"Enum", "StrEnum"})
ENUM_STRING_FIX_HINT = (
    "Use auto() instead of repeating the member name text. "
    "Exact upper-name values should use the shared _UpperNameStrEnum base."
)


def _extract_base_name(base: ast.expr) -> str | None:
    """Return simple base class name for class inheritance checks."""
    while isinstance(base, ast.Subscript):
        base = base.value
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        return base.attr
    return None


def _extract_string_literal(value: ast.expr) -> str | None:
    """Return string literal value from an enum assignment if available."""
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    return None


def _collect_enum_base_names(module: ast.Module) -> set[str]:
    """Collect enum base names and direct import aliases from the module."""
    base_names = set(ENUM_BASE_NAMES)
    for node in module.body:
        if not isinstance(node, ast.ImportFrom) or node.module != "enum":
            continue
        for imported_name in node.names:
            if imported_name.name in ENUM_BASE_NAMES:
                base_names.add(imported_name.asname or imported_name.name)
    return base_names


def _is_enum_class(
    class_name: str,
    class_nodes: dict[str, ast.ClassDef],
    enum_base_names: set[str],
    memo: dict[str, bool],
    visiting: set[str],
) -> bool:
    """Return True when class inherits from Enum/StrEnum directly or indirectly."""
    if class_name in memo:
        return memo[class_name]
    if class_name in visiting:
        return False

    visiting.add(class_name)
    class_node = class_nodes[class_name]
    result = False

    for base in class_node.bases:
        base_name = _extract_base_name(base)
        if base_name is None:
            continue

        if base_name in enum_base_names or base_name.endswith("Enum"):
            result = True
            break

        if base_name in class_nodes and _is_enum_class(
            base_name, class_nodes, enum_base_names, memo, visiting
        ):
            result = True
            break

    visiting.remove(class_name)
    memo[class_name] = result
    return result


def _is_shared_base_definition(path: Path, class_name: str) -> bool:
    """Allow only the canonical package-root shared enum base definition."""
    return (
        class_name == "_UpperNameStrEnum"
        and len(path.parts) == len(SHARED_BASE_RELATIVE_PATH) + 1
        and path.parts[1:] == SHARED_BASE_RELATIVE_PATH
    )


def check_file(path: Path) -> list[str]:
    """Return enum policy violations for a single Python file."""
    source = path.read_text(encoding="utf-8")
    source_lines = source.splitlines()
    try:
        module = ast.parse(source)
    except SyntaxError as exc:
        return [f"{path}:{exc.lineno or 1} Failed to parse file: {exc.msg}."]

    class_nodes = {
        node.name: node for node in module.body if isinstance(node, ast.ClassDef)
    }
    enum_base_names = _collect_enum_base_names(module)
    memo: dict[str, bool] = {}
    violations: list[str] = []

    for class_name, class_node in class_nodes.items():
        if not _is_enum_class(class_name, class_nodes, enum_base_names, memo, set()):
            continue

        custom_generator = next(
            (
                node
                for node in class_node.body
                if isinstance(node, ast.FunctionDef)
                and node.name == "_generate_next_value_"
            ),
            None,
        )
        if custom_generator is not None:
            line = (
                source_lines[custom_generator.lineno - 1]
                if custom_generator.lineno <= len(source_lines)
                else ""
            )
            is_shared_base = _is_shared_base_definition(path, class_name)
            if not is_shared_base and NOQA_ENUM_BASE not in line:
                violations.append(
                    f"{path}:{custom_generator.lineno} "
                    f"{class_name} defines _generate_next_value_. "
                    "Use the shared common.enum_utils._UpperNameStrEnum base instead."
                )

        for stmt in class_node.body:
            target_name = None
            value_node = None

            if (
                isinstance(stmt, ast.Assign)
                and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)
            ):
                target_name = stmt.targets[0].id
                value_node = stmt.value
            elif (
                isinstance(stmt, ast.AnnAssign)
                and isinstance(stmt.target, ast.Name)
                and stmt.value is not None
            ):
                target_name = stmt.target.id
                value_node = stmt.value

            if target_name is None or value_node is None:
                continue
            if target_name.startswith("_"):
                continue

            literal_value = _extract_string_literal(value_node)
            if literal_value is None or target_name.casefold() != literal_value.casefold():
                continue

            line = source_lines[stmt.lineno - 1] if stmt.lineno <= len(source_lines) else ""
            if NOQA_ENUM_STRING in line:
                continue

            violations.append(
                f"{path}:{stmt.lineno} {class_name}.{target_name} repeats string literal "
                "ignoring case. "
                f"{ENUM_STRING_FIX_HINT}"
            )

    return violations


def main() -> int:
    files = [Path(filename) for filename in sys.argv[1:]]
    if not files:
        return 0

    violations: list[str] = []
    for path in files:
        violations.extend(check_file(path))

    if violations:
        print("Lint failed:")
        for violation in violations:
            print(f"  {violation}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
