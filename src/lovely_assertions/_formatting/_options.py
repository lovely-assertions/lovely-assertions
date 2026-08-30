"""The four limits as one immutable value.

A hand-written frozen record rather than a dataclass, because ``dataclasses`` is
one of the imports this package refuses to pay for at import time: the class is
built once, and writing its ``__init__``, ``__eq__`` and ``__repr__`` out costs
less than importing a module to generate them.

Immutable because the value is read from a ``ContextVar`` that several frames
share. A scope that could edit the options in place would edit them for the
frames it was nested inside, and the block a reader is looking at would not be
the block that produced their message.
"""

from typing import override

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatting._limits import (
    DEFAULT_MAX_CHARS,
    DEFAULT_MAX_DEPTH,
    DEFAULT_MAX_DIFF_LINES,
    DEFAULT_MAX_ITEMS,
    MIN_DEPTH,
    MIN_SHOWN,
    checked,
    immutable,
)

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class FormattingOptions:
    """The bounds a failure message renders within.

    An immutable record, deliberately: the options in force are shared by every
    context that inherits them, and a mutable one would let a nested block edit
    what its caller sees. :meth:`replace` derives a modified copy instead.

        >>> FormattingOptions(max_items=3).replace(max_chars=40)
        FormattingOptions(max_items=3, max_chars=40, max_diff_lines=20, max_depth=2)

    These change what a failing assertion *says*, never what an assertion
    *decides*. Raising ``max_items`` cannot turn a pass into a failure or the
    other way round; it only stops a message eliding the part the reader needed.

    Every field is validated on the way in -- ``TypeError`` for a bound that is not
    an integer, ``ValueError`` for one below its minimum, which is ``1`` for the
    three that bound how much is shown and ``0`` for ``max_depth``. So an instance
    that exists is one every rendering site can use without re-checking it.
    """

    __slots__ = ("max_chars", "max_depth", "max_diff_lines", "max_items")

    #: Items shown from one collection.
    max_items: int
    #: Characters of any one rendered value, or of one line of a unified diff.
    max_chars: int
    #: Lines of a unified diff.
    max_diff_lines: int
    #: Levels of nested structure a *difference* descends into -- the bound in
    #: ``_diff``, and not the re-entry guard in ``_formatters.py``, which
    #: bounds recursion through user code and must keep a floor of its own.
    #: ``0`` is legal here and means "do not descend"; the other three bound how
    #: much of something is shown, so they must be at least ``1``.
    max_depth: int

    def __init__(
        self,
        *,
        max_items: int = DEFAULT_MAX_ITEMS,
        max_chars: int = DEFAULT_MAX_CHARS,
        max_diff_lines: int = DEFAULT_MAX_DIFF_LINES,
        max_depth: int = DEFAULT_MAX_DEPTH,
    ) -> None:
        # Keyword-only: four bare integers in a row is a footgun, and
        # `FormattingOptions(100, 2)` would not read as anything in particular.
        # Assigned through `object` because `__setattr__` below refuses -- the
        # hand-written half of a frozen dataclass.
        object.__setattr__(self, "max_items", checked("max_items", max_items, MIN_SHOWN))
        object.__setattr__(self, "max_chars", checked("max_chars", max_chars, MIN_SHOWN))
        object.__setattr__(
            self, "max_diff_lines", checked("max_diff_lines", max_diff_lines, MIN_SHOWN)
        )
        object.__setattr__(self, "max_depth", checked("max_depth", max_depth, MIN_DEPTH))

    @override
    def __setattr__(self, name: str, _value: object, /) -> None:
        raise AttributeError(immutable("set", name))

    @override
    def __delattr__(self, name: str, /) -> None:
        raise AttributeError(immutable("delete", name))

    @override
    def __repr__(self) -> str:
        return (
            "FormattingOptions(max_items="
            + str(self.max_items)
            + ", max_chars="
            + str(self.max_chars)
            + ", max_diff_lines="
            + str(self.max_diff_lines)
            + ", max_depth="
            + str(self.max_depth)
            + ")"
        )

    @override
    def __eq__(self, other: object, /) -> bool:
        """Compare by value: two records with the same four bounds are equal.

        Returns ``NotImplemented`` for anything that is not a
        :class:`FormattingOptions`, so Python falls back to the other operand and
        then to identity. :meth:`__hash__` agrees with this, which is what lets an
        options record be a dictionary key or a set member.
        """
        if not isinstance(other, FormattingOptions):
            return NotImplemented
        return (
            self.max_items == other.max_items
            and self.max_chars == other.max_chars
            and self.max_diff_lines == other.max_diff_lines
            and self.max_depth == other.max_depth
        )

    @override
    def __hash__(self) -> int:
        return hash((self.max_items, self.max_chars, self.max_diff_lines, self.max_depth))

    def replace(
        self,
        *,
        max_items: int | None = None,
        max_chars: int | None = None,
        max_diff_lines: int | None = None,
        max_depth: int | None = None,
    ) -> "FormattingOptions":
        """Derive a copy of these options with the named bounds changed.

            >>> FormattingOptions().replace(max_items=100).max_chars
            120

        ``None`` means "leave this one alone", which is what makes the copy
        *partial*: naming one bound is not a request to reset the other three, and
        naming none of them returns an equal copy. :func:`formatting` is this
        method with a ``ContextVar`` around it.

        Validates exactly as the constructor does, so a bound that could not
        produce a message raises here rather than surfacing in a later one.

        Returns ``FormattingOptions`` rather than ``Self``: the record is a value,
        not a base class, and promising a subclass back from a constructor call
        that does not build one would be a lie the checker propagates.
        """
        return FormattingOptions(
            max_items=self.max_items if max_items is None else max_items,
            max_chars=self.max_chars if max_chars is None else max_chars,
            max_diff_lines=self.max_diff_lines if max_diff_lines is None else max_diff_lines,
            max_depth=self.max_depth if max_depth is None else max_depth,
        )
