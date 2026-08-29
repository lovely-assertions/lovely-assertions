"""How much a failure message may print, and how a block asks for more.

Every rendering in the library is bounded: a collection prints its first few
items and counts the rest, one value prints about a terminal line of characters, a
unified diff prints a screenful, and a difference descends a couple of levels into
nested structure. Those defaults are chosen for the message a reader *skims* --
the one that says at a glance which assertion went wrong -- and they are exactly
wrong for the message they are *debugging*. A four-hundred-element list that shows
the first handful is least helpful precisely when the row that matters is the four
hundredth, which is the moment the reader is looking.

So the bounds stop being constants and become a scope::

    with formatting(max_items=100):
        expect(rows).contains(missing)

Four rules shape everything here.

**Nothing here runs for a passing assertion.** :func:`current_formatting` is read
from a failure branch and from nowhere else, so an open scope changes what a
*failing* assertion prints and costs a passing one nothing at all -- no
``ContextVar`` read, no allocation.

**Scoping is per context, not per process.** The options in force live in a
``ContextVar``, for the reason every other piece of scoped state in the package is
one: one thread's or one asyncio task's rendering must never reach another's
messages, or a parallel run turns a fixed message into a flaky one. It is also why
there is no global setter here -- shared assertion state that each test mutates
stops being safe the moment the suite runs in parallel.

**Nesting composes.** A scope resolves against whatever is in force when it is
*entered*, so an inner block that raises ``max_items`` alone keeps the outer
block's ``max_chars``. Asking for one bound is not a request to reset the others.

**A limit is a caller's decision, and a bad one is reported.** ``max_items=0``
would announce a failure and then decline to say anything about it. That is a bug
in the test, not a rendering preference, so it raises instead of quietly doing
nothing.

Two house rules show up in the shape of the code. :class:`FormattingOptions` would
obviously be a frozen dataclass, but importing this package must not drag in
``dataclasses`` -- so ``__setattr__``, ``__delattr__``, ``__eq__``, ``__hash__``
and ``__repr__`` are written out by hand. And f-strings are confined to arguments
of ``_fail``, the one call reached only once a failure is certain; nothing here
calls it, so every message here is concatenated instead (``_formatters.py`` and
``_diff.py`` do the same).
"""

from contextvars import ContextVar
from typing import TYPE_CHECKING, Final, override

from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from contextlib import AbstractContextManager
    from contextvars import Token

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = ["FormattingOptions", "current_formatting", "formatting"]

#: Items shown from one collection before a rendering says how many it left out.
#: Few enough to read as a clause taken in at a glance; past that the message is
#: skimmed rather than read.
_DEFAULT_MAX_ITEMS: Final = 10

#: Characters of any one rendered value, or of one line of a unified diff. About a
#: line of a modern terminal.
_DEFAULT_MAX_CHARS: Final = 120

#: Lines of unified diff before it is truncated. Larger than the item bound
#: because a diff is read as a block rather than as a clause inside a sentence,
#: and small enough that the block still sits next to the failing test instead of
#: scrolling it off the screen.
_DEFAULT_MAX_DIFF_LINES: Final = 20

#: Levels of nested structure a *difference* descends into -- the value under a
#: key, and the value under a key of that. It is the bound in ``_diff.py``, not
#: the separate re-entry guard in ``_formatters.py``: that one bounds recursion
#: through user code and is a safety limit rather than a legibility one.
_DEFAULT_MAX_DEPTH: Final = 2

#: The smallest ``max_depth`` worth accepting. Zero is meaningful and occasionally
#: what somebody wants: describe this value, do not descend into it. The other
#: three bound how much of *something* is shown, so zero there is a message that
#: reports a failure and then says nothing about it.
_MIN_DEPTH: Final = 0

#: The smallest value the three "how much is shown" bounds accept.
_MIN_SHOWN: Final = 1


