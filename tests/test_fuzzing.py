"""The fuzz properties, run as ordinary tests.

Atheris publishes manylinux x86_64 wheels and nothing else, so the fuzzer itself
reaches one platform and one job a week. The properties it drives are plain
functions, and this is where they run everywhere else: on macOS, on Windows, on
every pull request, over a seeded corpus.

Two different jobs, deliberately. The fuzzer looks for an input nobody thought
of. This looks for a *regression* in what the fuzzer already established, at a
cost measured in milliseconds -- and it is what keeps `fuzz/properties.py` from
rotting into a file that only a weekly job would notice was broken.

A crash the fuzzer finds is reduced to a call here, pinned as a named test, and
then fixed. This file is where a found bug stays found.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Final

import pytest
from fuzz import properties

if TYPE_CHECKING:
    from collections.abc import Callable

#: Fixed, so a failure reproduces from the name of the test alone. This is a
#: regression corpus rather than a search: the searching is the fuzzer's job, and
#: a seed that moved would make this file report different things on different
#: days for reasons nobody could act on.
SEED: Final = 20260829

#: Enough to exercise every branch of the shape table in `_values`, small enough
#: that nobody notices it in the suite's runtime.
ITERATIONS: Final = 250

PROPERTIES: Final[tuple[Callable[[bytes], None], ...]] = (
    properties.equality,
    properties.strings,
    properties.hostile_rendering,
    properties.hostile_comparison,
)


def _corpus(count: int, /) -> list[bytes]:
    """A deterministic spread of lengths, including the degenerate ones."""
    rng = random.Random(SEED)  # noqa: S311  (a corpus, not a secret)
    corpus = [b"", b"\x00", b"\xff" * 64]
    corpus += [bytes(rng.randrange(256) for _ in range(rng.randrange(0, 48))) for _ in range(count)]
    return corpus


@pytest.mark.parametrize("prop", PROPERTIES, ids=lambda p: p.__name__)
def test_the_fuzz_properties_hold_over_a_seeded_corpus(prop: Callable[[bytes], None]) -> None:
    """Every promise the fuzzer drives, checked here on every platform.

    A failure names the property and the exact input, so the reduction to a
    pinned regression test is a copy and a paste.
    """
    for data in _corpus(ITERATIONS):
        try:
            prop(data)
        except AssertionError as violation:
            message = f"{prop.__name__} failed on {data!r}: {violation}"
            raise AssertionError(message) from violation


def test_every_property_is_covered_by_a_driver() -> None:
    """A property nothing drives is a property the fuzzer never explores.

    The drivers are what the weekly job runs; a property added to
    `fuzz/properties.py` and left out of them would be exercised only by the
    corpus above, which searches for nothing.
    """
    from pathlib import Path

    drivers = Path(__file__).resolve().parent.parent / "fuzz"
    driven = " ".join(
        path.read_text(encoding="utf-8") for path in sorted(drivers.glob("fuzz_*.py"))
    )

    missing = [p.__name__ for p in PROPERTIES if f"properties.{p.__name__}(" not in driven]

    assert not missing, (
        f"these properties are checked by the corpus but no fuzzer drives them: {missing}. "
        f"Add each to a driver in fuzz/, or the fuzzer will never search their input space."
    )
