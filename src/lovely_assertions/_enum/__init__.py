"""Enumeration members.

**One rule: an enum member is an enum before it is anything else.** ``IntEnum``
members are integers and ``StrEnum`` members are strings, so the dispatch could
plausibly route them to :class:`~lovely_assertions.NumericExpect` and
:class:`~lovely_assertions.StringExpect` instead -- and that is the option this
package rejects. It would mean ``has_name`` and ``has_value`` were unavailable on
exactly the enums people write most, and that the subject a value gets depends on
which mixin its author chose, which is a rule nobody can hold in their head.
``is_equal_to``, ``is_in`` and ``is_one_of`` live on the generic subject and
remain available regardless; where the mixin's own catalogue is genuinely wanted,
``expect(Colour.RED.value)`` asks for it in one unambiguous move.

**Nothing here imports ``enum`` at import time.** The class is needed for typing
and never for dispatch, so it arrives under ``TYPE_CHECKING`` and importing this
package costs a program that holds no enumeration nothing. ``_subjects.py`` finds
the real type through ``sys.modules``, and so does the renderer. The one
statement that really does import it belongs to the flag guard, which cannot ask
its question without ``enum.Flag`` and pays for it once per process rather than
once per assertion: see
:func:`lovely_assertions._enum._membership.flag_is_present`.

**Names, not values, are what an alias resolves to.** With ``RED = 1`` written
first and ``CRIMSON = 1`` after it, ``Colour.CRIMSON`` *is* ``Colour.RED`` --
the alias is a second spelling of one member rather than a second member, and
the member is whichever spelling the class body reached first -- so ``.name`` is
``"RED"`` and :meth:`~EnumExpect.has_name` says so. An assertion cannot recover
which spelling the caller typed, and pretending otherwise would mean
``has_name("CRIMSON")`` passing for a member that will print itself as
``Colour.RED`` for the rest of the test.

**There is no ``is_defined``, because Python has no undefined member.**
FluentAssertions has one, and in .NET it earns its place: an enum is a struct
over an integer, ``(Colour)99`` is a legal value of type ``Colour``, and
asking whether it names a real member is a genuine question. Python has no such
value. ``Colour(99)`` raises ``ValueError`` rather than handing back an
undefined member, so by the time ``expect()`` is holding an enum member that
member is defined -- there is no subject the assertion could ever be false
about. An assertion that cannot fail is not an assertion, and one that quietly
answered a different question (does this *integer* name a member?) would be
worse than absent. Asking about the integer is
``expect([colour.value for colour in Colour]).contains(99)``, or
``pytest.raises(ValueError)`` around the call, and both say plainly which
question is being asked.

Two helpers sit under the assertions, and neither imports one.
:mod:`lovely_assertions._enum._rendering` decides how a member reaches a
sentence -- the name the reader wrote rather than the stdlib ``repr``, and a
spelling for the composite and empty flags that have no single name -- so that
one member cannot read two ways in one report.
:mod:`lovely_assertions._enum._membership` owns the one question the flag
assertions ask -- are all of the operand's bits set in the subject? -- together
with the refusals that are caller bugs rather than findings, and the cached
``enum.Flag`` that keeps a passing flag assertion to a single call. Above them
the assertions are one mixin per family of question -- names, values, flags,
none of which calls another -- assembled into the subject in
:mod:`lovely_assertions._enum._subject`.

Both exported names are the package's surface. :class:`EnumExpect` is what
``expect()`` hands back for a member; ``rendered`` is what every message in the
package is built from, and it renders whatever it is given rather than members
alone -- the operand of ``has_value`` may be any object at all -- so it is
reachable from the front door rather than through a private submodule.
"""

from lovely_assertions._enum._rendering import rendered as rendered
from lovely_assertions._enum._subject import EnumExpect as EnumExpect
from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = ["EnumExpect", "rendered"]
