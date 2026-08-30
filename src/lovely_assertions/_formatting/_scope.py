"""Which options are in force, and the block that changes them.

A ``ContextVar`` rather than a module global: two tests running in threads, or an
async suite interleaving coroutines, would otherwise read each other's limits and
a message would report a width nobody asked for.

Reading it costs a lookup that allocates nothing, which is exactly why it must
never happen on a passing assertion: a measurement of what an assertion allocates
cannot see a read that allocates nothing. The only thing that catches one is a
trap put on the variable itself, and the suite puts one there.
"""

from contextvars import ContextVar, Token
from typing import TYPE_CHECKING, Final, override

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatting._limits import MIN_DEPTH, MIN_SHOWN, checked_override
from lovely_assertions._formatting._options import FormattingOptions

if TYPE_CHECKING:
    from contextlib import AbstractContextManager

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


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
        max_items=checked_override("max_items", max_items, MIN_SHOWN),
        max_chars=checked_override("max_chars", max_chars, MIN_SHOWN),
        max_diff_lines=checked_override("max_diff_lines", max_diff_lines, MIN_SHOWN),
        max_depth=checked_override("max_depth", max_depth, MIN_DEPTH),
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
