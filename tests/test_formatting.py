"""Adjustable rendering limits.

``_formatting.py`` turns four constants into a scope. Four properties make that
worth having rather than merely possible, and each gets its own section here.

*It costs a passing assertion nothing.* A passing assertion reads no
``ContextVar`` and allocates nothing. Adding a second ``ContextVar`` to the
library is exactly the change that could break that, so the invariant is pinned
from both sides: the variable is booby-trapped the way
``tests/test_happy_path.py`` traps the failure machinery, and the allocation count
is measured the way ``tests/test_performance_invariants.py`` measures it.

*Nesting composes.* An inner block that raises ``max_items`` keeps the outer
block's ``max_chars``. Naming one bound is not a request to reset the others, and
that only works because a scope resolves against what is in force when it is
**entered**.

*Scoping is per context.* Same guarantee, and deliberately the same two tests, as
the soft-assertion scopes in ``tests/test_soft_assertions.py``: a scope in one
thread or one asyncio task must not reach another's messages.

*A bad limit is reported at the call.* ``max_items=0`` is a bug in the test, not a
rendering preference. It raises where the mistake is, rather than failing later
inside the report of somebody else's failure.
"""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager
from typing import Any, Final

import pytest
from benchmarks import blocks_allocated

from conftest import Detonator
from lovely_assertions import _formatting, expect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatting import FormattingOptions, _scope, current_formatting, formatting

#: The limits every message is rendered with when no scope is open. They are
#: pinned as literals rather than read back from ``_diff``/``_string``: this is
#: the contract the defaults promise, and reading a number back from the code it
#: configures would pin nothing at all.
DEFAULTS: Final = {"max_items": 10, "max_chars": 120, "max_diff_lines": 20, "max_depth": 2}

#: The three bounds that must be at least 1; ``max_depth`` is the fourth and
#: accepts 0, which is why it is not in here.
SHOWN_FIELDS: Final = ("max_items", "max_chars", "max_diff_lines")

ALL_FIELDS: Final = (*SHOWN_FIELDS, "max_depth")

#: The constructor seen through ``Any``, for the calls that are *supposed* to be
#: rejected. Suppressing the checkers instead would take one spelling for mypy and
#: another for pyright, on a line whose whole point is that both are right.
UNTYPED: Any = FormattingOptions


# ---------------------------------------------------------------------------
# The record: defaults, immutability, value semantics
# ---------------------------------------------------------------------------
def test_the_defaults_are_the_limits_the_library_already_had() -> None:
    """Making a limit adjustable must not quietly change it.

    Ten items, a hundred and twenty characters, twenty diff lines, two levels of
    nesting -- the numbers ``_diff`` and friends render with. Every pinned
    failure message in the suite depends on them.
    """
    options = FormattingOptions()
    assert {name: getattr(options, name) for name in ALL_FIELDS} == DEFAULTS


def test_every_field_is_readable() -> None:
    options = FormattingOptions(max_items=3, max_chars=40, max_diff_lines=5, max_depth=1)
    assert (options.max_items, options.max_chars) == (3, 40)
    assert (options.max_diff_lines, options.max_depth) == (5, 1)


def test_the_fields_are_keyword_only() -> None:
    """Four bare integers in a row would not read as anything in particular."""
    with pytest.raises(TypeError):
        UNTYPED(3)


def test_the_record_carries_no_instance_dictionary() -> None:
    """``__slots__``: the options are read on the failure path of every message."""
    assert not hasattr(FormattingOptions(), "__dict__")


@pytest.mark.parametrize("field", ALL_FIELDS)
def test_a_field_cannot_be_assigned(field: str) -> None:
    """The record is immutable, because the options in force are shared.

    Every context that inherits them holds the same object, so a mutable record
    would let a nested block edit what its caller sees.
    """
    options = FormattingOptions()
    with pytest.raises(AttributeError, match="immutable"):
        setattr(options, field, 5)
    assert getattr(options, field) == DEFAULTS[field]


def test_a_field_cannot_be_deleted() -> None:
    options = FormattingOptions()
    with pytest.raises(AttributeError, match="immutable"):
        del options.max_items
    assert options.max_items == 10


def test_a_refused_mutation_says_what_to_do_instead() -> None:
    options = FormattingOptions()
    with pytest.raises(AttributeError) as caught:
        options.max_items = 5
    message = str(caught.value)
    assert "cannot set max_items on FormattingOptions" in message
    assert ".replace(" in message


