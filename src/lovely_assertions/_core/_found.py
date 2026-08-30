"""The continuation a narrowing assertion hands back.

``.and_`` goes on asserting about the value that was narrowed from; ``.which``
goes down into the value that was found, re-dispatched to whatever subject its
type deserves. Two directions from one object, so a chain never has to be broken
in half to ask about both.
"""

from typing import TYPE_CHECKING, Any, cast, override

from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from lovely_assertions._core import Expect

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class Found[P, V, A = Expect[V]]:
    """The result of an assertion that *found* a value inside the subject.

    ``P`` is the subject the assertion was made on and ``V`` the value that was
    found: ``.and_`` goes back to the first, ``.which`` descends into the second,
    and ``.subject`` hands the found value over untyped by any wrapper.

    ``A`` is what ``.which`` hands back. It defaults to ``Expect[V]``, so the
    plain ``Found[Self, V]`` that most producers write means an ordinary subject.
    A producer that knows better says so: :meth:`Expect.is_instance_of` returns
    ``Found[Self, str, StringExpect]`` for ``type[str]``, because that is the
    object ``expect()`` builds, and declaring ``Expect[str]`` would withhold the
    string catalogue from a value that has it.

    **Why a type parameter rather than an overloaded ``which``.** The obvious
    shape is three overloaded properties differing in the ``self`` type.
    pyright refuses it outright -- ``Argument of type "property" cannot be
    assigned to parameter "func" of type "_F@overload"``, plus a
    ``reportRedeclaration`` per stub -- and then evaluates the attribute as
    ``Any``, which is a worse declaration than the one it would have replaced.
    The parameter moves the choice to the producer, which is the only place that
    knows the answer anyway: ``which`` sees a value, and a value's type is not
    what decides its subject here (see :meth:`Expect.is_instance_of`).
    """

    __slots__ = ("_named_type", "_parent", "_value")

    def __init__(self, parent: P, value: V, named_type: type[Any] | None = None, /) -> None:
        self._parent: P = parent
        self._value: V = value
        #: The type the *caller* named, where they named one. See :attr:`which`.
        self._named_type: type[Any] | None = named_type

    @override
    def __repr__(self) -> str:
        return f"Found({self._value!r})"

    @property
    def and_(self) -> P:
        """Continue asserting on the original subject."""
        return self._parent

    @property
    def which(self) -> A:
        """Continue asserting on the value that was found.

        The ``cast`` is where the declaration and the dispatch meet. ``expect()``
        answers ``Expect[V]`` for an unconstrained ``V`` and can answer nothing
        better from here -- the producer's overload is what knows ``A``. The cast
        itself costs one call and allocates nothing; a continuation is not an
        assertion, so the no-allocation rule that governs a passing assertion does
        not reach here, and the ``expect()`` dispatch this wraps dwarfs it anyway.

        **Where the caller named a type, that type decides**, and not the value.
        ``expect(colour).as_type(str)`` is a checker-visible promise of a
        ``StringExpect``, and dispatching on the value instead would break it for
        exactly one shape: a ``StrEnum`` member *is* a ``str``, but ``expect()``
        answers ``EnumExpect`` for it, on purpose. ``.starts_with(...)`` would
        then type-check under both checkers and raise ``AttributeError`` at
        runtime -- the one thing this library exists to prevent. The type the
        caller wrote is the one they meant, so
        :func:`~lovely_assertions._subjects.subject_for` is asked about that type
        and the runtime stays in step with the overloads. Where no type was named,
        the value is dispatched as ``expect()`` would dispatch it.
        """
        # Imported here rather than at module scope: `_subjects` imports this module.
        from lovely_assertions._subjects import expect, subject_for  # noqa: PLC0415

        named = self._named_type
        if named is not None:
            factory = subject_for(named)
            if factory is not None:
                return cast("A", factory(self._value))
        return cast("A", expect(self._value))

    @property
    def whose_value(self) -> A:
        """The mapping-flavoured spelling of :attr:`which`; the same object.

        ``expect(rows).contains_key("id").whose_value.is_equal_to(7)`` reads the way
        the assertion is meant, where ``.which`` would leave the reader working out
        what "which" refers to.
        """
        return self.which

    @property
    def subject(self) -> V:
        """The value that was found, re-typed."""
        return self._value
