"""Assertions about a class itself, rather than about one of its instances.

``expect(SomeClass)`` lands here, and the questions are the ones a class can
answer about its own declaration: what it derives from, which names it defines
and how, what it leaves abstract, and which protocols it satisfies. A class is
also a callable, so the subject inherits the callable catalogue whole --
:class:`TypeExpect` argues why that inheritance is the right shape rather than a
convenience.

Four rules run through the package.

**A "no" is never the whole finding.** ``issubclass`` answers ``False``, a name
is absent, a member turns out not to be callable -- and each of those facts on
its own leaves the reader to go and look at the class. So every failure here
carries what was actually there: the classes the subject does inherit from, the
way it really declares the name that was meant to be a method, the protocol
members it does not define -- or, for a negated assertion, the members it turned
out to provide and the reason ``issubclass`` said yes when nothing was inherited
at all. That is what the helper modules exist for.

**A protocol that cannot be checked at runtime is a bug in the test, not a
finding about the class.** ``issubclass`` refuses a protocol that is not
``@runtime_checkable``, and refuses a *data* protocol -- one with non-method
members -- even when it is. Neither refusal establishes anything about the
subject, so neither is reported through ``_fail``: both become a ``TypeError``
raised where the call was written, naming the actual problem and the fix. An
``AssertionFailure`` there would read as a genuine finding, and inside a soft
scope it would be collected as one, when nothing was ever checked.

**Nothing here trusts the subject to be a class.** Dispatch routes only classes
to this subject and a hand-built one is not turned away at the door, so every
attribute a message needs -- ``__name__``, ``__mro__``, ``__abstractmethods__``
-- is read with ``getattr`` and checked against the type it is supposed to have.
A message that raised while explaining a failure would replace the finding with
a traceback about this library.

**Rendering is failure-path work, and only that.** The bounds a message obeys
are read from the formatting scope in force at the moment it is built rather
than frozen into constants, which a passing assertion can afford because it
never reaches them. The helpers concatenate rather than interpolate for the same
reason: an f-string is a message, a message belongs inside a ``_fail`` call, and
one built anywhere else is one an assertion paid for without failing.

Underneath the assertions sit four helper modules, layered one way and importing
no assertion. :mod:`lovely_assertions._type._naming` renders a class's name and
a run of names within those bounds; :mod:`lovely_assertions._type._hierarchy`
reads the MRO, for what a class inherits from and for why ``issubclass`` said
yes; :mod:`lovely_assertions._type._members` recovers the undecorated
declaration from the class dictionaries, where a ``property``, a ``staticmethod``
and a ``classmethod`` are still what the reader wrote rather than what the
descriptor protocol hands back; and
:mod:`lovely_assertions._type._protocols` owns the runtime check together with
the two refusals above. Above them the assertions are one mixin per family of
question, none of which calls another, assembled into the subject in
:mod:`lovely_assertions._type._subject`.
"""

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._type._subject import TypeExpect as TypeExpect

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = ["TypeExpect"]