def test_an_unknown_attribute_is_refused_too() -> None:
    """A name the record does not have is refused by ``__setattr__``, not by ``__slots__``.

    ``__slots__`` alone would raise here too; the frozen ``__setattr__`` gets
    there first, and its message is the more useful of the two.
    """
    options = FormattingOptions()
    with pytest.raises(AttributeError, match="immutable"):
        setattr(options, "max_lines", 5)  # noqa: B010


def test_repr_names_every_field() -> None:
    assert repr(FormattingOptions(max_items=3)) == (
        "FormattingOptions(max_items=3, max_chars=120, max_diff_lines=20, max_depth=2)"
    )


def test_repr_is_the_call_that_would_rebuild_it() -> None:
    options = FormattingOptions(max_items=3, max_chars=40, max_diff_lines=5, max_depth=0)
    rebuilt: FormattingOptions = eval(repr(options))  # noqa: S307
    assert rebuilt == options


def test_two_records_with_the_same_bounds_are_equal() -> None:
    assert FormattingOptions(max_items=3) == FormattingOptions(max_items=3)
    assert FormattingOptions(max_items=3) != FormattingOptions(max_items=4)


def test_equality_declines_rather_than_denies_for_another_type() -> None:
    """``NotImplemented``, so the other operand gets its turn."""
    assert FormattingOptions().__eq__(3) is NotImplemented
    assert FormattingOptions() != 3


def test_equal_records_hash_alike() -> None:
    """An immutable value is a legal dictionary key, and two equal ones are one key."""
    assert hash(FormattingOptions(max_items=3)) == hash(FormattingOptions(max_items=3))
    assert len({FormattingOptions(), FormattingOptions()}) == 1


# ---------------------------------------------------------------------------
# replace: the modified copy
# ---------------------------------------------------------------------------
def test_replace_changes_one_bound_and_keeps_the_rest() -> None:
    derived = FormattingOptions().replace(max_items=100)
    assert derived.max_items == 100
    assert (derived.max_chars, derived.max_diff_lines, derived.max_depth) == (120, 20, 2)


def test_replace_leaves_the_original_alone() -> None:
    options = FormattingOptions()
    assert options.replace(max_items=100) is not options
    assert options.max_items == 10


def test_replace_with_nothing_named_is_an_equal_copy() -> None:
    options = FormattingOptions(max_items=3)
    assert options.replace() == options


def test_replace_composes() -> None:
    derived = FormattingOptions().replace(max_chars=500).replace(max_items=100)
    assert (derived.max_items, derived.max_chars) == (100, 500)


def test_replace_validates_what_it_is_given() -> None:
    with pytest.raises(ValueError, match="max_items must be at least 1"):
        FormattingOptions().replace(max_items=0)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("field", SHOWN_FIELDS)
@pytest.mark.parametrize("value", [0, -1])
def test_a_bound_that_shows_nothing_is_refused(field: str, value: int) -> None:
    """A bound that would show nothing is a caller's mistake, so it is raised.

    A message that reports a failure and then declines to describe it is not a
    rendering anybody asked for.
    """
    with pytest.raises(ValueError, match="must be at least 1"):
        FormattingOptions(**{field: value})


def test_max_depth_zero_is_meaningful_and_allowed() -> None:
    """``max_depth`` bounds *recursion*, not how much is shown.

    Zero says "describe this value, do not descend into it", which is a rendering
    somebody may well want on a deep structure. That is why it is the one bound
    whose floor is 0.
    """
    assert FormattingOptions(max_depth=0).max_depth == 0
    with formatting(max_depth=0) as options:
        assert options.max_depth == 0


def test_a_negative_depth_is_still_refused() -> None:
    with pytest.raises(ValueError, match="max_depth must be at least 0"):
        FormattingOptions(max_depth=-1)


@pytest.mark.parametrize("value", ["10", 2.5, None, object()])
def test_a_bound_that_is_not_an_integer_is_refused(value: object) -> None:
    """Reported here, at the boundary, rather than later.

    A float limit does not fail on the way in -- it fails inside a slice, while a
    *failing test* is being reported, turning somebody's assertion failure into a
    ``TypeError`` raised in the assertion library, a long way from the call that
    caused it.
    """
    with pytest.raises(TypeError, match="max_items must be an integer"):
        UNTYPED(max_items=value)


def test_the_message_names_the_bound_that_was_wrong() -> None:
    with pytest.raises(ValueError, match="max_diff_lines") as caught:
        FormattingOptions(max_diff_lines=0)
    assert str(caught.value) == "max_diff_lines must be at least 1, not 0"


