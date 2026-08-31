"""Counting, as a value an assertion is handed rather than work a test does first.

``occurrences=`` is what turns "is it in there" into "is it in there the right
number of times", and the assertions that take a constraint are spread across
the library: a substring, an item in a collection or a sequence, a value in a
mapping, a warning, a mock's calls -- the last of these taking it as the count
argument itself rather than a keyword. They all accept the same object, answering
the same two questions -- whether a count passes, and how the bound reads in a
failure -- so a count is written the same way wherever it appears and a failure
names the bound that was missed instead of printing two integers.

What leaves the package is that vocabulary and no more: :class:`Occurrence`, the
type a signature names; the factories that build the shipped bounds,
:func:`exactly`, :func:`at_least`, :func:`at_most`, :func:`more_than` and
:func:`less_than`; and :data:`once` and :data:`twice`, which are values rather
than calls, for the counts that read better as words. The classes those factories
return are deliberately not here. A signature naming one would promise which
class a factory happens to build when the promise is the two methods, and a
constructor reached directly takes a bound the factory would have refused.

Underneath, the package is layered one way, and reaches into the library only for
the traceback helper and the pluralisation a failure message borrows.
:mod:`lovely_assertions._occurrence._protocol` holds the published type by
itself; :mod:`lovely_assertions._occurrence._constraint` holds the values that
satisfy it, structurally and without importing it; and
:mod:`lovely_assertions._occurrence._factories` holds what a caller writes,
together with the refusal of a bound that could never fail or never pass.

None of the assertions that accept a constraint import any of this at runtime.
Each annotates :class:`Occurrence` under ``TYPE_CHECKING`` and then calls the two
methods on whatever it was given, so a constraint arrives already built, a
caller's own class stands on exactly the footing a shipped one does, and a
program that never writes a count never loads this package at all.
"""

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._occurrence._factories import at_least as at_least
from lovely_assertions._occurrence._factories import at_most as at_most
from lovely_assertions._occurrence._factories import exactly as exactly
from lovely_assertions._occurrence._factories import less_than as less_than
from lovely_assertions._occurrence._factories import more_than as more_than
from lovely_assertions._occurrence._factories import once as once
from lovely_assertions._occurrence._factories import twice as twice
from lovely_assertions._occurrence._protocol import Occurrence as Occurrence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = [
    "Occurrence",
    "at_least",
    "at_most",
    "exactly",
    "less_than",
    "more_than",
    "once",
    "twice",
]
