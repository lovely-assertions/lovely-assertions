"""Assertions about a class itself -- ``TypeExpect``.

``expect(SomeClass)`` hands back a :class:`TypeExpect`, which extends
:class:`~lovely_assertions.CallableExpect` because a class is also a callable. So
a class subject answers both kinds of question::

    expect(Order).raises(TypeError)                 # the constructor rejects an empty call
    expect(Order).is_subclass_of(Record)            # and what the class itself is

That first line is not a curiosity. A constructor that must refuse bad arguments
is a real assertion, and calling the class through the subject is the only way to
make it without folding the class into a lambda.

Four questions a class subject has to answer, and the answers this one gives.

**What counts as abstract?** ``__abstractmethods__`` being non-empty, whatever the
metaclass. ``ABCMeta`` is the usual thing that populates it, but it is not the
only one -- ``abc.update_abstractmethods``, a hand-rolled metaclass, or a
framework computing its own abstractness all write the same attribute -- and an
assertion that asked for ``ABCMeta`` instead would call those classes concrete
while the interpreter refuses to instantiate them. It is also the only place the
*names* live, and naming what is left unimplemented is the useful half of the
failure. Note what this deliberately is **not**: a claim about instantiability.
``class Base(ABC): pass`` constructs fine and is not abstract here; a
``Protocol`` cannot be constructed at all and is not abstract here either,
because it leaves nothing unimplemented. The assertion says what it measured.

**A protocol that cannot be checked is a bug in the test, not a finding about the
class.** ``isinstance``/``issubclass`` refuse a protocol that is not
``@runtime_checkable``, and refuse a *data* protocol -- one with non-method
members -- even when it is. Neither refusal says anything about the subject, so
neither is reported through ``_fail``: they are raised as ``TypeError`` where the
call was written, with the actual problem named and the fix in the message. An
``AssertionFailure`` there would let a runner present "your class does not
implement Closeable" when nothing was ever checked -- and inside a soft scope it
would be collected and read as a genuine finding. ``_callable._reject_awaitable``
takes exactly this line for exactly this reason.

The data-protocol refusal is not a limitation to work around, either. A member
declared ``name: str`` lives on *instances*; a class that assigns it in
``__init__`` conforms perfectly and has no such class attribute. Checking the
class would report a failure that is simply false, so the assertion declines and
points at the instance.

**A method is an attribute that is callable, and ``getattr`` on a class flattens
the four ways of writing one.** A plain ``def`` comes back as a function, a
``classmethod`` as a bound method, a ``staticmethod`` as a plain function again,
and a ``property`` as the descriptor object -- which is not callable, so
:meth:`TypeExpect.has_method` rejects it, correctly and unhelpfully unless the
message says *why*. Only the undecorated declaration in the MRO tells the four
apart, so :func:`_kind_of` reads that instead, and the failure says "but it is a
property" rather than printing an address.

**``has_attribute`` asks the class, and only the class.** An attribute assigned in
``__init__`` belongs to instances and is not found here; the message says where
it looked so the reader is not left guessing.

Two house rules show in the shape of the code. Every rendering is bounded by the
scope in force (``_formatting.current_formatting``), read inside failure branches
and nowhere else, so a passing assertion never touches a ``ContextVar``. And the
helpers below build text by concatenation rather than with f-strings: an f-string
is a message, a message belongs inside a ``_fail`` call, and a passing assertion
must render nothing at all.
"""

from typing import TYPE_CHECKING, Any, Final, Self, cast, get_protocol_members, is_protocol

from lovely_assertions._callable import CallableExpect
from lovely_assertions._core import Found
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._formatting import current_formatting
from lovely_assertions._text import length_note

if TYPE_CHECKING:
    from collections.abc import Sequence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = ["TypeExpect"]

#: Distinguishes "the class has no such attribute" from "it has one whose value
#: is ``None``". ``hasattr`` followed by ``getattr`` would answer both questions
#: at the cost of two lookups; one ``getattr`` with a sentinel answers them at the
#: cost of none.
_MISSING: Final = object()

#: Handed to ``isinstance`` to find out whether a runtime check against a
#: protocol runs at all. See :func:`_accepts_isinstance`.
_PROBE: Final = object()


