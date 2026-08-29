"""Harness self-test, negative half: every marked line must be rejected.

If this file ever passes a checker, the whole typing surface is unverified --
the positive corpus would be green for the trivial reason that nothing is being
checked at all.
"""

from typing import assert_type


def identity(value: str, /) -> str:
    return value


def probe() -> None:
    assert_type(identity("x"), int)  # expect-error
    identity(1)  # expect-error
    unknown_name()  # expect-error: an undefined name proves the file is really checked


def wrong_return() -> int:
    return identity("x")  # expect-error
