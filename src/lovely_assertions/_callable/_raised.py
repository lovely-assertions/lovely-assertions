"""The exception subject: what was caught, once something was.

Four seams over one value. What it says, what was attached to it with
``add_note``, what it was raised *from*, and whatever question the catalogue does
not cover. The cause seam is the one worth reading twice: ``raise B from A`` is a
claim about why, and asserting on it is asserting on a design decision rather
than on a value.
"""

from typing import TYPE_CHECKING, Any, Self, cast

from lovely_assertions._callable._continuation import ContinuationAssertions
from lovely_assertions._callable._message import MessageAssertions
from lovely_assertions._callable._notes import NoteAssertions
from lovely_assertions._callable._rendering import SUPPRESSED, cause_of, rendered
from lovely_assertions._core import Expect, describe_predicate
from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from collections.abc import Callable

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class RaisedExpect[E: BaseException](
    ContinuationAssertions[E],
    MessageAssertions[E],
    NoteAssertions[E],
    Expect[E],
):
    """The exception that was raised, as a subject.

    Everything on :class:`~lovely_assertions.Expect` already works here --
    ``is_instance_of``, ``satisfies``, ``is_equal_to`` on ``.args`` through
    ``.subject`` -- so this class adds only what is about being an exception.
    """

    __slots__ = ()

    # -- cause -----------------------------------------------------------------
    def with_cause[C: BaseException](
        self, exception_type: type[C], /, *, because: str = ""
    ) -> "RaisedExpect[C]":
        """Assert the exception has a cause of type ``exception_type``; continue on the cause.

        ``__cause__`` first, then ``__context__`` (see :func:`cause_of`), and
        the failure names which of the two it looked at -- "it has no cause" and
        "its cause is a TypeError that happened to be in flight" are different
        findings and deserve different messages.
        """
        found, source = cause_of(self._subject)
        if isinstance(found, exception_type):
            return RaisedExpect(found)
        if found is not None:
            return cast(
                "RaisedExpect[C]",
                self._fail_narrowing(
                    f"to have a cause of type {exception_type.__name__},"
                    f" but {source} was {rendered(found)}",
                    because,
                ),
            )
        return cast("RaisedExpect[C]", self._fail_no_cause(exception_type, source, because))

    def with_cause_exactly[C: BaseException](
        self, exception_type: type[C], /, *, because: str = ""
    ) -> "RaisedExpect[C]":
        """Assert the cause is ``exception_type`` itself -- a subclass does not count.

        ``__cause__`` first, then ``__context__``, exactly as :meth:`with_cause`,
        and the cause becomes the new subject. With no cause at all the finding is
        the absence rather than the type, so the message is the one
        :meth:`with_cause` gives: it says whether the context was suppressed with
        ``raise ... from None`` or simply never set. Reach for :meth:`with_cause`
        unless the point of the test is which exception type the code wrapped.
        """
        found, source = cause_of(self._subject)
        found_type = type(found)
        if found_type is exception_type:
            return RaisedExpect(cast("C", found))
        if found is not None:
            return cast(
                "RaisedExpect[C]",
                self._fail_narrowing(
                    f"to have a cause of exactly {exception_type.__name__},"
                    f" but {source} was {rendered(found)}",
                    because,
                ),
            )
        return cast("RaisedExpect[C]", self._fail_no_cause(exception_type, source, because))

    def _fail_no_cause(
        self, exception_type: type[BaseException], source: str, because: str, /
    ) -> Any:  # noqa: ANN401  (the stand-in a soft scope hands back is deliberately untyped)
        """Report a missing cause. **Failure path only**, and shared by both cause assertions.

        A helper is safe here where it would not be for the general case: it
        takes the *pieces*, never a built message, so nothing is formatted until
        one of the branches below runs -- and both of them are already inside a
        failure. It says "of type" for :meth:`with_cause_exactly` too: with no
        cause at all, the difference between "of type" and "of exactly" has
        nothing to bite on, and the finding is the absence either way.
        """
        if source == SUPPRESSED:
            return self._fail_narrowing(
                f"to have a cause of type {exception_type.__name__},"
                f" but its context was suppressed with `raise ... from None`",
                because,
            )
        return self._fail_narrowing(
            f"to have a cause of type {exception_type.__name__},"
            f" but neither __cause__ nor __context__ was set",
            because,
        )

    # -- predicate ----------------------------------------------------------
    def where(self, predicate: "Callable[[E], bool]", /, *, because: str = "") -> Self:
        """Assert the exception satisfies ``predicate``.

        The exception-flavoured spelling of ``matches``: FluentAssertions' ``Where``
        is where the attributes a specific exception carries -- ``errno``,
        ``response.status_code`` -- get asserted on, and the predicate is typed
        with the exception type ``raises`` narrowed to.

        The expectation says "to satisfy", not "to raise an exception
        satisfying", because the subject name is not always the caller: reached
        through ``with_cause`` it is the *outer* call, and
        ``Expected chained to raise an exception satisfying is_fatal, but
        KeyError('k') did not`` says that ``chained`` raised a ``KeyError``, which
        it did not. What was tested is named in the tail either way.
        """
        subject = self._subject
        if predicate(subject):
            return self
        return self._fail(
            f"to satisfy {describe_predicate(predicate)}, but {rendered(subject)} did not",
            because,
        )