# ---------------------------------------------------------------------------
# Rendering -- failure path only.
#
# No f-strings here: an f-string is a message, a message belongs inside a `_fail`
# call, and none of these helpers may run before an assertion has already failed.
# ---------------------------------------------------------------------------
def _rendered(value: object, /) -> str:
    """Render a value for a failure message, bounded by the formatting scope.

    ``max_chars`` is read here rather than frozen into a module constant, so a
    block that opened ``formatting(max_chars=...)`` gets the longer rendering it
    asked for -- and a passing assertion, which never reaches this function,
    still reads no ``ContextVar`` at all.
    """
    text = format_value(value)
    limit = current_formatting().max_chars
    if len(text) <= limit:
        return text
    return text[:limit] + "..." + length_note(len(text))


def _listed(rendered: "Sequence[str]", /) -> str:
    """Lay a run of already-rendered names out in a sentence, bounded and counted.

    The bound is ``max_items`` from the scope in force, and what is left out is
    counted rather than dropped silently -- ``_callable._render_notes`` does the
    same for an exception's notes, and for the same reason: a message that
    truncates without saying so is a message the reader will trust wrongly.

    An empty run renders as the empty string; every caller here has already
    established that it has something to say before calling.
    """
    limit = current_formatting().max_items
    if len(rendered) <= limit:
        return ", ".join(rendered)
    left_out = len(rendered) - limit
    return ", ".join(rendered[:limit]) + ", ... (" + str(left_out) + " more)"


def _named(candidate: object, /) -> str:
    """A class's name for a failure message.

    ``__name__`` rather than ``__qualname__``, matching ``is_instance_of`` and
    every other type named in a message in this library. Read with ``getattr``
    rather than as an attribute because a hand-built subject need not be a class
    at all, and a message must still come out.
    """
    name: str | None = getattr(candidate, "__name__", None)
    return name if isinstance(name, str) else _rendered(candidate)


def _mro_of(subject: object, /) -> "tuple[type[Any], ...]":
    """A class's method resolution order, or an empty one for a non-class.

    The annotation is what ``type`` promises; the ``getattr`` is what actually
    holds, because this subject is only guaranteed to be a class by dispatch and
    a hand-built one need not be (see :class:`TypeExpect`).
    """
    mro: tuple[type[Any], ...] | None = getattr(subject, "__mro__", None)
    return mro if isinstance(mro, tuple) else ()


def _bases_of(subject: object, /) -> str:
    """What a class inherits from, itself excluded. Failure path only.

    This is the "what was there" half of a failed subclass check: a reader who
    has just been told the class is not a subclass of something wants to know
    what it *is* derived from, and the MRO answers that in one line. A class
    registered as a virtual subclass with ``ABCMeta.register`` does not appear
    here, because nothing was inherited -- :func:`_why_subclass` is what explains
    the opposite failure.
    """
    ancestors = [_named(base) for base in _mro_of(subject)[1:]]
    if not ancestors:
        return "nothing"
    return _listed(ancestors)


def _why_subclass(subject: object, other: type[object], /) -> str:
    """Why ``issubclass`` said yes, for a negated assertion. Failure path only.

    Three answers, because three genuinely different things happened.
    ``issubclass`` is reflexive, so a class is a subclass of itself and a reader
    who did not have that in mind needs telling. Ordinary inheritance puts the
    other class in the MRO. And neither of those explains a *virtual* subclass --
    ``ABCMeta.register``, or a ``__subclasshook__`` matching structurally -- where
    ``issubclass`` says yes and the MRO shows nothing, which is precisely the
    case a reader stares at without understanding.
    """
    name = _named(other)
    if subject is other:
        return "it is " + name + " itself"
    if other in _mro_of(subject):
        return name + " is one of its base classes"
    return "it counts as one without inheriting from it: " + name + " is not in its MRO"


def _declared(subject: object, name: str, /) -> object:
    """The undecorated declaration of ``name``, from the class dictionaries.

    ``getattr`` runs the descriptor protocol, which is exactly what hides the
    difference this function exists to see: it turns a ``classmethod`` into a
    bound method, a ``staticmethod`` into a plain function and a ``property``
    into the descriptor. The declaration in ``__dict__`` is the only place the
    four are still distinguishable.
    """
    for base in _mro_of(subject):
        declaration = vars(base).get(name, _MISSING)
        if declaration is not _MISSING:
            return declaration
    return None


