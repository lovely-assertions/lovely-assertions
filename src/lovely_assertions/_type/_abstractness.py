"""What a class has left unimplemented.

Both directions ask one attribute, ``__abstractmethods__``, and nothing else --
neither the MRO the inheritance family walks nor the class dictionaries the
attribute family opens. The reading of it lives with the protocol helpers, which
ask it of the *other* class rather than of the subject: an abstract base class's
unimplemented names are the list a conformance failure measures a candidate
against.

The seam stops deliberately short of "can this be constructed". Instantiability
is settled by ``__new__``, ``__init__`` and the metaclass at the moment of the
call, so the only way to learn it is to make the call, and nothing here makes it.
The two answers come apart in practice: a ``Protocol`` refuses construction while
leaving nothing unimplemented, and so does any class whose ``__init__`` turns
callers away. A test that means "this cannot be built" wants ``raises``,
inherited here from the callable catalogue, which does make the call.
"""

from typing import Self

from lovely_assertions._callable import CallableExpect
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._type._naming import listed
from lovely_assertions._type._protocols import abstract_methods

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class AbstractnessAssertions(CallableExpect):
    """What is still missing -- not whether the class can be built."""

    __slots__ = ()

    # -- abstractness ------------------------------------------------------
    def is_abstract(self, *, because: str = "") -> Self:
        """Assert the class leaves at least one abstract method unimplemented.

        "Abstract" means ``__abstractmethods__`` is not empty -- the attribute
        ``ABCMeta`` populates and CPython refuses to instantiate a class over --
        rather than "declared with ``ABCMeta``". ``class Base(ABC): pass``
        declares no abstract method, constructs perfectly well, and fails this.

        It is not a claim about instantiability, which nothing measures
        cheaply: a ``Protocol`` cannot be constructed and leaves nothing
        unimplemented, so it is not abstract by this test. The module docstring
        works the boundary through.

        A class that declares no ``__abstractmethods__`` at all and one whose
        every inherited abstract method has been implemented are different
        mistakes, and the failure says which. Returns the subject, so the call
        chains.
        """
        declared = abstract_methods(self._subject)
        if declared:
            return self
        if declared is None:
            return self._fail("to be abstract, but it declares no abstract methods", because)
        return self._fail("to be abstract, but it leaves no abstract method unimplemented", because)

    def is_not_abstract(self, *, because: str = "") -> Self:
        """Assert the class leaves no abstract method unimplemented.

        The complement of :meth:`is_abstract`, and the assertion an implementation
        wants: "this subclass is finished". A class that never declared an
        abstract method passes. The failure names what is missing, sorted --
        ``__abstractmethods__`` is a ``frozenset``, and an unordered message would
        differ between runs of the same test. Returns the subject, so the call
        chains.
        """
        declared = abstract_methods(self._subject)
        if not declared:
            return self
        return self._fail(
            f"not to be abstract, but it leaves"
            f" {listed(sorted(format_value(name) for name in declared))} unimplemented",
            because,
        )
