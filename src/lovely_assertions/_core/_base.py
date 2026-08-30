"""The wrapper itself, and the one place a failure is reported.

One attribute, allocated per assertion, and a primitive every assertion in the
library ends in. That primitive is why a soft scope, a subject name and
``because=`` work everywhere without a single assertion knowing about any of
them: there is exactly one function that turns a comparison that said no into a
sentence, and it is here.

Everything else about a subject is a mixin over this class. What lives here is
what every one of them needs.
"""

from typing import Any, Self, override

from lovely_assertions._core._routing import report_failure
from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class _AbsorbingSubject:
    """Stand-in returned when a *narrowing* assertion fails inside a soft scope.

    The narrowed subject does not exist -- there is nothing to assert on. Raising
    ``AttributeError`` would be noise, and letting the chain continue against the
    un-narrowed value would report a second failure derived from the first. So
    everything downstream is absorbed instead, and the soft report keeps one
    message per root cause.
    """

    __slots__ = ()

    def __getattr__(self, name: str) -> Any:  # noqa: ANN401  (absorbs every attribute)
        return self

    def __call__(self, *_args: object, **_kwargs: object) -> Any:  # noqa: ANN401  (absorbs calls)
        return self

    @override
    def __repr__(self) -> str:
        return "<lovely-assertions: narrowing failed, further assertions absorbed>"


_ABSORBING: Any = _AbsorbingSubject()


class ExpectBase[T]:
    """A disposable, typed wrapper around the value under test.

    Built by :func:`~lovely_assertions.expect`, chained on, and thrown away. ``T``
    is the subject's type; it is what ``.subject`` re-exposes after an assertion
    has narrowed it.
    """

    #: ``_name`` is declared but deliberately not assigned in ``__init__``. An
    #: unassigned slot costs the wrapper one pointer and its construction
    #: nothing, where assigning it would put an attribute store on every subject
    #: ever built. The failure path reads it with a default instead.
    __slots__ = ("_name", "_subject")

    def __init__(self, subject: T, /) -> None:
        self._subject: T = subject

    @override
    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._subject!r})"

        # -- continuations -----------------------------------------------------

    @property
    def subject(self) -> T:
        """The value under test, re-typed by whatever narrowing has happened."""
        return self._subject

    @property
    def and_(self) -> Self:
        """Re-chain another assertion on the same subject. A typed no-op."""
        return self

        # -- the primitive -----------------------------------------------------

    def _fail(
        self, expectation: str, because: str = "", /, *, cause: BaseException | None = None
    ) -> Self:
        """Report a failed assertion. **Failure path only** -- never call this to test.

        Renders the message, then routes: append to the collector when a soft
        scope is active, otherwise raise. Returns ``Self`` so that a soft block
        keeps chaining past the failure instead of stopping at the first one.

        ``cause`` chains the raised failure onto an exception that is the reason
        for it -- the one an exception assertion caught, for instance. Without it
        the assertion message would replace the traceback the reader actually
        needs. Ignored in a soft scope, where nothing is raised to chain onto.
        """
        report_failure(expectation, because, cause, getattr(self, "_name", None))
        return self

    def _fail_narrowing(
        self, expectation: str, because: str = "", /, *, cause: BaseException | None = None
    ) -> Any:  # noqa: ANN401  (the narrowed subject does not exist; a stand-in stands in)
        """``_fail`` for assertions that were supposed to produce a *narrowed* subject.

        There is no narrowed subject to return, so a soft scope gets a stand-in
        that absorbs the rest of the chain rather than a wrapper whose static type
        is now a lie.
        """
        report_failure(expectation, because, cause, getattr(self, "_name", None))
        return _ABSORBING

    def described_as(self, name: str, /) -> Self:
        """Name this subject explicitly, instead of recovering it from the source.

        Subject recovery reads the statement that built the subject, which is the
        right answer almost always and no answer at all in two places: a loop,
        where every iteration names the same variable, and a helper, where the
        source names the helper's parameter rather than the caller's value.

            for index, row in enumerate(rows):
                expect(row).described_as(f"rows[{index}]").is_equal_to(...)

        ``expect(value, name=...)`` is the same thing said earlier.
        """
        self._name = name
        return self
