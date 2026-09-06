"""Several values in one call, and the refusal of none at all.

``contains_all()`` with no arguments is an assertion that cannot fail, which is
the one kind of test worse than a wrong one -- so it is refused where it is
written rather than passing quietly forever.

``contains_all`` is **order-blind**, which is right for what it claims and wrong
for what a reader often means. A log line asserted with
``contains_all("connecting", "ready", "authenticated")`` passes just as happily
on a transcript that authenticated before it was ready.
:meth:`MultipleContainmentAssertions.contains_in_order` is the claim that reads
the same and checks the order too.
"""

from typing import TYPE_CHECKING, Self

from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._string._render import clipped, preview
from lovely_assertions._text import holds_any, holds_every

if TYPE_CHECKING:
    from collections.abc import Sequence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Guard message for the multi-value assertions. ``contains_all()`` with nothing
#: to look for would pass whatever the subject is, and ``contains_any()`` could
#: never pass. Both are bugs in the test rather than findings about the subject,
#: so they are raised, not reported.
_NEEDS_VALUES = "at least one value to look for is required"


def _fragment_gap(subject: str, fragments: "Sequence[str]", /) -> int | None:
    """Index into ``fragments`` of the first one that breaks the ordered scan.

    ``None`` means every fragment was found in order, though not necessarily
    adjacent.

    The sequence subject answers the same question about items, and cannot answer
    it about fragments: an item consumes one *position*, while a fragment consumes
    a *span* as wide as itself. So the cursor moves past the end of what matched
    rather than one step on, which is what makes the scan **non-overlapping** --
    the rule this subject already applies to counting, and the one that makes
    ``contains_in_order("aa", "aa")`` a claim about ``"aaaa"`` rather than about
    ``"aaa"``.

    An empty fragment matches at the cursor and consumes nothing, exactly as
    ``"" in subject`` is true of every string.

    Walked with an explicit index rather than with ``enumerate`` or a ``for``,
    and the reason is the happy path: this runs on every *passing* call, where
    ``enumerate`` costs its wrapper and its iterator and a bare ``for`` still
    costs the iterator. The index is not a contortion bought with that -- this
    scan has to report *which* fragment broke the order, so it needs the number
    either way, and the loop that already holds one is the plain way to write it.
    The membership scans beside this one have no such need and stay ``for`` loops,
    at the iterator's cost.
    """
    cursor = 0
    index = 0
    total = len(fragments)
    while index < total:
        fragment = fragments[index]
        found = subject.find(fragment, cursor)
        if found < 0:
            return index
        cursor = found + len(fragment)
        index += 1
    return None


class MultipleContainmentAssertions(Expect[str]):
    """Several values at once."""

    __slots__ = ()

    def contains_all(self, *values: str, because: str = "") -> Self:
        """Assert every one of ``values`` appears in the string.

        The failure names the values that were missing rather than reporting
        only that some were. Called with no values at all this raises
        ``ValueError``: an assertion that looks for nothing would pass whatever
        the subject is, which is a bug where it was written rather than a
        finding about the subject. :meth:`contains_any` asks for one of them
        instead of all.
        """
        if not values:
            raise ValueError(_NEEDS_VALUES)
        subject = self._subject
        if holds_every(subject, values):
            return self
        missing = [value for value in values if value not in subject]
        return self._fail(
            f"to contain all of {preview(values)}, "
            f"but {clipped(subject)} is missing {preview(missing)}",
            because,
        )

    def does_not_contain_all(self, *values: str, because: str = "") -> Self:
        """Assert at least one of ``values`` is absent from the string.

        The negation of :meth:`contains_all`, so it is satisfied by one missing
        value; :meth:`does_not_contain_any` is the one that demands all of them
        be absent. Raises ``ValueError`` when called with no values, for the
        reason :meth:`contains_all` gives.
        """
        if not values:
            raise ValueError(_NEEDS_VALUES)
        subject = self._subject
        if not holds_every(subject, values):
            return self
        return self._fail(
            f"not to contain all of {preview(values)}, "
            f"but {clipped(subject)} contains every one of them",
            because,
        )

    def contains_in_order(self, *values: str, because: str = "") -> Self:
        """Assert every one of ``values`` appears, in this order, not necessarily adjacent.

        The assertion :meth:`contains_all` cannot make. Anything at all may sit
        between the fragments, and each one consumes a span of its own, so the
        scan is **non-overlapping** the way counting is (:meth:`contains`):
        ``contains_in_order("aa", "aa")`` wants four ``a`` rather than three.

        The failure tells apart the two ways it can break -- a fragment that is
        not in the string at all, and one that is there but arrives too early.
        Raises ``ValueError`` when called with no values, for the reason
        :meth:`contains_all` gives.
        """
        if not values:
            raise ValueError(_NEEDS_VALUES)
        subject = self._subject
        gap = _fragment_gap(subject, values)
        if gap is None:
            return self
        wanted = values[gap]
        if wanted not in subject:
            return self._fail(
                f"to contain {preview(values)} in order,"
                f" but {clipped(wanted)} was missing from {clipped(subject)}",
                because,
            )
        return self._fail(
            f"to contain {preview(values)} in order, but {clipped(wanted)}"
            f" did not appear after {clipped(values[gap - 1])}: {clipped(subject)}",
            because,
        )

    def does_not_contain_in_order(self, *values: str, because: str = "") -> Self:
        """Assert ``values`` do not all appear in this order.

        The negation of :meth:`contains_in_order`, so one fragment missing or one
        arriving too early is enough; it does not ask for them to be absent, which
        is :meth:`does_not_contain_any`. Raises ``ValueError`` when called with no
        values.
        """
        if not values:
            raise ValueError(_NEEDS_VALUES)
        subject = self._subject
        if _fragment_gap(subject, values) is not None:
            return self
        return self._fail(
            f"not to contain {preview(values)} in order,"
            f" but {clipped(subject)} does, in that order",
            because,
        )

    def contains_any(self, *values: str, because: str = "") -> Self:
        """Assert at least one of ``values`` appears in the string.

        :meth:`contains_all` is the one that demands every value. The failure
        reports that none of them were found, and echoes the values it looked
        for. Raises ``ValueError`` when called with no values: a choice between
        nothing could never be satisfied by any subject.
        """
        if not values:
            raise ValueError(_NEEDS_VALUES)
        subject = self._subject
        if holds_any(subject, values):
            return self
        return self._fail(
            f"to contain at least one of {preview(values)}, "
            f"but {clipped(subject)} contains none of them",
            because,
        )

    def does_not_contain_any(self, *values: str, because: str = "") -> Self:
        """Assert none of ``values`` appears in the string.

        Every one of them has to be absent, where :meth:`does_not_contain_all`
        is satisfied by a single missing value. The failure names the ones that
        were found. Raises ``ValueError`` when called with no values.
        """
        if not values:
            raise ValueError(_NEEDS_VALUES)
        subject = self._subject
        if not holds_any(subject, values):
            return self
        present = [value for value in values if value in subject]
        return self._fail(
            f"not to contain any of {preview(values)}, "
            f"but {clipped(subject)} contains {preview(present)}",
            because,
        )
