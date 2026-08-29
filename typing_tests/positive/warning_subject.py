"""The warning surface: ``WarnedExpect``, ``expect_warns``, ``warns``, ``does_not_warn``.

Four claims are pinned here.

*The category asked for is the category handed back.* ``warns`` narrows through
what it returns, so ``.where(...)`` receives the warning class the caller named
and a field it carries is checked rather than guessed.

*The subject is a tuple of them.* A call raises at most one exception and may
issue any number of warnings, so ``.subject`` is ``tuple[W, ...]`` -- which is
also what makes the generic catalogue apply to it as a whole.

*The continuations keep the type.* ``.and_`` and ``.which`` are both ``Self``, and
every assertion returns the subject it was called on, a user's own subclass
included.

*The context-manager form types its ``as`` binding.* ``expect_warns`` is declared
as a context manager over ``WarnedExpect[W]``; the handle's own class never
appears in a user's inferred types.

**Named** ``warning_subject.py``, **not** ``warnings.py``, and the reason is not
cosmetic. This directory is deliberately not a package, so both checkers compile
each file here as a *top-level module of its own basename*. A file called
``warnings.py`` therefore becomes the module ``warnings`` on the search path, and
every ``import warnings`` in the repository resolves to this file instead of to
the standard library -- a flood of errors in unrelated files under both checkers,
all of them variations on ``Module has no attribute "catch_warnings"``. The
``_subject`` suffix is the convention the neighbours here already use
(``bool_subject.py``, ``enum_subject.py``, ``type_subject.py``), so nothing new
is being invented to dodge it.

``typing_tests/positive/string.py`` is the same landmine, unexploded: nothing in
the checked corpus imports ``string``.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import assert_type

from lovely_assertions import Expect, exactly
from lovely_assertions._callable import CallableExpect
from lovely_assertions._warnings import WarnedExpect, expect_warns


class Removed(DeprecationWarning):
    """A warning carrying a field, which is the whole point of narrowing to it."""

    version: str


def legacy() -> None:
    """A call that warns, as far as the type checker is concerned."""


# ---------------------------------------------------------------------------
# warns: the requested category is the new subject
# ---------------------------------------------------------------------------
def warns_narrows_to_the_requested_category() -> None:
    warned = CallableExpect(legacy).warns(DeprecationWarning)
    assert_type(warned, WarnedExpect[DeprecationWarning])
    assert_type(warned.subject, tuple[DeprecationWarning, ...])


def a_subclass_is_a_legitimate_request() -> None:
    assert_type(CallableExpect(legacy).warns(Removed), WarnedExpect[Removed])
    assert_type(CallableExpect(legacy).warns(Removed).subject[0].version, str)


def the_bare_category_is_the_any_warning_spelling() -> None:
    assert_type(CallableExpect(legacy).warns(Warning), WarnedExpect[Warning])


def occurrences_is_keyword_only_and_optional() -> None:
    assert_type(
        CallableExpect(legacy).warns(UserWarning, occurrences=exactly(2)),
        WarnedExpect[UserWarning],
    )
    assert_type(
        CallableExpect(legacy).warns(UserWarning, occurrences=None, because="D10"),
        WarnedExpect[UserWarning],
    )


def does_not_warn_returns_the_callable_subject() -> None:
    assert_type(CallableExpect(legacy).does_not_warn(), CallableExpect)
    assert_type(CallableExpect(legacy).does_not_warn(UserWarning), CallableExpect)
    assert_type(CallableExpect(legacy).subject, Callable[..., object])


# ---------------------------------------------------------------------------
# The subject's own assertions
# ---------------------------------------------------------------------------
def every_assertion_returns_the_same_subject(warned: WarnedExpect[Removed]) -> None:
    assert_type(warned.with_message("gone"), WarnedExpect[Removed])
    assert_type(warned.with_message_containing("gone"), WarnedExpect[Removed])
    assert_type(warned.where(lambda warning: warning.version == "3.0"), WarnedExpect[Removed])
    assert_type(warned.and_, WarnedExpect[Removed])
    assert_type(warned.which, WarnedExpect[Removed])


def the_predicate_receives_one_warning_and_the_matcher_the_tuple(
    warned: WarnedExpect[Removed],
) -> None:
    """``where`` is per-warning; ``matches`` is the whole capture. Both are typed."""
    warned.where(lambda warning: warning.version.startswith("3"))
    warned.matches(lambda captured: len(captured) == 2)


def the_generic_catalogue_applies_to_the_tuple(warned: WarnedExpect[UserWarning]) -> None:
    assert_type(warned.is_not_none(), Expect[tuple[UserWarning, ...]])
    assert_type(warned.subject, tuple[UserWarning, ...])


def a_user_subclass_keeps_its_own_type() -> None:
    """An extension subject must not be downgraded to the base by an inherited assertion."""

    class Mine(WarnedExpect[UserWarning]):
        __slots__ = ()

        def is_mine(self) -> "Mine":
            return self

    mine = Mine(())
    assert_type(mine.with_message("x"), Mine)
    assert_type(mine.with_message("x").is_mine(), Mine)
    assert_type(mine.where(lambda warning: bool(warning.args)).and_.is_mine(), Mine)


# ---------------------------------------------------------------------------
# The context-manager form
# ---------------------------------------------------------------------------
def expect_warns_is_a_context_manager_over_the_subject() -> None:
    manager = expect_warns(Removed)
    assert_type(manager, AbstractContextManager[WarnedExpect[Removed]])


def the_binding_carries_the_category_through_the_block() -> None:
    with expect_warns(Removed) as warned:
        legacy()
    assert_type(warned, WarnedExpect[Removed])
    assert_type(warned.subject, tuple[Removed, ...])
    assert_type(warned.subject[0].version, str)


def the_block_takes_occurrences_and_a_reason() -> None:
    with expect_warns(UserWarning, occurrences=exactly(2), because="D10") as warned:
        legacy()
    assert_type(warned, WarnedExpect[UserWarning])