# ---------------------------------------------------------------------------
# current_formatting
# ---------------------------------------------------------------------------
def test_outside_any_scope_the_defaults_are_in_force() -> None:
    assert current_formatting() == FormattingOptions()


def test_reading_twice_hands_back_the_same_record() -> None:
    """Reading the options hands back one shared default, not a fresh copy per read.

    That is what makes the failure-path lookup free rather than merely cheap.
    """
    assert current_formatting() is current_formatting()


# ---------------------------------------------------------------------------
# formatting: the scope
# ---------------------------------------------------------------------------
def test_a_scope_puts_its_overrides_in_force() -> None:
    with formatting(max_items=100):
        assert current_formatting().max_items == 100


def test_the_as_target_is_the_resolved_options() -> None:
    with formatting(max_items=100) as options:
        assert options is current_formatting()
        assert options.max_items == 100


def test_a_scope_leaves_the_bounds_it_did_not_name_alone() -> None:
    with formatting(max_items=100) as options:
        assert (options.max_chars, options.max_diff_lines, options.max_depth) == (120, 20, 2)


def test_leaving_a_scope_restores_what_was_in_force() -> None:
    with formatting(max_items=100):
        pass
    assert current_formatting().max_items == 10


def test_an_exception_still_restores_the_previous_options() -> None:
    with pytest.raises(ZeroDivisionError), formatting(max_items=100):
        _ = 1 / 0
    assert current_formatting().max_items == 10


def test_nesting_composes() -> None:
    """Naming one bound is not a request to reset the other three.

    The property the whole design turns on: an inner block that raises
    ``max_items`` keeps the ``max_chars`` its caller asked for.
    """
    with formatting(max_chars=500), formatting(max_items=100) as inner:
        assert (inner.max_items, inner.max_chars) == (100, 500)


def test_the_inner_scope_wins_for_the_bound_it_names() -> None:
    with formatting(max_items=50), formatting(max_items=100):
        assert current_formatting().max_items == 100


def test_leaving_an_inner_scope_returns_to_the_outer_one() -> None:
    with formatting(max_chars=500) as outer:
        with formatting(max_items=100):
            pass
        assert current_formatting() is outer


def test_sibling_scopes_do_not_leak_into_each_other() -> None:
    with formatting(max_items=100):
        pass
    with formatting(max_chars=500) as second:
        assert second.max_items == 10


def test_a_scope_resolves_where_it_is_entered_not_where_it_is_built() -> None:
    """The bounds a scope composes with are read at ``__enter__``, not at construction.

    A context manager built in a fixture has to compose with whatever scope the
    test it is handed to happens to be inside.
    """
    scope = formatting(max_items=100)
    with formatting(max_chars=500), scope as options:
        assert (options.max_items, options.max_chars) == (100, 500)


def test_a_scope_object_can_be_entered_again_afterwards() -> None:
    scope = formatting(max_items=100)
    with scope:
        assert current_formatting().max_items == 100
    with scope:
        assert current_formatting().max_items == 100
    assert current_formatting().max_items == 10


def test_re_entering_a_scope_that_is_already_active_is_refused() -> None:
    """Entering one scope object twice at once is refused rather than silently broken.

    The second entry would overwrite the token of the first, so the outer entry
    could never be undone and the scope would stay in force for the rest of the
    process. Better said out loud than left to be discovered.
    """
    scope = formatting(max_items=100)
    with pytest.raises(RuntimeError, match="already active"), scope, scope:
        pass
    assert current_formatting().max_items == 10


def test_a_scope_with_no_overrides_changes_nothing() -> None:
    """A scope that overrides nothing is allowed rather than refused.

    It is the honest result of ``formatting(max_items=configured)`` when nothing
    was configured, and a caller assembling its overrides should not have to
    guard against having none.
    """
    with formatting() as options:
        assert options == FormattingOptions()


def test_a_bad_limit_is_refused_at_the_call_not_at_the_block() -> None:
    """The mistake is at the call site, and so is the traceback."""
    with pytest.raises(ValueError, match="max_items must be at least 1"):
        formatting(max_items=0)


def test_formatting_returns_a_context_manager() -> None:
    assert isinstance(formatting(max_items=2), AbstractContextManager)


