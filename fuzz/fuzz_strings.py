"""The string catalogue survives arbitrary text at any width.

Run with ``python -m fuzz.fuzz_strings``. All the deciding is in
:mod:`fuzz.properties`; this file is the Atheris driver and nothing else, which
is why it is the one part of the tree the checkers are told to skip.
"""

from __future__ import annotations

import sys

import atheris

with atheris.instrument_imports():
    from fuzz import properties


def one_input(data: bytes) -> None:
    """One fuzzer iteration."""
    properties.strings(data)


def main() -> None:
    atheris.Setup(sys.argv, one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
