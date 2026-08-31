"""The context-manager form, and the two things it must not get wrong.

A handle asked before its block ends is asked about a capture that has not
happened, and answering would be answering about nothing. And once a soft scope
has recorded a failure, a handle that never got its warnings must stop reporting
rather than pile a second failure on the first.
"""

from typing import TYPE_CHECKING, Any, Never, Self, override

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._warnings._capture import allowed, matching, reissue_unmatched
from lovely_assertions._warnings._rendering import warned_report
from lovely_assertions._warnings._subject import WarnedExpect

if TYPE_CHECKING:
    from types import TracebackType
    from warnings import WarningMessage

    from lovely_assertions._occurrence import Occurrence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Raised from the handle ``expect_warns`` yields, for as long as the block has
#: not finished. Anything else -- a placeholder subject, a bare ``AttributeError``
#: from the unset slot -- would leave the reader guessing. ``_callable.py`` says
#: the same thing about the same moment, in the same words.
_NOT_CAPTURED_YET = (
    "the warnings are only available after the `with expect_warns(...)` block has finished"
)


class CaughtWarnings[W: Warning](WarnedExpect[W]):
    """The handle :func:`expect_warns` yields: a subject that arrives late.

    It is the context manager *and* the subject, so ``as warned`` binds the object
    the assertions are made on. Its ``_subject`` slot stays unset until
    :meth:`__exit__` fills it, which is what makes an access from inside the block
    an error rather than a lie (see :meth:`__getattr__`). ``_callable._CaughtExpect``
    is the same design against exceptions, and the differences between the two are
    each noted where they appear.
    """

    #: Five attributes beyond the inherited subject: what the block was asked for,
    #: how many times, the reason to report if it does not happen, the open
    #: capture, and the log it is filling. Two more carry the soft-scope seam:
    #: ``_absorbed``, whether a soft scope has already collected this block's
    #: failure, at which point the rest of the chain has nothing left to say, and
    #: ``_stand_in``, the value a narrowing assertion is handed once it has.
    __slots__ = (
        "_absorbed",
        "_because",
        "_capture",
        "_expected",
        "_occurrences",
        "_records",
        "_stand_in",
    )

    def __init__(
        self, expected: type[W], occurrences: "Occurrence | None", because: str, /
    ) -> None:
        self._expected: type[W] = expected
        self._occurrences: Occurrence | None = occurrences
        self._because: str = because
        self._absorbed: bool = False
        # Named here rather than recovered from the source, which is the one place
        # this differs from `expect_raises`. Name recovery reads the *first
        # argument* of a call it recognises as an entry point, and the set of
        # entry points lives in `_names.py`; naming the category outright gets the
        # same "Expected UserWarning to ..." without that coupling, spares the
        # frame walk a failure would otherwise pay for, and says `UserWarning`
        # even where the caller passed the category in a variable.
        self._name = expected.__name__

    def __getattr__(self, name: str) -> Never:
        """Explain the one attribute that can legitimately be missing.

        ``_subject`` is an unset slot until the block finishes, so ``.subject``,
        ``__repr__`` and every inherited assertion land here when they are reached
        from *inside* the block. Saying why beats the bare ``AttributeError`` the
        slot would raise, and beats a placeholder even more: a placeholder would
        let the assertion run and report on nothing. Every other name is a typo
        and keeps the ``AttributeError`` it deserves.

        A plain ``RuntimeError``, where ``_callable`` needs a private subclass: its
        ``__exit__`` has to tell its own guard from a failure of the code under
        test, and this one does not -- any exception crossing the block means the
        block did not finish, and none of them is reported.
        """
        if name == "_subject":
            raise RuntimeError(_NOT_CAPTURED_YET)
        raise AttributeError(name)

    @override
    def _fail(
        self, expectation: str, because: str = "", /, *, cause: BaseException | None = None
    ) -> Self:
        """As ``Expect._fail``, unless the failure has already been reported.

        In a soft scope, :meth:`__exit__` collects its failure and execution
        carries on into a chain whose warnings were never captured. The object
        bound by ``as warned`` cannot be swapped for the stand-in that absorbs a
        narrowing failure elsewhere, so the absorbing happens here instead: one
        root cause, one message.

        Where ``_CaughtExpect`` also has to override ``where``, ``matches`` and
        ``satisfies``, this family does not. Those three hand the subject to a
        user's callable, and an exception subject has no harmless value to hand
        over -- so it gets the stand-in, whose every attribute is itself, and
        ``len(error.args)`` inside a predicate raises ``TypeError`` from inside the
        soft block. A tuple has ``()``, which is a real value of the declared type,
        and a predicate written for real warnings runs against no warnings without
        complaint -- so :meth:`__exit__` keeps ``()`` as the subject and those three
        need no guard.

        That does not reach the *narrowing* assertions. They hand their result to
        the rest of the chain rather than to a predicate, and what they owe it is a
        value that goes on absorbing, not one that is merely safe to read: ``()``
        would answer ``.which`` with an ``AttributeError``, which is not an
        ``AssertionError`` and so would escape the soft scope and lose every
        failure already collected. :meth:`_fail_narrowing` hands back the stand-in
        for exactly that reason.
        """
        if self._absorbed:
            return self
        return super()._fail(expectation, because, cause=cause)

    @override
    def _fail_narrowing(
        self, expectation: str, because: str = "", /, *, cause: BaseException | None = None
    ) -> Any:
        """As ``Expect._fail_narrowing``, absorbed once the failure has been reported.

        The stand-in and not the subject: see :meth:`_fail` for why the empty
        tuple that serves every other absorbed assertion cannot serve this one.
        """
        if self._absorbed:
            return self._stand_in
        return super()._fail_narrowing(expectation, because, cause=cause)

    def __enter__(self) -> "WarnedExpect[W]":
        """Open the capture. Everything about it is argued in the module docstring.

        ``action="always"`` is the 3.11 spelling of ``simplefilter("always")``
        inside the block, and is used in preference to calling ``simplefilter``
        by hand because it makes the filter change and its restoration one
        object's business rather than two statements that can be separated.
        """
        import warnings  # noqa: PLC0415  (deferred: only a warning assertion pays for it)

        capture = warnings.catch_warnings(record=True, action="always")
        self._capture: warnings.catch_warnings[list[WarningMessage]] = capture
        self._records: list[WarningMessage] = capture.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: "TracebackType | None",
        /,
    ) -> None:
        """Close the capture, then judge it -- and only if the block finished.

        The capture is closed first, unconditionally, so the process's filters and
        ``showwarning`` are restored whatever else happens here. An exception
        crossing the block means the block did not finish, so there is nothing to
        judge: the exception is the finding, and it travels. That is what
        ``pytest.warns`` does with the same situation, and what
        ``_CaughtExpect.__exit__`` does with a ``BaseException``.

        Returns ``None``, where ``_CaughtExpect.__exit__`` returns a ``bool``, and
        the difference is the whole of the difference between the two families.
        ``expect_raises`` suppresses the exception it was asked for, because that
        exception is its subject; a warning is not raised, so there is nothing here
        to suppress -- and suppressing a block's genuine exception because a
        warning assertion failed would hide the more interesting failure. Declared
        as ``None`` rather than as ``bool`` so that the promise is the signature
        rather than a sentence in a docstring; mypy asks for exactly that.
        """
        records = self._records
        self._capture.__exit__(exc_type, exc, traceback)
        if exc is not None:
            return
        found = matching(records, self._expected)
        reissue_unmatched(records, self._expected)
        if allowed(len(found), self._occurrences):
            self._subject = found
            return
        # The subject is filled in before the failure is reported, not after: in a
        # soft scope the report returns and the chain runs on, and it has to run
        # against a real value. The empty tuple is one -- "no warning matched" --
        # which is why the assertions that hand the subject to a callable of the
        # user's need no guard here.
        self._subject = ()
        # Reported through `_fail_narrowing` rather than `_fail` for its return
        # value alone -- the sentence is the same either way. What it hands back is
        # the stand-in that a narrowing assertion further down the chain has to be
        # given: `()` would answer the `.which` after it with an `AttributeError`,
        # which crosses the soft scope instead of being absorbed inside it.
        self._stand_in: Any = self._fail_narrowing(
            f"to be warned{warned_report(records, len(found), self._occurrences)}", self._because
        )
        # Only reached inside a soft scope; the report raised otherwise. The
        # failure is on the report, so everything downstream of it has one root
        # cause already named and nothing of its own to add.
        self._absorbed = True
