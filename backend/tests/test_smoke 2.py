"""Smoke test to verify cantena package is importable."""


def test_import_cantena() -> None:
    import cantena

    assert cantena is not None


def test_cantena_has_docstring() -> None:
    import cantena

    assert cantena.__doc__ is not None
