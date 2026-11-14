"""Pure-unit: no module in api/ defines the same top-level name twice.

Python keeps the last `def` of a name. When two functions share a name,
the first one is lost at import time, and its callers reach the second
one. On 2026-11-14 this was the cause of HTTP 500 on
/scope/averages/fielding/by-season: `_fielding_by_season_live` was
defined twice in api/routers/scope_averages.py, and the endpoint called
the second one with the arguments of the first.

The test parses each module with `ast` (nothing is imported, no DB) and
reports every top-level function or class name that is defined more
than once.

ALLOWED lists the known duplicates whose copies have the same body, so
that keeping the last one changes nothing. Remove an entry when the
extra copy is deleted. Never add a duplicate whose copies differ.

Usage:
  uv run python tests/sanity/test_no_duplicate_defs.py

Exits 0 on all-pass, 1 on any failure.
"""

from __future__ import annotations

import ast
import collections
import pathlib
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]

# (module path relative to the project, name): the copies are identical.
ALLOWED = {
    ("api/routers/bowling.py", "_format_overs"),
}


def _body(node: ast.AST) -> str:
    """The node's code without its docstring, for comparing copies."""
    body = list(node.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        body = body[1:]
    head = [getattr(node, k, None) for k in ("args", "returns", "bases", "keywords")]
    head += list(node.decorator_list)
    return "".join(ast.dump(h) if isinstance(h, ast.AST) else repr(h) for h in head) \
        + "".join(ast.dump(s) for s in body)


def self_test() -> bool:
    """`_body` ignores a docstring, and counts a decorator and a return type."""
    src = (
        'def f(x):\n    "doc"\n    return x\n'
        "def g(x):\n    return x\n"
        "@deco\ndef h(x):\n    return x\n"
        "def k(x) -> int:\n    return x\n"
    )
    f, g, h, k = ast.parse(src).body
    ok = _body(f) == _body(g) and _body(f) != _body(h) and _body(f) != _body(k)
    print(f"  [{'PASS' if ok else 'FAIL'}] identical-copy check: docstring ignored; decorator and return type count")
    return ok


def duplicates(root: pathlib.Path) -> dict[tuple[str, str], list[ast.AST]]:
    """Map (module, name) to its nodes, for each name defined twice or more."""
    out = {}
    for path in sorted((root / "api").rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        seen: dict[str, list[ast.AST]] = collections.defaultdict(list)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                seen[node.name].append(node)
        rel = path.relative_to(root).as_posix()
        for name, nodes in seen.items():
            if len(nodes) > 1:
                out[(rel, name)] = nodes
    return out


def main() -> int:
    print("Sanity: no duplicate top-level definitions in api/")
    dups = duplicates(PROJECT_ROOT)
    ok_all = self_test()
    for key, nodes in sorted(dups.items()):
        lines = [n.lineno for n in nodes]
        same = len({_body(n) for n in nodes}) == 1
        if key in ALLOWED and same:
            print(f"  [PASS] {key[0]}: {key[1]} at lines {lines} (allowed; copies identical)")
            continue
        why = "allowed, but the copies now differ" if key in ALLOWED else "the later one replaces the earlier"
        print(f"  [FAIL] {key[0]}: {key[1]} defined at lines {lines} ({why})")
        ok_all = False
    for key in sorted(ALLOWED - set(dups)):
        print(f"  [FAIL] ALLOWED entry {key} is no longer a duplicate; remove it")
        ok_all = False
    if ok_all and not dups:
        print("  [PASS] no duplicates")
    print("\nALL PASS" if ok_all else "\nFAILURES")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
