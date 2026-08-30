"""What counts as a formatter, and where a mis-built one is reported.

The protocol is two methods: one that claims a value, one that renders it. It is
structural rather than a base class, so a formatter can be any object a user
already has -- and a ``Protocol`` cannot check at registration that the two
methods are actually there, which is what the refusals below are for.

They are raised at :func:`register_formatter`, not at the first render. A
formatter is registered once, in a fixture or at import; it renders inside
somebody else's failing assertion. Reporting the mistake at the second point
means reporting it inside a message the reader is already trying to read.
"""

from typing import Protocol, runtime_checkable

from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


@runtime_checkable
class ValueFormatter(Protocol):
    """Renders a value into the text of a failure message.

    Structural, so nothing has to inherit from it: an object with these two
    methods is a formatter. ``can_handle`` decides, ``format`` renders, and
    neither is asked anything on the happy path.
    """

    __slots__ = ()

    def can_handle(self, value: object, /) -> bool:
        """Whether this formatter claims ``value``."""
        ...

    def format(self, value: object, /) -> str:
        """Render ``value`` for a failure message."""
        ...


def check(formatter: object, /) -> None:
    """Refuse an object that cannot work as a formatter.

    Takes ``object`` rather than ``ValueFormatter`` so the check means something:
    against the declared type it would be a tautology, and the callers are
    exactly where a caller's declaration might be wrong.

    ``isinstance`` against a protocol asks only whether the two *names* exist, so
    it accepts ``can_handle = True``. Callability is checked as well, because the
    consequence of letting that through is invisible: the ``TypeError`` from
    calling a bool would reach :func:`_apply`, which reads it as a decline, and
    the formatter would then silently render nothing for the life of the process.
    """
    if isinstance(formatter, ValueFormatter) and _callable_members(formatter):
        return
    message = (
        type(formatter).__name__
        + " is not a value formatter: it needs can_handle(value) and format(value)"
    )
    raise TypeError(message)


def _callable_members(formatter: object, /) -> bool:
    """Whether both formatter members are callable, not merely present."""
    return callable(getattr(formatter, "can_handle", None)) and callable(
        getattr(formatter, "format", None)
    )


def check_class(candidate: object, owner: str, /) -> None:
    """Refuse something ``isinstance`` could not use as a class.

    Same reasoning as :func:`check`, one level down. ``isinstance(value, "list")``
    raises ``TypeError``, :func:`_apply` reads that as a decline, and a formatter
    built on a string instead of a class then turns down every value there is
    without ever saying why. Worse, it is data-dependent -- ``isinstance`` walks a
    tuple left to right, so ``IterableFormatter(list, "tuple")`` works until the
    day it is handed something that is not a list. A mistake whose only symptom is
    *messages that did not change* has to be reported where it was made.
    """
    if isinstance(candidate, type):
        return
    message = owner + " needs a class to claim, not " + type(candidate).__name__
    raise TypeError(message)


def check_name(candidate: object, /) -> None:
    """Refuse an attribute name that is not a string, for the reason above."""
    if isinstance(candidate, str):
        return
    message = "ObjectFormatter needs attribute names, not " + type(candidate).__name__
    raise TypeError(message)
