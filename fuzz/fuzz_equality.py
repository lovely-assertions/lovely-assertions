"""Comparing two arbitrary values fails rather than errors.

Run with ``python -m fuzz.fuzz_equality``. All the deciding is in
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
    properties.equality(data)


def main() -> None:
    atheris.Setup(sys.argv, one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
