"""Presence, absence, and the exact set.

The variadic and only-these forms are separate because they fail differently: one
is about keys that should be there, the other about keys that should not.
"""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Self, cast

from lovely_assertions._core import Expect, Found, describe_predicate
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._mapping._previews import (
    NEEDS_VALUES,
    did_you_mean,
    preview,
)

if TYPE_CHECKING:
    from collections.abc import Callable

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class KeyAssertions[K, V](Expect[Mapping[K, V]]):
    """Which keys are there."""

    __slots__ = ()

    def contains_key(self, key: K, /, *, because: str = "") -> "Found[Self, V]":
        """Assert the mapping has ``key``; continue on its value with ``.whose_value``.

        On failure the message lists the keys that *are* present, and names the
        closest spelling among them when there is one -- a mistyped key is the
        common case, and the diff is the answer rather than a hint towards it.
        """
        subject = self._subject
        if key in subject:
            return Found(self, subject[key])
        return cast(
            "Found[Self, V]",
            self._fail_narrowing(
                f"to contain key {format_value(key)}{did_you_mean(key, subject)}, "
                f"but the keys were {preview(subject.keys())}",
                because,
            ),
        )

    def does_not_contain_key(self, key: K, /, *, because: str = "") -> Self:
        """Assert the mapping has no such key.

        A key mapped to ``None`` is still present and still fails this. The
        message reports the value that key held, which is usually the next thing
        wanted; :meth:`does_not_contain_entry` is the assertion for "not with
        *that* value".
        """
        subject = self._subject
        if key not in subject:
            return self
        return self._fail(
            f"not to contain key {format_value(key)}, but it held {format_value(subject[key])}",
            because,
        )

    def contains_keys(self, *keys: K, because: str = "") -> Self:
        """Assert every one of ``keys`` is present.

        Extra keys in the mapping are fine: this asks what it must have, not what
        it may not, and :meth:`contains_only_keys` is what closes the other
        direction. Repeats among ``keys`` change nothing. The failure lists the
        missing keys separately from the keys that were actually there, so the
        two do not have to be diffed by eye. Raises ``ValueError`` when called
        with no keys, since an assertion with nothing to look for cannot fail.
        """
        if not keys:
            raise ValueError(NEEDS_VALUES)
        subject = self._subject
        for key in keys:
            if key not in subject:
                break
        else:
            return self
        missing = [key for key in keys if key not in subject]
        return self._fail(
            f"to contain keys {preview(keys)}, but was missing {preview(missing)}; "
            f"the keys were {preview(subject.keys())}",
            because,
        )

    def does_not_contain_keys(self, *keys: K, because: str = "") -> Self:
        """Assert none of ``keys`` is present.

        Every one of them has to be absent -- one that is present fails the whole
        call -- and the failure names the ones that were found. Raises
        ``ValueError`` when called with no keys.
        """
        if not keys:
            raise ValueError(NEEDS_VALUES)
        subject = self._subject
        for key in keys:
            if key in subject:
                break
        else:
            return self
        present = [key for key in keys if key in subject]
        return self._fail(
            f"not to contain keys {preview(keys)}, but found {preview(present)}", because
        )

    def contains_only_keys(self, *keys: K, because: str = "") -> Self:
        """Assert the keys are exactly ``keys`` -- no more, no fewer, order ignored.

        Both directions are checked, and the failure says which one gave way:
        keys that were missing, keys that were surplus, or both. Repeats among
        ``keys`` are ignored; a mapping cannot hold a key twice, so reading them
        as a set is the only interpretation that means anything.

        A call with no keys asserts the mapping is *empty*, which is a real claim
        rather than a vacuous one -- so, unlike the other variadics here, it is
        allowed rather than rejected.
        """
        subject = self._subject
        expected = set(keys)
        if set(subject) == expected:
            return self
        missing = [key for key in keys if key not in subject]
        surplus = [key for key in subject if key not in expected]
        if not missing:
            return self._fail(
                f"to contain only the keys {preview(keys)}, but also had {preview(surplus)}",
                because,
            )
        if not surplus:
            return self._fail(
                f"to contain only the keys {preview(keys)}, but was missing {preview(missing)}",
                because,
            )
        return self._fail(
            f"to contain only the keys {preview(keys)}, but was missing {preview(missing)} "
            f"and also had {preview(surplus)}",
            because,
        )

    def contains_key_matching(
        self, predicate: "Callable[[K], bool]", /, *, because: str = ""
    ) -> "Found[Self, K]":
        """Assert some key satisfies ``predicate``; continue on that key with ``.which``.

        This is where a ``Found`` earns its place, and ``contains_key`` is where
        it would not: there the caller already holds the key they searched for,
        and what they want next is the value behind it. Here the caller does not
        know *which* key matched, so the key is the thing worth handing back.

        The **first** matching key in iteration order is the one handed on, as
        in the two forms beside it.
        """
        for key in self._subject:
            if predicate(key):
                return Found(self, key)
        return cast(
            "Found[Self, K]",
            self._fail_narrowing(
                f"to contain a key matching {describe_predicate(predicate)}, "
                f"but the keys were {preview(self._subject.keys())}",
                because,
            ),
        )