def _checked(name: str, value: object, minimum: int, /) -> int:
    """Validate one limit, or say which one was wrong and why.

    Takes ``object`` rather than ``int`` so the check means something: against the
    declared type it would be a tautology, and this is the boundary where a
    caller's declaration might be wrong (``_formatters._check_class`` takes the
    same line for the same reason).

    The type check earns its place. A limit that is not an integer does not fail
    here -- it fails later, inside a slice, while a *failing test* is being
    reported, turning somebody's assertion failure into a ``TypeError`` raised in
    the assertion library. That is the worst outcome available, and it is a long
    way from the call that caused it.
    """
    if not isinstance(value, int):
        message = name + " must be an integer, not " + type(value).__name__
        raise TypeError(message)
    if value < minimum:
        message = name + " must be at least " + str(minimum) + ", not " + str(value)
        raise ValueError(message)
    return value


def _override(name: str, value: object, minimum: int, /) -> int | None:
    """:func:`_checked` for an override, where ``None`` means "leave this one alone"."""
    if value is None:
        return None
    return _checked(name, value, minimum)


def _immutable(action: str, name: str, /) -> str:
    """The message behind a refused mutation."""
    return (
        "cannot "
        + action
        + " "
        + name
        + " on FormattingOptions: it is immutable."
        + " Derive a modified copy with .replace(...) instead."
    )


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
    #: ``_diff.py``, and not the re-entry guard in ``_formatters.py``, which
    #: bounds recursion through user code and must keep a floor of its own.
    #: ``0`` is legal here and means "do not descend"; the other three bound how
    #: much of something is shown, so they must be at least ``1``.
    max_depth: int

    def __init__(
        self,
        *,
        max_items: int = _DEFAULT_MAX_ITEMS,
        max_chars: int = _DEFAULT_MAX_CHARS,
        max_diff_lines: int = _DEFAULT_MAX_DIFF_LINES,
        max_depth: int = _DEFAULT_MAX_DEPTH,
    ) -> None:
        # Keyword-only: four bare integers in a row is a footgun, and
        # `FormattingOptions(100, 2)` would not read as anything in particular.
        # Assigned through `object` because `__setattr__` below refuses -- the
        # hand-written half of a frozen dataclass.
        object.__setattr__(self, "max_items", _checked("max_items", max_items, _MIN_SHOWN))
        object.__setattr__(self, "max_chars", _checked("max_chars", max_chars, _MIN_SHOWN))
        object.__setattr__(
            self, "max_diff_lines", _checked("max_diff_lines", max_diff_lines, _MIN_SHOWN)
        )
        object.__setattr__(self, "max_depth", _checked("max_depth", max_depth, _MIN_DEPTH))

    @override
    def __setattr__(self, name: str, _value: object, /) -> None:
        raise AttributeError(_immutable("set", name))

    @override
    def __delattr__(self, name: str, /) -> None:
        raise AttributeError(_immutable("delete", name))

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


#: The options every message renders within until a scope says otherwise. One
#: shared instance rather than a fresh one per read: it is immutable, so sharing
#: it across threads shares nothing that can change.
_DEFAULTS: Final = FormattingOptions()

#: The options in force on this thread or task. A ``ContextVar`` because scoped
#: state has to be isolated per thread and per asyncio task, or a parallel run
#: leaks one test's rendering into another test's message. Read on the failure
#: path only.
_ACTIVE: ContextVar[FormattingOptions] = ContextVar(
    "lovely_assertions.formatting_options", default=_DEFAULTS
)


def current_formatting() -> FormattingOptions:
    """Return the bounds a failure message currently renders within.

        >>> current_formatting().max_items
        10

    **Failure path only.** Every rendering site reads its bounds from here, inside
    its failure branch. A passing assertion must never reach this function: it
    reads a ``ContextVar``, and a passing assertion is meant to read none. It
    allocates nothing, so the failure path pays a lookup and no more.

    Outside any :func:`formatting` block it returns the shared default record,
    which is why the call is free rather than merely cheap. The result is
    immutable and is a snapshot: it does not track a scope entered afterwards, so
    read it again rather than holding on to one.
    """
    return _ACTIVE.get()


