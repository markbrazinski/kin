"""Packaging smoke test — proves src/ layout resolves and Core/Integration import."""

import core  # noqa: F401
import integration  # noqa: F401


def test_packages_import() -> None:
    assert True
