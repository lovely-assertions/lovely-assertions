"""What a protocol requires, whether a class provides it, and the check that answers.

Conformance and inheritance are one ``issubclass`` call underneath, asked by two
mixins that are independent by design and never reach for one another. So the
call sits below both rather than inside either: a second copy would be a second
opinion about which of the builtin's refusals the library may reword, and a
subclass check disagreeing with a conformance check about that is a bug nobody
would think to look for.

Rewording is why the plain builtin is not enough. Two protocols cannot be
checked against a class at runtime at all -- one that is not
``@runtime_checkable``, and a data protocol, whose members live on instances --
and each arrives as a ``TypeError`` that is true and of no use to somebody who
asked a question about their class. Those two are raised again with the fix
named, and raised rather than reported as a failure, because nothing about the
subject was established either way. Every other ``TypeError`` is left exactly as
it came.

The rest is what a failed check has to say, and "no" is not it. The finding is
the members that are missing -- or, for a negated check, the ones the class
turned out to provide -- and collecting them means knowing that a protocol keeps
its requirements under :func:`typing.get_protocol_members` while an abstract
base class keeps them under ``__abstractmethods__``. Both are read here, which
is what lets ``implements`` name a missing ``__len__`` whichever of the two the
reader wrote, and what lets the abstractness assertions read
``__abstractmethods__`` through the same guarded accessor rather than trusting
an attribute any class is free to overwrite.
"""

from typing import Any, Final, cast, get_protocol_members, is_protocol

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._type._hierarchy import bases_of, why_subclass
from lovely_assertions._type._naming import listed, named

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Handed to ``isinstance`` to find out whether a runtime check against a
#: protocol runs at all. See :func:`_accepts_isinstance`.
_PROBE: Final = object()


def abstract_methods(subject: object, /) -> "frozenset[str] | None":
    """The names a class has left abstract, or ``None`` when it has no ``__abstractmethods__``.

    ``None`` and an empty set are different findings and both reach a message:
    a class with no ``__abstractmethods__`` at all never had an abstract method
    marked on it, while an empty one carries the attribute and has nothing left
    unimplemented. Those are two different mistakes and deserve two different
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
    return abstract_methods(other)


def _missing_members(subject: object, other: type[object], /) -> "list[str]":
    """The members ``other`` requires that ``subject`` does not have."""
    required = _required_members(other)
    if not required:
        return []
    return sorted(format_value(name) for name in required if not hasattr(subject, name))


def shortfall(subject: object, other: type[object], /) -> str:
    """Why the class does not satisfy ``other``. Failure path only.

    Naming the members that are missing is the whole value of ``implements``
    over a bare "no". When there are none to name -- ``other`` is a concrete
    class, or the member is present but reached in a way the protocol check does
    not accept -- the fallback is the same "what was there" a failed subclass
    check gives, which is always computable and never wrong.
    """
    missing = _missing_members(subject, other)
    if missing:
        return "it does not define " + listed(missing)
    return "it inherits from " + bases_of(subject)


def provided(subject: object, other: type[object], /) -> str:
    """The mirror of :func:`shortfall`, for the negated assertion.

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
        return "it defines " + listed(present)
    return why_subclass(subject, other)


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

    ``None`` matters as much as the two messages: only a protocol is refused in
    either of these two ways, so a ``TypeError`` raised by a class's own
    ``__subclasshook__`` is not this function's to explain, and rewriting it
    would replace a true error with a plausible lie about protocols.
    """
    if not is_protocol(other):
        return None
    name = named(other)
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
        name + " has non-method members (" + listed(non_methods) + "), and a data protocol"
        " cannot be checked against a class: those members live on instances, not on the"
        " class. Assert on an instance instead -- expect(obj).is_instance_of(" + name + ")."
    )


def checked_issubclass(subject: object, other: type[object], /) -> bool:
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
