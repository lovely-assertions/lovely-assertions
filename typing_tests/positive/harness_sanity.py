"""Harness self-test, positive half: this file must be clean under both checkers.

It deliberately uses nothing from ``lovely_assertions``. Its job is to prove the
typing harness is wired up -- toolchain, config, paths -- before any of the
library's own typing tests rely on it.
"""

from typing import assert_type


def identity(value: str, /) -> str:
    return value


def probe() -> None:
    assert_type(identity("x"), str)
    assert_type(len("x"), int)
