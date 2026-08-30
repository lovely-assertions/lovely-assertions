"""The pair, which is the question a mapping test usually means.

``contains_entry`` says *"but that key held 'ada'"* where a key check and a value
check, written separately, would say the key is present and the value is absent
somewhere -- two true sentences that do not add up to the finding.
"""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Self, cast

from lovely_assertions._core import Expect, Found, describe_predicate
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._mapping._previews import (
    MISSING,
    NEEDS_VALUES,
    did_you_mean,
    entry_diff,
    preview,
    preview_entries,
)

if TYPE_CHECKING:
    from collections.abc import Callable

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class EntryAssertions[K, V](Expect[Mapping[K, V]]):
    """A key and its value, taken together."""

    __slots__ = ()

    def contains_entry(self, key: K, value: V, /, *, because: str = "") -> Self:
        """Assert the mapping maps ``key`` to ``value``.

        A key that is absent and a key that holds something else are different
        bugs, and the message says which one happened rather than leaving the
        reader to check.
        """
        actual = self._subject.get(key, MISSING)
        if actual is value or actual == value:
            return self
        if actual is MISSING:
            return self._fail(
                f"to contain entry {format_value(key)}: {format_value(value)},"
                f" but the key was missing"
                f"{did_you_mean(key, self._subject)}; "
                f"the keys were {preview(self._subject.keys())}",
                because,
            )
        return self._fail(
            f"to contain entry {format_value(key)}: {format_value(value)},"
            f" but that key held {format_value(actual)}",
            because,
        )

    def does_not_contain_entry(self, key: K, value: V, /, *, because: str = "") -> Self:
        """Assert the mapping does not map ``key`` to ``value``.

        A missing key satisfies this: the entry is not there either way.
        """
        actual = self._subject.get(key, MISSING)
        if actual is value or actual == value:
            return self._fail(
                f"not to contain entry {format_value(key)}: {format_value(value)},"
                f" but it was there",
                because,
            )
        return self

    def contains_entries(self, entries: Mapping[K, V], /, *, because: str = "") -> Self:
        """Assert every entry of ``entries`` is present with that exact value.

        A superset is fine -- this asks what the mapping must contain, not what it
        may not. Values are compared with ``x is y or x == y``, the rule this
        class applies everywhere, and the failure keeps the keys that were absent
        apart from the keys that held something else, because those are different
        bugs. Raises ``ValueError`` when ``entries`` is empty.
        """
        if not entries:
            raise ValueError(NEEDS_VALUES)
        subject = self._subject
        for key, value in entries.items():
            actual = subject.get(key, MISSING)
            if not (actual is value or actual == value):
                break
        else:
            return self
        return self._fail(
            f"to contain entries {preview_entries(entries)}, but {entry_diff(subject, entries)}",
            because,
        )

    def contains_entry_matching(
        self, predicate: "Callable[[K, V], bool]", /, *, because: str = ""
    ) -> "Found[Self, tuple[K, V]]":
        """Assert some entry satisfies ``predicate(key, value)``; continue with ``.which``.

        The predicate takes the key and the value as **two arguments**, not one
        pair. Three reasons, in order of weight. This class already spells an
        entry as two positional arguments -- ``contains_entry(key, value)``,
        ``does_not_contain_entry(key, value)`` -- and one concept must not read
        two ways in one catalogue. Python 3 removed tuple parameter unpacking, so
        the pair form's only spelling in a lambda is ``entry[0]`` and
        ``entry[1]``, which is precisely the unreadable test this library exists
        to replace. And a named predicate written for it, ``def is_stale(key,
        value)``, is then an ordinary two-parameter function rather than one
        contorted for the call site.

        What comes back is the whole entry, because that is what was searched
        for: ``.subject`` is the ``(key, value)`` pair, and the key half is
        usually the half worth reporting. Assert on the value with
        ``.subject[1]`` or re-enter through ``expect()``. The **first** matching
        entry in iteration order is the one handed on, as in the two forms
        beside it.
        """
        for key, value in self._subject.items():
            if predicate(key, value):
                return Found(self, (key, value))
        return cast(
            "Found[Self, tuple[K, V]]",
            self._fail_narrowing(
                f"to contain an entry matching {describe_predicate(predicate)}, "
                f"but the entries were {preview_entries(self._subject)}",
                because,
            ),
        )
