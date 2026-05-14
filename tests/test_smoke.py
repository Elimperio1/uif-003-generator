"""Step 1 smoke test: confirm the uif package and submodules import cleanly."""

import importlib


def test_imports():
    for name in (
        "uif",
        "uif.parse_ytd",
        "uif.parse_employees",
        "uif.match",
        "uif.generate_003",
        "uif.validate",
    ):
        importlib.import_module(name)
