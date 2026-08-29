"""Every marked line here must be rejected by pyright and mypy.

The positive corpus states what must hold; this one states what must *not*, and
without it the positive half proves only that the checkers ran. A harness that
cannot detect a wrong ``assert_type`` rubber-stamps every right one.

``bool`` sits under ``int`` in the type system, so the failing directions are
where this subject is actually fragile: an ``int`` must not acquire the boolean
catalogue, a ``bool | None`` must fall back to the generic subject rather than
smuggle it in, and the signatures must be exactly as narrow as advertised. Each
of those is a way the library could get *more* permissive without a single
positive assertion changing colour.
"""

from typing import assert_type

from lovely_assertions import BoolExpect, Expect, NumericExpect, expect


def dispatch_does_not_fall_through_to_int(flag: bool, number: int) -> None:
    assert_type(expect(flag), NumericExpect)  # expect-error: bool beats int in the overload order
    assert_type(expect(True), NumericExpect)  # expect-error
    assert_type(expect(flag), Expect[bool])  # expect-error: must be the specialised subject
    assert_type(expect(number), BoolExpect)  # expect-error: an int is not a bool


def the_catalogue_belongs_to_booleans_alone(number: int, text: str) -> None:
    expect(number).is_true()  # expect-error: not a boolean subject
    expect(text).is_false()  # expect-error
    expect(number).implies(True)  # expect-error


def an_optional_bool_is_not_a_bool(maybe_flag: bool | None) -> None:
    """Narrow first, then re-enter -- do not narrow *in order to* assert."""
    assert_type(expect(maybe_flag), BoolExpect)  # expect-error: a union falls back
    expect(maybe_flag).is_true()  # expect-error: the catalogue is one `is_not_none` away


def the_signatures_are_pinned(flag: bool) -> None:
    expect(flag).is_true("the feature is on")  # expect-error: because is keyword-only
    expect(flag).is_not_false(because=1)  # expect-error: because is a string
    expect(flag).implies()  # expect-error: the consequent is required
    expect(flag).implies("yes")  # expect-error: the consequent is a bool
    expect(flag).implies(True, "an admin can read")  # expect-error: because is keyword-only
    expect(flag).implies(consequent=True)  # expect-error: positional-only, so the name is ours


def the_subject_is_a_bool_all_the_way_down(flag: bool) -> None:
    """The strictness test in ``tests/test_bool.py`` needs a ``cast`` for a reason."""
    BoolExpect(1)  # expect-error: a truthy int is not a bool
    expect(flag).matches(lambda text: text.upper())  # expect-error: the predicate is handed a bool


def the_return_types_are_pinned(flag: bool) -> None:
    assert_type(expect(flag).is_true(), Expect[bool])  # expect-error: chaining keeps the subject
    assert_type(expect(flag).implies(True), NumericExpect)  # expect-error
    assert_type(expect(flag).subject, int)  # expect-error: a bool, not the int it subclasses
    assert_type(expect(flag).is_instance_of(int).which, Expect[bool])  # expect-error
