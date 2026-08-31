"""The three type names a class statement needs without importing ``datetime``.

A base and a type-parameter bound are evaluated when the class is created, so
neither can be a name only a checker can see. A string is not free either: on
CPython 3.14 subscripting a generic with one builds a ``ForwardRef``, and
building one imports ``annotationlib``, which pulls in ``ast`` and ``enum``.

A PEP 695 alias is lazily evaluated in the one way that matters here -- the
object exists without its right-hand side being resolved -- so it can name a type
this library refuses to import while a checker still sees straight through it.
"""

from typing import TYPE_CHECKING

from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from datetime import datetime, time, timedelta

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: The value types again, this time as PEP 695 aliases, for the four class
#: statements below whose *base* names one of them.
#:
#: A base is evaluated when the class is created, so it cannot be a name only
#: the checkers can see. A string is the obvious escape and it is not free: on
#: CPython 3.14, subscripting a generic with a string builds a ``ForwardRef``,
#: and building one imports ``annotationlib``, which pulls in ``ast`` and
#: ``enum`` -- three modules that would then load for every program that merely
#: says ``import lovely_assertions``, and invisible on 3.13 where a
#: ``ForwardRef`` costs nothing.
#:
#: A PEP 695 alias is lazily evaluated in the one way that matters here: the
#: object exists without its right-hand side being resolved, so the alias can
#: name a type from a module this library refuses to import, and a checker still
#: reads through it to ``DateExpect[datetime]``. A bound -- ``[T: "date"]`` -- is
#: lazy already and stays a string; only a base needs this.
type DateTimeValue = datetime


type TimeValue = time


type TimeDeltaValue = timedelta
