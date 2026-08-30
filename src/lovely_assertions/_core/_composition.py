"""The two connectives chaining is not.

Chaining assertions is an AND, and it reads so naturally that the other two have
to be asked for by name. Both take branches rather than booleans, so a failing
branch can say *what* it expected -- which is the whole difference between "none
of the alternatives matched" and a report naming each one and what it wanted.
"""

from typing import TYPE_CHECKING, Self

from lovely_assertions._core._inspection import collect_failures
from lovely_assertions._core._rendering import render_alternative
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from collections.abc import Callable
from lovely_assertions._core._base import ExpectBase

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Guard for the composition assertions. Nothing to satisfy either passes
#: whatever the subject is or can never pass; both are bugs in the test.
_NEEDS_BRANCHES = "at least one alternative is required"


class CompositionAssertions[T](ExpectBase[T]):
    """The assertions of the ``composition`` seam."""

    __slots__ = ()

    def satisfies_any(self, *branches: "Callable[[Self], object]", because: str = "") -> Self:
        """Assert at least one branch holds.

        Chaining is an implicit AND; this and :meth:`satisfies_none` are the other
        two connectives. Each branch receives the subject itself, so it stays
        concretely typed -- a string subject autocompletes to string assertions
        inside the lambda, which a type-erased matcher object could never do.

        Branches run in order and stop at the first that holds, so a later branch
        is not evaluated once the assertion is settled. When none holds, the
        failure lists every branch's findings under its own number.

        Raises :class:`ValueError` when no branch is given: a call with nothing to
        satisfy asserts nothing at all.
        """
        if not branches:
            raise ValueError(_NEEDS_BRANCHES)
        findings: list[str] = []
        for index, branch in enumerate(branches, 1):
            collected = collect_failures(branch, self)
            if not collected:
                return self
            findings.append(render_alternative(index, collected))
        return self._fail(
            f"to satisfy at least one of {len(branches)} alternatives, but none did\n"
            + "\n".join(findings),
            because,
        )

    def satisfies_none(self, *branches: "Callable[[Self], object]", because: str = "") -> Self:
        """Assert no branch holds -- the complement of :meth:`satisfies_any`.

        Branches run in order and stop at the first that holds, which is the one
        the failure names. Raises :class:`ValueError` when no branch is given.
        """
        if not branches:
            raise ValueError(_NEEDS_BRANCHES)
        for index, branch in enumerate(branches, 1):
            if not collect_failures(branch, self):
                return self._fail(
                    f"to satisfy none of {len(branches)} alternatives,"
                    f" but alternative {index} held",
                    because,
                )
        return self