#: The three decorators ``getattr`` on a class dissolves, and what a reader calls
#: them. Keyed on the exact type rather than matched with ``isinstance``:
#: ``staticmethod`` and ``classmethod`` are generic, and narrowing to one of them
#: yields the partially unknown type pyright's strict mode will not let a caller
#: pass on (the trap ``_callable._is_awaitable`` documents). Nothing here needs
#: the narrowed value, only its name, so the exact test stays out of that hole.
_DECORATED: Final[dict[type, str]] = {
    property: "a property",
    staticmethod: "a static method",
    classmethod: "a class method",
}


def _kind_of(subject: object, name: str, value: object, /) -> str:
    """How the class declares ``name``, as a reader would say it. Failure path only.

    Named rather than printed: ``<property object at 0x10f3a2d90>`` is the kind
    of rendering that tells a reader nothing, and "a property" is the entire
    finding when ``has_method`` turned one down.
    """
    decorated = _DECORATED.get(type(_declared(subject, name)))
    if decorated is not None:
        return decorated
    if value is None:
        return "None"
    if isinstance(value, type):
        return "the nested class " + _named(value)
    if callable(value):
        return "a method"
    return "the " + type(value).__name__ + " " + _rendered(value)


def _abstract_methods(subject: object, /) -> "frozenset[str] | None":
    """The names a class has left abstract, or ``None`` when it declares none.

    ``None`` and an empty set are different findings and both reach a message:
    a class with no ``__abstractmethods__`` at all never declared an abstract
    method, while an empty one means every inherited abstract method has been
    implemented. Those are two different mistakes and deserve two different
    sentences.

    The annotation is what ``ABCMeta`` promises; the ``isinstance`` is what
    actually holds, because any class can put anything under that name and a
    failure message must not blow up inside itself. ``_callable._notes_of`` takes
    the same line with ``__notes__``, for the same reason.
    """
    declared: frozenset[str] | None = getattr(subject, "__abstractmethods__", None)
    return declared if isinstance(declared, frozenset) else None


def _required_members(other: type[object], /) -> "frozenset[str] | None":
    """The member names ``other`` requires of whatever claims to satisfy it.

    A protocol carries them under :func:`typing.get_protocol_members`; an
    abstract base class carries them under ``__abstractmethods__``, which is why
    ``expect(MyList).implements(Sized)`` can report the missing ``__len__``
    rather than merely reporting a "no". Anything else -- a plain concrete class
    -- requires nothing structural, and ``None`` says so.
    """
    if is_protocol(other):
        return get_protocol_members(other)
    return _abstract_methods(other)


def _missing_members(subject: object, other: type[object], /) -> "list[str]":
    """The members ``other`` requires that ``subject`` does not have."""
    required = _required_members(other)
    if not required:
        return []
    return sorted(format_value(name) for name in required if not hasattr(subject, name))


def _shortfall(subject: object, other: type[object], /) -> str:
    """Why the class does not satisfy ``other``. Failure path only.

    Naming the members that are missing is the whole value of ``implements``
    over a bare "no". When there are none to name -- ``other`` is a concrete
    class, or the member is present but reached in a way the protocol check does
    not accept -- the fallback is the same "what was there" a failed subclass
    check gives, which is always computable and never wrong.
    """
    missing = _missing_members(subject, other)
    if missing:
        return "it does not define " + _listed(missing)
    return "it inherits from " + _bases_of(subject)


def _provided(subject: object, other: type[object], /) -> str:
    """The mirror of :func:`_shortfall`, for the negated assertion.

    What makes a *failed* ``does_not_implement`` legible is the list of members
    the class turned out to define, because the reader's next move is to delete
    one of them.

    Only the members it *has* are listed, never everything the protocol asked
    for. A class registered with ``ABCMeta.register`` satisfies ``issubclass``
    while defining none of them, and a message claiming otherwise would send the
    reader looking for a ``__len__`` that was never written. Where there is
    nothing to list, the inheritance note says what really happened.
    """
    required = _required_members(other)
    present = (
        sorted(format_value(name) for name in required if hasattr(subject, name))
        if required
        else []
    )
    if present:
        return "it defines " + _listed(present)
    return _why_subclass(subject, other)


