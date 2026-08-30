"""What is stored, without saying under which key.

The counted form is the one people reach for after a grouping: "three keys hold
this" is a claim about the shape of the result, not about any one entry.
"""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Self, cast

from lovely_assertions._core import Expect, Found, describe_predicate
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._mapping._previews import (
    NEEDS_VALUES,
    preview,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from lovely_assertions._occurrence import Occurrence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class ValueAssertions[K, V](Expect[Mapping[K, V]]):
    """Which values are held, and by how many keys."""

    __slots__ = ()

    def contains_value(
        self, value: V, /, *, occurrences: "Occurrence | None" = None, because: str = ""
    ) -> "Found[Self, V]":
        """Assert some key holds ``value``; continue on it with ``.which``.

        The value handed on is the one *stored*, not the one passed in. They
        compare equal, and when they are not the same object the stored one is
        the one worth asserting against.

        ``occurrences`` turns the question into **how many keys hold it**::

            expect(statuses).contains_value("failed", occurrences=at_most(2))

        Counting stops at nothing: every value is compared, by the same
        ``x is y or x == y`` this class applies everywhere (see the module
        docstring), so the count and the plain form can never disagree about
        whether the value is in there. Distinct keys holding equal values each
        count -- ``{"a": 1, "b": 1.0}`` holds ``1`` twice -- and a NaN counts the
        keys holding *that* NaN, since identity is tested first and a NaN is
        equal to nothing, itself included.

        One consequence of keeping the return type (a constraint may be satisfied
        by **no** matches at all, as ``at_most(0)`` is): there is then nothing
        stored to continue on, and ``.which`` gets the value that was passed in.
        A continuation onto a value the mapping does not hold is a strange thing
        to write, and the alternative -- a ``Found`` over a sentinel, or a second
        return type for one assertion -- would be worse than strange.
        """
        subject = self._subject
        if occurrences is None:
            for candidate in subject.values():
                if candidate is value or candidate == value:
                    return Found(self, candidate)
            return cast(
                "Found[Self, V]",
                self._fail_narrowing(
                    f"to contain value {format_value(value)}, "
                    f"but the values were {preview(subject.values())}",
                    because,
                ),
            )
        count = 0
        # Seeded with what was asked for, which is also the answer when the
        # constraint is satisfied by no match at all; the first stored match
        # replaces it. One pass, and no sentinel to cast away afterwards.
        stored = value
        for candidate in subject.values():
            if candidate is value or candidate == value:
                if count == 0:
                    stored = candidate
                count += 1
        if occurrences.allows(count):
            return Found(self, stored)
        return cast(
            "Found[Self, V]",
            self._fail_narrowing(
                f"to contain value {format_value(value)} {occurrences.describe()}, "
                f"but found {count}: {preview(subject.values())}",
                because,
            ),
        )

    def does_not_contain_value(self, value: V, /, *, because: str = "") -> Self:
        """Assert no key holds ``value``.

        Compared with ``x is y or x == y``, so a mapping is reported as holding
        *the* NaN it stores and no other one, and this can never contradict
        :meth:`contains_value`. The failure names the key that held it, which is
        the half of the entry worth reporting. :meth:`does_not_contain_values` is
        the variadic form.
        """
        for key, candidate in self._subject.items():
            if candidate is value or candidate == value:
                return self._fail(
                    f"not to contain value {format_value(value)},"
                    f" but key {format_value(key)} held it",
                    because,
                )
        return self

    def contains_values(self, *values: V, because: str = "") -> Self:
        """Assert every one of ``values`` is held by some key.

        Which key holds what is not asked, and each value is looked up on its
        own, so passing the same value twice asks one question twice rather than
        demanding two entries hold it -- ``contains_value(v, occurrences=...)``
        is where counting lives. The lookup goes through the mapping's values
        view, so the comparison is the ``x is y or x == y`` this class applies
        everywhere. Raises ``ValueError`` when called with no values.
        """
        if not values:
            raise ValueError(NEEDS_VALUES)
        present = self._subject.values()
        for value in values:
            if value not in present:
                break
        else:
            return self
        missing = [value for value in values if value not in present]
        return self._fail(
            f"to contain values {preview(values)}, but was missing {preview(missing)}; "
            f"the values were {preview(present)}",
            because,
        )

    def does_not_contain_values(self, *values: V, because: str = "") -> Self:
        """Assert none of ``values`` is held by any key.

        Every one of them has to be absent, and the failure names the ones that
        were found. Same comparison as :meth:`contains_values`, so the two can
        never disagree. Raises ``ValueError`` when called with no values.
        """
        if not values:
            raise ValueError(NEEDS_VALUES)
        present = self._subject.values()
        for value in values:
            if value in present:
                break
        else:
            return self
        found = [value for value in values if value in present]
        return self._fail(
            f"not to contain values {preview(values)}, but found {preview(found)}", because
        )

    def contains_value_matching(
        self, predicate: "Callable[[V], bool]", /, *, because: str = ""
    ) -> "Found[Self, V]":
        """Assert some key holds a value satisfying ``predicate``; continue with ``.which``.

        The first matching value in iteration order is the one handed on. A
        mapping with several matches is answering "is there one", and picking the
        first is the only answer that costs nothing.
        """
        for value in self._subject.values():
            if predicate(value):
                return Found(self, value)
        return cast(
            "Found[Self, V]",
            self._fail_narrowing(
                f"to contain a value matching {describe_predicate(predicate)}, "
                f"but the values were {preview(self._subject.values())}",
                because,
            ),
        )
