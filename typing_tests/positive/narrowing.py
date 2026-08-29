"""Narrowing through the returned subject -- the differentiating claim.

The caller's variable cannot be narrowed: ``TypeIs``/``TypeGuard`` only narrow a
function's first positional argument, and ``expect()`` captures the subject inside
a wrapper. So the re-typing lands on what the chain *returns*, and the user
re-binds it.

A function that is annotated ``-> str`` and returns a narrowed subject is the
strongest form of this test: it does not compile unless the narrowing happened.
"""

from typing import assert_type

from lovely_assertions import Expect, expect


# ---------------------------------------------------------------------------
# is_not_none
# ---------------------------------------------------------------------------
def is_not_none_strips_none(
    maybe_text: str | None,
    maybe_items: list[int] | None,
    maybe_rows: dict[str, int] | None,
) -> None:
    assert_type(expect(maybe_text).is_not_none(), Expect[str])
    assert_type(expect(maybe_items).is_not_none(), Expect[list[int]])
    assert_type(expect(maybe_rows).is_not_none(), Expect[dict[str, int]])
    assert_type(expect(maybe_text).is_not_none().subject, str)


def is_not_none_keeps_the_rest_of_a_union(value: int | str | None) -> None:
    """Only ``None`` comes off; the remaining members stay.

    The two checkers disagree: pyright solves ``S`` to ``int | str``, mypy widens
    it to ``object``. pyright is the reference checker, so the API keeps the
    precise form and mypy's answer is recorded in the suppression below rather
    than designed around.
    """
    assert_type(expect(value).is_not_none().subject, int | str)  # type: ignore[assert-type]


def narrowing_satisfies_a_return_annotation(raw: str | None) -> str:
    """The load-bearing test: this only compiles if the narrowing is real."""
    return expect(raw).is_not_none().subject


def narrowing_composes(raw: str | None) -> int:
    return len(expect(raw).is_not_none().subject)


def is_not_none_on_a_non_optional_is_a_no_op(text: str) -> None:
    """Allowed, and it must not invent a different subject type."""
    assert_type(expect(text).is_not_none(), Expect[str])


# ---------------------------------------------------------------------------
# is_instance_of
# ---------------------------------------------------------------------------
def is_instance_of_narrows_to_the_asserted_type(payload: object) -> None:
    assert_type(expect(payload).is_instance_of(int).subject, int)
    assert_type(expect(payload).is_instance_of(int).which, Expect[int])


def is_instance_of_satisfies_a_return_annotation(payload: object) -> int:
    return expect(payload).is_instance_of(int).subject


def is_instance_of_narrows_a_union(value: int | str) -> str:
    return expect(value).is_instance_of(str).subject


class Account:
    __slots__ = ()


def is_instance_of_accepts_a_user_type(payload: object) -> Account:
    assert_type(expect(payload).is_instance_of(Account).subject, Account)
    return expect(payload).is_instance_of(Account).subject


# ---------------------------------------------------------------------------
# The documented limitation, asserted so it cannot regress silently
# ---------------------------------------------------------------------------
def the_original_variable_is_not_narrowed(raw: str | None) -> None:
    """``raw`` stays optional; only the returned subject is re-typed.

    A limitation the README states outright. Pinned here so that if a future
    Python ever makes the caller's own variable narrowable, this test fails and
    the promise can be widened deliberately.
    """
    expect(raw).is_not_none()
    assert_type(raw, str | None)
