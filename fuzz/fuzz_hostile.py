"""A value that misbehaves cannot turn a failure into an error.

Run with ``python -m fuzz.fuzz_hostile``. All the deciding is in
:mod:`fuzz.properties`; this file is the Atheris driver and nothing else, which
is why it is the one part of the tree the checkers are told to skip.
"""

from __future__ import annotations

import sys

import atheris

with atheris.instrument_imports():
    from fuzz import properties


def one_input(data: bytes) -> None:
    """One fuzzer iteration, over both halves of the promise.

    Rendering and comparison are separate properties because the library makes
    two different promises about them, and running both from one driver keeps
    the pair in front of whoever reads this.
    """
    properties.hostile_rendering(data)
    properties.hostile_comparison(data)


def main() -> None:
    atheris.Setup(sys.argv, one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
