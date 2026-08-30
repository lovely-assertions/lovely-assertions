"""Opening a scope, and what a failure inside one is worth on its own.

The factory is separate from the scope it builds because it is what a reader
writes, and because opening one is the only moment the decision is theirs: after
that every assertion in the block behaves differently and none of them says so.

A collected failure carries a note naming the scope it came from. One failure out
of eight, reported without that, is a sentence the reader has to go and locate.
"""

from typing import TYPE_CHECKING

from lovely_assertions._core._scope import SoftScope
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from lovely_assertions._formatters import ValueFormatter

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


def soft_assertions(
    name: str | None = None, /, *, formatters: "tuple[ValueFormatter, ...]" = ()
) -> SoftScope:
    """Open a soft-assertion scope; failures inside it aggregate instead of raising.

    On exit the scope raises a single :class:`AssertionFailure` listing every
    failure it collected. A non-assertion exception raised inside the block
    propagates untouched, carrying whatever had already failed as notes attached
    to it, and :meth:`SoftScope.discard` takes the collected messages without
    raising at all.

    ``name`` prefixes the subject name in every failure the block collects, and
    nested scopes compose their names with ``/``. A nested scope hands its
    failures up to the scope containing it, so only the outermost one raises.

    ``formatters`` scopes value formatters to the block, overriding the globally
    registered ones for as long as it runs. It is the only sanctioned way to
    change rendering per test: global registration is write-once at import,
    because assertion state that a test can mutate stops being safe the moment
    the runner goes parallel.

    A block reports everything that was wrong with the payload, not the first
    thing::

        >>> with soft_assertions("payload") as scope:
        ...     _ = expect(1).is_equal_to(2)
        ...     _ = expect(3).is_greater_than(4)
        ...     collected = scope.discard()
        >>> len(collected)
        2
    """
    return SoftScope(name, formatters=formatters)
