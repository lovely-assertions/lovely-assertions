"""Handing the subject to a callback the caller wrote.

One that returns a verdict, one that asserts. Both exist because no catalogue
covers every question, and an escape hatch that reports badly is one people stop
using -- so a failing predicate is described by its source where it can be read,
and a failing inspector reports what it said rather than merely that it said no.
"""

from typing import TYPE_CHECKING, Self

from lovely_assertions._core._inspection import collect_failures, describe_predicate
from lovely_assertions._core._rendering import render_findings
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from collections.abc import Callable
from lovely_assertions._core._base import ExpectBase

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
from lovely_assertions._diff import render_operand

__tracebackhide__ = hide_internal_frames


class PredicateAssertions[T](ExpectBase[T]):
    """The assertions of the ``predicates`` seam."""

    __slots__ = ()

    def matches(self, predicate: "Callable[[T], bool]", /, *, because: str = "") -> Self:
        """Assert ``predicate(subject)`` is true.

        The truth of the result decides, not its type, so a predicate returning a
        non-empty container passes. The failure can say no more than that the
        predicate said no, and names it by its ``__name__`` -- a lambda has none
        worth printing and is reported as the predicate. Where the *reason*
        matters, prefer :meth:`satisfies`, whose nested assertions each explain
        themselves.
        """
        if predicate(self._subject):
            return self
        return self._fail(
            f"to match {describe_predicate(predicate)},"
            f" but {render_operand(self._subject)} did not",
            because,
        )

    def satisfies(self, inspector: "Callable[[T], object]", /, *, because: str = "") -> Self:
        """Assert the subject satisfies the nested assertions in ``inspector``.

        Failures inside ``inspector`` are collected rather than raised one at a
        time, so a single call reports everything that was wrong with the subject,
        each finding on its own line. Any other exception propagates untouched: a
        broken inspector is a bug in the test, not a finding about the subject.

        The callback must *assert*, not return a verdict. One that hands back
        ``True`` or ``False`` has asserted nothing and would pass whatever the
        subject was, so it raises :class:`TypeError` and points at :meth:`matches`
        instead.
        """
        collected = collect_failures(inspector, self._subject, "matches")
        if not collected:
            return self
        return self._fail(
            "to satisfy the inspection\n" + render_findings(collected),
            because,
        )