# ---------------------------------------------------------------------------
# The runtime check, and the two refusals it has to explain
# ---------------------------------------------------------------------------
def _accepts_isinstance(protocol: type[object], /) -> bool:
    """Whether a runtime check against this protocol runs at all.

    Asked by trying it rather than by reading ``_is_runtime_protocol``: that
    attribute is private, and this is the question that actually matters. A
    protocol that is not ``@runtime_checkable`` refuses ``isinstance`` and
    ``issubclass`` alike, while a runtime-checkable *data* protocol answers
    ``isinstance`` and refuses only ``issubclass``. Trying the one that still
    works is what tells the two refusals apart, and it needs nothing private to
    do it. Refusal path only.
    """
    try:
        isinstance(_PROBE, protocol)
    except TypeError:
        return False
    return True


def _uncheckable(other: type[object], /) -> str | None:
    """Why ``issubclass`` refused ``other``, or ``None`` when it was not about it.

    ``None`` matters as much as the two messages: a ``TypeError`` from a class's
    own ``__subclasshook__``, or from a subject that is not a class, is not this
    function's to explain, and rewriting it would replace a true error with a
    plausible lie about protocols.
    """
    if not is_protocol(other):
        return None
    name = _named(other)
    if not _accepts_isinstance(other):
        return (
            name + " is not @runtime_checkable, so nothing can be checked against it at"
            " runtime. Decorate it with typing.runtime_checkable, or assert on the members"
            " you care about with has_method(...)."
        )
    non_methods = sorted(
        format_value(member)
        for member in get_protocol_members(other)
        if not callable(getattr(other, member, None))
    )
    return (
        name + " has non-method members (" + _listed(non_methods) + "), and a data protocol"
        " cannot be checked against a class: those members live on instances, not on the"
        " class. Assert on an instance instead -- expect(obj).is_instance_of(" + name + ")."
    )


def _issubclass(subject: object, other: type[object], /) -> bool:
    """``issubclass``, with the two protocol refusals explained rather than re-raised.

    The ``cast`` states what ``expect()`` already guaranteed and what the
    inherited annotation cannot say (see :class:`TypeExpect`). The ``try`` costs
    nothing while nothing is raised, so a passing assertion pays for the guard no
    more than an attribute lookup and a call.
    """
    try:
        return issubclass(cast("type[Any]", subject), other)
    except TypeError as error:
        reason = _uncheckable(other)
        if reason is None:
            # Not about the protocol rules -- CPython's own message is the true
            # one, and burying it under ours would help nobody.
            raise
        raise TypeError(reason) from error