def test_the_scope_repr_is_the_call_that_built_it() -> None:
    assert repr(formatting(max_items=100, max_depth=0)) == "formatting(max_items=100, max_depth=0)"
    assert repr(formatting()) == "formatting()"


def test_exiting_a_scope_that_was_never_entered_is_harmless() -> None:
    scope = formatting(max_items=100)
    assert scope.__exit__(None, None, None) is None
    assert current_formatting().max_items == 10


# ---------------------------------------------------------------------------
# Scoping is per context
# ---------------------------------------------------------------------------
def test_scopes_are_isolated_between_threads() -> None:
    """ContextVar, not global state: one thread's rendering must not reach another's."""
    barrier = threading.Barrier(2)

    def scoped() -> int:
        with formatting(max_items=999):
            barrier.wait(timeout=5)
            return current_formatting().max_items

    def unscoped() -> int:
        barrier.wait(timeout=5)
        return current_formatting().max_items

    with ThreadPoolExecutor(max_workers=2) as pool:
        inside = pool.submit(scoped)
        outside = pool.submit(unscoped)
        assert inside.result(timeout=5) == 999
        assert outside.result(timeout=5) == 10


def test_scopes_are_isolated_between_concurrent_tasks() -> None:
    """Same guarantee under asyncio, where tasks copy the context."""

    async def scoped() -> int:
        with formatting(max_items=999):
            await asyncio.sleep(0)
            return current_formatting().max_items

    async def unscoped() -> int:
        await asyncio.sleep(0)
        return current_formatting().max_items

    async def main() -> list[int]:
        return list(await asyncio.gather(scoped(), unscoped(), scoped()))

    assert asyncio.run(main()) == [999, 10, 999]


# ---------------------------------------------------------------------------
# None of this is reachable from a passing assertion
# ---------------------------------------------------------------------------
@pytest.fixture
def no_options_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Booby-trap the options ``ContextVar`` the way ``test_happy_path`` traps ``_fail``."""
    monkeypatch.setattr(_scope, "_ACTIVE", Detonator())


@pytest.mark.usefixtures("no_options_lookup")
def test_a_passing_assertion_never_reads_the_options() -> None:
    """A passing assertion reads no ``ContextVar``.

    Adding a second one to the library is exactly the change that could break
    that. Every rendering site reads its bounds inside its failure branch, so the
    lookup sits past the ``return self`` and a passing assertion never reaches it
    at all.
    """
    expect(3).is_equal_to(3)
    expect("hello").starts_with("he")
    expect([1, 2, 3]).contains(2)
    expect({"a": 1}).contains_key("a")


@pytest.mark.usefixtures("no_options_lookup")
def test_the_trap_actually_detonates() -> None:
    """A rule nobody can fail is not a rule."""
    with pytest.raises(AssertionError, match="belongs to the failure path"):
        current_formatting()


def test_reading_the_options_allocates_nothing() -> None:
    """The failure path pays a lookup and no more, scope open or not."""
    baseline = blocks_allocated(lambda: None)
    assert blocks_allocated(current_formatting) <= baseline
    with formatting(max_items=100):
        assert blocks_allocated(current_formatting) <= baseline


def test_a_passing_assertion_allocates_nothing_inside_a_scope() -> None:
    """An open scope changes what a *failing* assertion prints, and nothing else.

    ``tests/test_performance_invariants.py`` makes this claim outside a scope;
    what it cannot see is a scope making the hot path pay for itself.
    """
    baseline = blocks_allocated(lambda: None)
    subject = expect(3)
    text = expect("hello")
    with formatting(max_items=100, max_chars=500):
        assert blocks_allocated(lambda: subject.is_equal_to(3)) <= baseline
        assert blocks_allocated(lambda: text.starts_with("he")) <= baseline


# ---------------------------------------------------------------------------
# Module conventions
# ---------------------------------------------------------------------------
def test_this_modules_frames_fold_out_of_an_assertion_traceback() -> None:
    """Every frame of ``_formatting.py`` folds out of a failing test's traceback.

    pytest reads ``__tracebackhide__`` from a frame's globals, so one
    module-level assignment covers the module -- while leaving the frames in
    place for a genuine error raised inside it.
    """
    assert _formatting.__tracebackhide__ is hide_internal_frames


def test_the_public_surface_is_the_three_documented_names() -> None:
    assert _formatting.__all__ == ["FormattingOptions", "current_formatting", "formatting"]
    assert _formatting.__all__ == sorted(_formatting.__all__)
    for name in _formatting.__all__:
        assert hasattr(_formatting, name)