def formatting(
    *,
    max_items: int | None = None,
    max_chars: int | None = None,
    max_diff_lines: int | None = None,
    max_depth: int | None = None,
) -> "AbstractContextManager[FormattingOptions]":
    """Scope different rendering bounds to a block.

        >>> with formatting(max_items=100) as options:
        ...     options.max_items
        100

    Exactly the assertions that were failing before still fail, and they say more
    about it. ``None`` leaves a bound alone, so::

        with formatting(max_chars=500):
            with formatting(max_items=100):
                ...  # max_items=100 *and* max_chars=500

    The block resolves against whatever is in force when it is **entered**, not
    when it is called, so a context manager built in a fixture composes with
    whatever scope the test happens to be inside.

    A limit that could not produce a message is refused here, at the call, where
    the mistake is -- not later, in the middle of reporting somebody's failure:
    ``TypeError`` for a bound that is not an integer, ``ValueError`` for one below
    its minimum. A call with no overrides at all is allowed: it is a scope that
    changes nothing, which is the honest result of
    ``formatting(max_items=configured)`` when nothing was configured.

    The context manager yields the resolved :class:`FormattingOptions`, and
    restores whatever was in force before on the way out of the block, exception
    or no exception. One object holds one reset token, so entering the same one
    again without leaving it raises ``RuntimeError``; call :func:`formatting`
    again for a nested scope.
    """
    return _FormattingScope(
        max_items=_override("max_items", max_items, _MIN_SHOWN),
        max_chars=_override("max_chars", max_chars, _MIN_SHOWN),
        max_diff_lines=_override("max_diff_lines", max_diff_lines, _MIN_SHOWN),
        max_depth=_override("max_depth", max_depth, _MIN_DEPTH),
    )


class _FormattingScope:
    """The context manager :func:`formatting` returns.

    Holds the *overrides* rather than resolved options, because the base they
    apply to is not known until the block is entered -- that is what makes nesting
    compose. Written out rather than spelled with ``@contextmanager`` so that
    ``contextlib`` stays out of the import graph and the failure-path read stays
    an attribute lookup on a plain object.
    """

    __slots__ = ("_max_chars", "_max_depth", "_max_diff_lines", "_max_items", "_token")

    def __init__(
        self,
        *,
        max_items: int | None,
        max_chars: int | None,
        max_diff_lines: int | None,
        max_depth: int | None,
    ) -> None:
        self._max_items: int | None = max_items
        self._max_chars: int | None = max_chars
        self._max_diff_lines: int | None = max_diff_lines
        self._max_depth: int | None = max_depth
        self._token: Token[FormattingOptions] | None = None

    @override
    def __repr__(self) -> str:
        """Show the call that built this scope, not the options it will resolve to.

        Resolved options would be a guess: the base they apply to is whatever is
        in force at ``__enter__``, which has not happened yet.
        """
        named = [
            name + "=" + str(value)
            for name, value in (
                ("max_items", self._max_items),
                ("max_chars", self._max_chars),
                ("max_diff_lines", self._max_diff_lines),
                ("max_depth", self._max_depth),
            )
            if value is not None
        ]
        return "formatting(" + ", ".join(named) + ")"

    def _resolved(self, base: FormattingOptions, /) -> FormattingOptions:
        return base.replace(
            max_items=self._max_items,
            max_chars=self._max_chars,
            max_diff_lines=self._max_diff_lines,
            max_depth=self._max_depth,
        )

    def __enter__(self) -> FormattingOptions:
        if self._token is not None:
            message = (
                "this formatting scope is already active;"
                " call formatting(...) again for a nested one"
            )
            raise RuntimeError(message)
        options = self._resolved(_ACTIVE.get())
        self._token = _ACTIVE.set(options)
        return options

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _traceback: object,
        /,
    ) -> None:
        token = self._token
        if token is None:
            return
        # Cleared so the same object can be entered again later, rather than
        # resetting a spent token -- ``SoftScope`` does the same with its own.
        self._token = None
        _ACTIVE.reset(token)
