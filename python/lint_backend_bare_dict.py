#!/usr/bin/env python3
"""Lint rule: disallow bare dict literals in backend runtime code.

Use structured models for protocol/API/storage payloads. Legitimate internal
mapping cases must carry an inline ``# noqa: bare-dict`` comment with a reason.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path


NOQA_TOKEN = "noqa: bare-dict"
NOQA_PATTERN = re.compile(r"noqa:\s*bare-dict\b(.*)")
UPPER_SNAKE_CASE = re.compile(r"^[A-Z][A-Z0-9_]*$")
SKIPPED_KEYWORDS = {"headers", "responses", "set_"}
SKIPPED_CALLS = {"urlencode"}
DICT_NODE_TYPES = (ast.Dict, ast.DictComp)


def build_parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    """Build a parent pointer map for upward context checks."""
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    return parents


def has_noqa_reason(lines: list[str], start_line: int, end_line: int) -> bool:
    """Return True when the dict span includes a valid bare-dict noqa reason."""
    for line_no in range(start_line, end_line + 1):
        if line_no <= 0 or line_no > len(lines):
            continue
        match = NOQA_PATTERN.search(lines[line_no - 1])
        if match is None:
            continue
        if match.group(1).strip():
            return True
    return False


def is_empty_dict(node: ast.AST) -> bool:
    """Return True when the node is an empty dict literal."""
    return isinstance(node, ast.Dict) and not node.keys


def annotation_is_mapping(annotation: ast.AST) -> bool:
    """Return True when a type annotation describes a mapping."""
    if isinstance(annotation, ast.Name):
        return annotation.id in {"dict", "Mapping", "MutableMapping"}
    if isinstance(annotation, ast.Attribute):
        return annotation.attr in {"dict", "Mapping", "MutableMapping"}
    if isinstance(annotation, ast.Subscript):
        return annotation_is_mapping(annotation.value)
    return False


def find_enclosing_function(
    node: ast.AST,
    parents: dict[ast.AST, ast.AST],
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """Return the closest enclosing function-like node."""
    current: ast.AST | None = node
    while current is not None:
        current = parents.get(current)
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return current
    return None


def is_returned_mapping(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    """Allow dicts returned from functions that declare a mapping return type."""
    parent = parents.get(node)
    if not isinstance(parent, ast.Return):
        return False
    function_node = find_enclosing_function(parent, parents)
    return (
        function_node is not None
        and function_node.returns is not None
        and annotation_is_mapping(function_node.returns)
    )


def is_optional_mapping_ifexp(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    """Allow ``dict if cond else None`` and ``None if cond else dict`` patterns."""
    parent = parents.get(node)
    if not isinstance(parent, ast.IfExp):
        return False
    return (
        parent.body is node
        and isinstance(parent.orelse, ast.Constant)
        and parent.orelse.value is None
    ) or (
        parent.orelse is node
        and isinstance(parent.body, ast.Constant)
        and parent.body.value is None
    )


def is_list_comprehension_element(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    """Allow dicts emitted as list-comprehension elements."""
    return isinstance(parents.get(node), ast.ListComp)


def is_module_level_constant(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    """Allow module-level constant lookup tables."""
    parent = parents.get(node)
    if not isinstance(parent, ast.Assign):
        return False
    grandparent = parents.get(parent)
    if not isinstance(grandparent, ast.Module):
        return False
    return any(
        isinstance(target, ast.Name) and UPPER_SNAKE_CASE.match(target.id)
        for target in parent.targets
    )


def is_typed_mapping_assignment(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    """Allow dicts assigned to explicitly typed mapping variables."""
    parent = parents.get(node)
    return isinstance(parent, ast.AnnAssign) and annotation_is_mapping(parent.annotation)


def is_empty_dict_accumulator(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    """Allow empty dict accumulators used for incremental population."""
    return is_empty_dict(node) and isinstance(parents.get(node), (ast.Assign, ast.AnnAssign))


def is_mapping_item_assignment(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    """Allow dict literals assigned into an existing mapping slot."""
    parent = parents.get(node)
    return isinstance(parent, ast.Assign) and any(
        isinstance(target, ast.Subscript) for target in parent.targets
    )


def is_dict_call_argument(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    """Allow dicts passed directly into function or method calls."""
    return isinstance(parents.get(node), (ast.Call, ast.keyword))


def is_or_fallback(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    """Allow ``expr or {}`` empty mapping fallbacks."""
    parent = parents.get(node)
    return is_empty_dict(node) and isinstance(parent, ast.BoolOp) and isinstance(parent.op, ast.Or)


def is_empty_dict_return(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    """Allow empty dict returns used as neutral mapping results."""
    return is_empty_dict(node) and isinstance(parents.get(node), ast.Return)


def has_allowed_dict_ancestor(
    node: ast.AST,
    parents: dict[ast.AST, ast.AST],
    allowed_cache: dict[ast.AST, bool],
) -> bool:
    """Allow nested dicts when an enclosing dict is already allowed."""
    current = parents.get(node)
    while current is not None:
        if isinstance(current, DICT_NODE_TYPES) and allowed_cache.get(current, False):
            return True
        current = parents.get(current)
    return False


def is_skipped_context(
    node: ast.Dict | ast.DictComp,
    parents: dict[ast.AST, ast.AST],
    allowed_cache: dict[ast.AST, bool],
) -> bool:
    """Allow framework metadata or standard library helper mappings."""
    if has_allowed_dict_ancestor(node, parents, allowed_cache):
        return True
    if isinstance(node, ast.DictComp):
        return True
    if is_empty_dict_accumulator(node, parents):
        return True
    if is_empty_dict_return(node, parents):
        return True
    if is_or_fallback(node, parents):
        return True
    if is_module_level_constant(node, parents):
        return True
    if is_typed_mapping_assignment(node, parents):
        return True
    if is_mapping_item_assignment(node, parents):
        return True
    if is_returned_mapping(node, parents):
        return True
    if is_optional_mapping_ifexp(node, parents):
        return True
    if is_list_comprehension_element(node, parents):
        return True
    if is_dict_call_argument(node, parents):
        return True

    current: ast.AST | None = node
    while current is not None:
        parent = parents.get(current)
        if isinstance(parent, ast.keyword) and parent.arg in SKIPPED_KEYWORDS:
            return True
        if isinstance(parent, ast.Call):
            func = parent.func
            if isinstance(func, ast.Name) and func.id in SKIPPED_CALLS:
                return True
            if isinstance(func, ast.Attribute) and func.attr in SKIPPED_CALLS:
                return True
        current = parent
    return False


def describe_node(lines: list[str], node: ast.Dict | ast.DictComp) -> str:
    """Return a concise source preview for the violation line."""
    if 0 < node.lineno <= len(lines):
        return lines[node.lineno - 1].strip()
    return "<source unavailable>"


def check_file(path: Path) -> list[str]:
    """Return all bare-dict violations found in the given Python file."""
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise RuntimeError(f"Failed to parse {path}: {exc}") from exc

    parents = build_parent_map(tree)
    allowed_cache: dict[ast.AST, bool] = {}
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, DICT_NODE_TYPES):
            continue
        allowed = is_skipped_context(node, parents, allowed_cache)
        allowed_cache[node] = allowed
        if allowed:
            continue

        start_line = node.lineno
        end_line = getattr(node, "end_lineno", node.lineno)
        if has_noqa_reason(lines, start_line, end_line):
            continue

        preview = describe_node(lines, node)
        violations.append(
            f"{path}:{start_line} bare dict literal is forbidden; "
            f"use a model or add '# {NOQA_TOKEN} <reason>'. Source: {preview}"
        )

    return violations


def main() -> int:
    files = [Path(f) for f in sys.argv[1:]]
    if not files:
        return 0

    violations: list[str] = []
    for path in files:
        try:
            violations.extend(check_file(path))
        except RuntimeError as exc:
            print(f"ERROR: {exc}")
            return 1

    if violations:
        print("Python bare dict lint failed:")
        for violation in violations:
            print(f"  - {violation}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
