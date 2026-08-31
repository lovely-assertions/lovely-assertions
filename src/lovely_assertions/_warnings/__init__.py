"""Assertions about the warnings a call issues.

The catalogue this library is measured against is FluentAssertions', and .NET
has no warnings concept at all, so nothing in that catalogue asks for this
family -- a gap no source suggests is a gap nobody notices. Without it a
warning-emitting callable is invisible here: ``raises`` reports "but nothing was
raised (the call returned None)", which is true, unhelpful, and exactly the shape
of answer a library gives when it has not been asked the question.

Two entry forms land on the same subject, as the exception family does. The
**context-manager form** is the primary one, and sits where ``pytest.warns``
sits::

    with expect_warns(DeprecationWarning) as warned:
        legacy()
    warned.with_message_containing("use parse_iso instead")

The **callable form** wraps a thunk, ``expect(legacy).warns(DeprecationWarning)``,
and lives on :class:`~lovely_assertions.CallableExpect` beside ``raises`` --
in ``_callable.py``, so that both forms refuse an ``async def`` through the one
guard rather than through two that can drift.

**Why this exists next to** ``pytest.warns``, stated plainly because the honest
answer is "not for every case". ``pytest.warns`` is one line, is already in the
file, and needs no import. Three things it cannot do:

*It does not show you what was warned.* It tells you the warning you asked for
did not fire, which you already knew, and says nothing about the four that did --
which is the information that ends the investigation. Every failure this module
reports lists the warnings that were issued, each with the file and line the
``stacklevel`` pointed at.

*It cannot be collected.* ``pytest.warns`` raises, so it ends the test at the
first finding. Everything here reports through ``_fail``, so an active
``soft_assertions`` scope gathers a failed warning assertion alongside the rest
and the block runs to the end.

*It cannot count.* ``occurrences=exactly(2)`` and ``occurrences=at_least(1)`` are
the constraints the rest of this library already speaks, and ``pytest.warns`` has
no spelling for either -- a test that cares whether a deprecation fired once or
once per row has to record the warnings and count them by hand.

And one thing ``pytest.warns`` cannot express at all: assert that **nothing**
warned. Without it, that assertion is written out by hand around a
``catch_warnings`` block every time it is wanted.
:meth:`~lovely_assertions.CallableExpect.does_not_warn` is that assertion.

**The subject is a tuple.** ``raises`` narrows to *the* exception, because a call
raises at most one; a call may issue any number of warnings, and an assertion
that silently kept the first would be wrong in the case the user wrote
``occurrences=`` for. So :class:`WarnedExpect` carries every matching warning, in
the order they were issued, and its own assertions ask whether *some* warning
satisfies them -- the same "any of them" that ``RaisedExpect.with_note_matching``
already applies to notes.

That choice pays for itself in the soft-assertion path. When ``expect_raises``
fails inside a soft scope it has no exception to hand back, so ``_CaughtExpect``
substitutes a stand-in for its subject and has to guard the three assertions that
would hand that stand-in to a user's callable. A tuple has a perfectly good empty
value, so :class:`_CaughtWarnings` keeps ``()`` as its subject -- a real value of
the declared type, and one a predicate written for real warnings survives -- and
needs no such guards. The stand-in still appears where it has to: a narrowing
assertion owes the rest of the chain something that goes on absorbing, and ``()``
is not that, so :meth:`_CaughtWarnings._fail_narrowing` hands the stand-in back
exactly as every other subject in the library does.

**Capture is process-wide, and that is CPython's doing, not this library's.**
``warnings.catch_warnings`` swaps the global filter list and the global
``showwarning``, and its own documentation says it is not thread-safe. Two
consequences, both documented rather than papered over: a warning issued by
*another* thread while a block is open is captured by that block and counts
towards its constraint, and two threads capturing at once can restore each
other's filters. A lock here would fix neither, because it would have to be held
across the user's entire block -- arbitrary code, including code that blocks on
the other thread -- so this module does not take one. ``pytest.warns`` has the
same caveat for the same reason. Nesting in *one* thread is fine:
``catch_warnings`` is re-entrant, and it restores what it found rather than a
default.

**The** ``__warningregistry__`` **trap is handled, and not by us.** A warning
already issued once from a module is not issued again, because ``warn_explicit``
remembers ``(text, category, lineno)`` in that module's ``__warningregistry__``.
That is the single most common way a warning test passes alone and fails in a
suite. ``catch_warnings.__enter__`` bumps ``warnings._filters_version``, and
``warn_explicit`` clears any registry whose version does not match -- so entering
a capture invalidates every registry in the process. This module gets that for
free by using ``catch_warnings`` rather than saving and restoring
``warnings.filters`` by hand, which is the tempting shortcut and the one that
reintroduces the bug.

**Ambient filters do not apply inside the block.** Capture runs under
``action="always"``, so a ``DeprecationWarning`` that the interpreter ignores by
default is still seen, and ``-W error`` does not turn the warning under test into
an exception. Both are deliberate: an assertion that a warning was issued cannot
be written at all if the project's filters have already converted it into
something else, and a test that says "this call deprecates" should not have to
know how the suite is configured. It is also what ``pytest.warns`` does.

**Warnings nobody asked about are re-issued on the way out.** A capture that
matched ``UserWarning`` and swallowed a ``DeprecationWarning`` would have
disarmed the project's own filters for the duration of the block -- silently, and
in the direction that loses information. So every warning outside the category
under test is handed back to ``warnings.warn_explicit`` once the ambient filters
are restored, which is where it would have gone had the block not been there.
Two consequences follow, and both are the price of being faithful rather than
convenient: under ``-W error`` a re-issued warning raises, at the end of the
block instead of in the middle of the call that issued it; and the re-issue
carries no registry, so a ``once`` filter shows it again. A block that did not
finish -- one whose body raised -- re-issues nothing: its exception is the
finding, and running the project's filters over the warnings it managed to issue
first could raise a second exception that would replace it.

Four files: how a warning reads, how a capture is selected from and put back,
the subject over what was caught, and the block that catches it.
"""

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._warnings._capture import allowed, matching, reissue_unmatched
from lovely_assertions._warnings._caught import CaughtWarnings
from lovely_assertions._warnings._expect_warns import expect_warns
from lovely_assertions._warnings._rendering import issued_report, warned_report
from lovely_assertions._warnings._subject import WarnedExpect

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = [
    "CaughtWarnings",
    "WarnedExpect",
    "allowed",
    "expect_warns",
    "issued_report",
    "matching",
    "reissue_unmatched",
    "warned_report",
]