class TypeExpect(CallableExpect):
    """The subject ``expect()`` hands back for a class.

    It extends :class:`~lovely_assertions.CallableExpect`, so the whole callable
    catalogue is available on a class as well: ``expect(Order).raises(TypeError)``
    calls the constructor and asserts it refuses, which is a real assertion and
    the reason the inheritance is the right shape rather than a convenience.

    That inheritance fixes the subject's static type at
    ``Callable[..., object]``, so ``.subject`` hands a class back as a callable
    rather than as a ``type``. That is deliberate. Re-annotating the inherited
    ``_subject`` would be narrowing a mutable attribute in a subclass, which both
    checkers refuse and are right to; and a ``.subject`` typed ``type[Any]``
    would trade an honest type for an ``Any`` that silences the checker on every
    attribute reached through it. The caller already holds the class -- they
    wrote it in the ``expect(...)`` call -- so nothing is lost that they had.

    The subject *is* a class, because dispatch only routes one here. A
    hand-built ``TypeExpect(some_function)`` is not rejected on the way in, for
    the reason ``BoolExpect`` does not reject a hand-built ``BoolExpect(1)``: the
    assertions report the oddity instead of hiding it, and a constructor guard
    would cost every ordinary call to catch a mistake nobody makes twice.
    """

    __slots__ = ()

    # -- inheritance -------------------------------------------------------
    def is_subclass_of(self, other: type[object], /, *, because: str = "") -> Self:
        """Assert the subject is a subclass of ``other``.

        ``issubclass`` semantics exactly, which is to say more than inheritance:
        it is reflexive (a class is a subclass of itself), and it counts virtual
        subclasses registered with ``ABCMeta.register`` as well as structural
        matches made by a ``__subclasshook__``. The failure names what the class
        does inherit from, so the reader is not left to go and look.

        One type per call, never a tuple -- ``expect(C).is_subclass_of((A, B))``
        is a ``pytest.raises`` habit and the checker refuses it. Two calls say
        which one failed; a tuple would not. Returns the subject, so the call
        chains.

        Raises ``TypeError``, not a failure, when ``other`` is a protocol nothing
        can be checked against at runtime -- see :meth:`implements`, which
        explains both refusals and names the fix in the message.
        """
        if _issubclass(self._subject, other):
            return self
        return self._fail(
            f"to be a subclass of {_named(other)}, but it inherits from {_bases_of(self._subject)}",
            because,
        )

    def is_not_subclass_of(self, other: type[object], /, *, because: str = "") -> Self:
        """Assert the subject is not a subclass of ``other``.

        The exact complement of :meth:`is_subclass_of`, which means a class fails
        this against itself. The failure says which of the three ways it holds --
        the class itself, an ordinary base class, or a virtual subclass that
        inherits nothing -- because only the first two are visible in the source.
        Returns the subject, so the call chains, and raises ``TypeError`` on an
        uncheckable protocol exactly as :meth:`is_subclass_of` does.
        """
        if not _issubclass(self._subject, other):
            return self
        return self._fail(
            f"not to be a subclass of {_named(other)}, but {_why_subclass(self._subject, other)}",
            because,
        )

    # -- attributes and methods --------------------------------------------
    def has_attribute(self, name: str, /, *, because: str = "") -> "Found[Self, Any]":
        """Assert the class defines ``name``; continue on its value with ``.which``.

            expect(Order).has_attribute("DEFAULTS").which.is_instance_of(dict)

        The question is asked of the **class**, and only of the class: an
        attribute assigned in ``__init__`` belongs to instances and is not found
        here. The failure says where it looked, because that is the mistake this
        assertion is most often used to make.

        What ``.which`` receives is what ``getattr`` on the class returns, which
        for a ``property`` is the descriptor rather than any value -- there is no
        instance for it to compute one from. :meth:`has_method` names the four
        shapes a callable member can take, and is the one to reach for when the
        member is meant to be callable rather than merely present.

        An attribute holding ``None`` is found like any other; "defined as
        ``None``" and "not defined" are told apart. Returns a ``Found``, whose
        ``.and_`` continues on the class and whose ``.which`` continues on the
        attribute's value.
        """
        found: Any = getattr(self._subject, name, _MISSING)
        if found is not _MISSING:
            return Found(self, found)
        return cast(
            "Found[Self, Any]",
            self._fail_narrowing(
                f"to have the attribute {format_value(name)},"
                f" but no such attribute is defined on the class",
                because,
            ),
        )

    def does_not_have_attribute(self, name: str, /, *, because: str = "") -> Self:
        """Assert the class does not define ``name``.

        The assertion a removal wants: a deprecation that landed, an internal
        that must not have leaked. The failure names *how* the class declares
        it -- a property, a class method, a value -- because "it is still there"
        is a fact the reader already had.

        Asked of the class, and only of the class, exactly as
        :meth:`has_attribute` is: an attribute assigned in ``__init__`` belongs to
        instances and passes here. Returns the subject, so the call chains.
        """
        found: Any = getattr(self._subject, name, _MISSING)
        if found is _MISSING:
            return self
        return self._fail(
            f"not to have the attribute {format_value(name)},"
            f" but it is {_kind_of(self._subject, name, found)}",
            because,
        )

    def has_method(self, name: str, /, *, because: str = "") -> "Found[Self, Any]":
        """Assert the class defines ``name`` as a method; continue on it with ``.which``.

        A method is a callable attribute, and ``getattr`` on a class flattens the
        four ways of writing one: a plain ``def`` comes back as a function, a
        ``classmethod`` as a bound method, a ``staticmethod`` as a plain function
        again. All three are callable and all three pass. A ``property`` comes
        back as the descriptor, which is *not* callable and does not pass -- a
        property is a computed attribute, not a method, and the failure says
        exactly that rather than printing an address.

        A nested class is turned down too, for all that ``callable()`` says yes
        to it. ``expect(Repo).has_method("Row")`` where ``Row`` is an inner class
        is a test that passes for the wrong reason, and this library exists to
        stop those; without the carve-out the assertion would mean nothing more
        than "has a callable attribute", losing the one distinction it is for.

        A missing name and a name declared as something other than a method are
        different findings and get different sentences. Signatures are not
        checked, only that the member is there and callable. Returns a ``Found``,
        whose ``.and_`` continues on the class and whose ``.which`` continues on
        the method object. Reach for :meth:`has_attribute` when a property or a
        plain value is what is wanted.
        """
        found: Any = getattr(self._subject, name, _MISSING)
        if found is _MISSING:
            return cast(
                "Found[Self, Any]",
                self._fail_narrowing(
                    f"to have a method {format_value(name)},"
                    f" but no such attribute is defined on the class",
                    because,
                ),
            )
        if callable(found) and not isinstance(found, type):
            return Found(self, found)
        return cast(
            "Found[Self, Any]",
            self._fail_narrowing(
                f"to have a method {format_value(name)},"
                f" but it is {_kind_of(self._subject, name, found)}",
                because,
            ),
        )

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
        declared = _abstract_methods(self._subject)
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
        declared = _abstract_methods(self._subject)
        if not declared:
            return self
        return self._fail(
            f"not to be abstract, but it leaves"
            f" {_listed(sorted(format_value(name) for name in declared))} unimplemented",
            because,
        )

    # -- protocols ---------------------------------------------------------
    def implements(self, protocol: type[object], /, *, because: str = "") -> Self:
        """Assert the class satisfies ``protocol``.

            @runtime_checkable
            class Closeable(Protocol):
                def close(self) -> None: ...

            expect(Session).implements(Closeable)

        The runtime question is ``issubclass``, the same one
        :meth:`is_subclass_of` asks -- Python has one structural-conformance
        operator and this is it. The two are separate names because they read
        differently and fail differently: this one lists the members the class
        does not define, which is what a reader of a conformance failure needs
        and what an inheritance failure has nothing to say about. An abstract
        base class works here too, and lists its abstract methods the same way.

        Two protocols cannot be checked at all, and both raise ``TypeError``
        rather than reporting a failure, because nothing about the subject was
        established: one that is not ``@runtime_checkable``, and a *data*
        protocol -- one with non-method members -- which cannot be checked
        against a class because its members live on instances. Each refusal
        names the fix.

        What ``issubclass`` checks for a method protocol is that the members
        exist, not that their signatures match. A checker is what verifies
        signatures; this verifies that the object in front of you at runtime is
        the one the checker was looking at. Returns the subject, so the call
        chains.
        """
        if _issubclass(self._subject, protocol):
            return self
        return self._fail(
            f"to implement {_named(protocol)}, but {_shortfall(self._subject, protocol)}",
            because,
        )

    def does_not_implement(self, protocol: type[object], /, *, because: str = "") -> Self:
        """Assert the class does not satisfy ``protocol``.

        The complement of :meth:`implements`, and the one an accidental
        conformance wants: a class that grew a ``__len__`` and quietly became a
        ``Sized`` is a change no signature records. The failure lists the members
        it turned out to provide, since the reader's next move is to find where
        one of them came from; where it provides none -- a class registered with
        ``ABCMeta.register`` defines nothing and still conforms -- the message
        says that instead of listing members that were never written.

        Raises ``TypeError`` on the two protocols that cannot be checked at all,
        for the reason :meth:`implements` gives. Returns the subject, so the call
        chains.
        """
        if not _issubclass(self._subject, protocol):
            return self
        return self._fail(
            f"not to implement {_named(protocol)}, but {_provided(self._subject, protocol)}",
            because,
        )
