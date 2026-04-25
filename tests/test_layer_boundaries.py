"""Architecture invariant: src/core/*.py imports nothing from integration or ui."""

import ast
from pathlib import Path

import pytest

FORBIDDEN_ROOTS = ("integration", "ui", "src.integration", "src.ui")
CORE_DIR = Path(__file__).parent.parent / "src" / "core"


def _matches_forbidden(name: str) -> bool:
    return any(name == root or name.startswith(root + ".") for root in FORBIDDEN_ROOTS)


def _forbidden_imports(source: str, filename: str) -> list[tuple[int, str]]:
    """Return (lineno, imported_name) for every forbidden import in source."""
    tree = ast.parse(source, filename=filename)
    violations: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _matches_forbidden(alias.name):
                    violations.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if _matches_forbidden(mod):
                violations.append((node.lineno, mod))
    return violations


def test_core_imports_nothing_from_integration_or_ui() -> None:
    """Scan every .py under src/core/ and fail with a clear message if
    any file imports from integration or ui. Passes trivially today —
    Core is docstring-only stubs — and gains teeth as Core fills in.
    """
    failures: list[str] = []
    for path in sorted(CORE_DIR.rglob("*.py")):
        source = path.read_text()
        for lineno, name in _forbidden_imports(source, str(path)):
            failures.append(f"{path}:{lineno}: forbidden import '{name}'")
    assert not failures, "Core layer violations:\n" + "\n".join(failures)


@pytest.mark.parametrize(
    "bad_source,expected",
    [
        ("import integration\n", "integration"),
        (
            "from integration.ollama_adapter import X\n",
            "integration.ollama_adapter",
        ),
        ("from src.ui.server import app\n", "src.ui.server"),
        ("import ui.foo\n", "ui.foo"),
    ],
)
def test_scanner_detects_known_violations(bad_source: str, expected: str) -> None:
    """Scanner must reject forbidden imports, not just pass trivially.
    Without this, an empty Core could silently mask a broken scanner.
    """
    violations = _forbidden_imports(bad_source, "synthetic.py")
    assert any(name == expected for _, name in violations), (
        f"scanner failed to flag '{expected}' in:\n{bad_source}"
    )


@pytest.mark.parametrize(
    "benign_source",
    [
        "import integrationx\n",
        "from uikit import Button\n",
        "import integration_helper\n",
    ],
)
def test_scanner_ignores_falsely_similar_names(benign_source: str) -> None:
    """Guard against the naive `startswith(tuple)` form that would
    false-positive on modules like `integrationx` or `uikit`.
    """
    violations = _forbidden_imports(benign_source, "synthetic.py")
    assert violations == [], (
        f"scanner wrongly flagged benign import in:\n{benign_source}"
    )
