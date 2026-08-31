"""Assertions for callables and the exceptions they raise.

Two entry forms land on the same subject. The **callable form** wraps a thunk,
``expect(lambda: parse("x")).raises(ValueError)``; the **context-manager form**
is the primary one, and sits where ``pytest.raises`` sits::

    with expect_raises(ValueError) as caught:
        parse("x")
    caught.with_message_containing("invalid")

Both hand back a :class:`RaisedExpect`, whose subject *is* the caught exception,
so the whole generic catalogue applies to it.

Several rules run through the module.

**The real exception is never dropped.** When the call raises something other
than what was asked for, that exception's traceback is the most valuable thing on
screen, so every failure reported from inside an ``except`` hands it to ``_fail``
as ``cause=`` and the ``AssertionFailure`` is raised ``from`` it. The message
explains the test, the ``__cause__`` explains the code, and neither is paid for
until something actually fails.

**``BaseException`` is not ``Exception``.** The wrong-type branches and
``does_not_raise()`` catch ``Exception`` only. A ``KeyboardInterrupt`` means the
user pressed Ctrl-C and a ``SystemExit`` means something called ``sys.exit``;
turning either into an assertion failure would hijack the interpreter's own
control flow. Ask for one by name -- ``raises(SystemExit)``,
``does_not_raise(KeyboardInterrupt)`` -- and it is caught, because then it is the
subject of the test rather than an interruption of it.

**A cause is ``__cause__`` first, ``__context__`` second.** ``raise X from Y``
sets ``__cause__`` and a bare ``raise`` inside an ``except`` sets ``__context__``;
both are what a reader calls "the inner exception", so :meth:`RaisedExpect.with_cause`
looks at both and every failure it reports names the attribute it looked at.

**``__notes__`` is absent until the first ``add_note``** (PEP 678), so it is read
with :func:`_notes_of` and never with an attribute access. Every note assertion
lists the notes that *were* attached, because when the expected one is missing
that listing is the entire finding -- and ``pytest.raises`` offers nothing here
at all, so a reader who lands on a failure has nowhere else to have looked.

**Warnings live here too, and only their callable form does.** ``warns`` and
``does_not_warn`` sit beside ``raises`` and ``does_not_raise`` at the bottom of
:class:`CallableExpect`; everything they are made of -- the capture, the verdict,
the listing, :class:`~lovely_assertions._warnings.WarnedExpect` and the
``expect_warns`` block -- is in :mod:`lovely_assertions._warnings`, whose module
docstring argues the design. They are written here rather than there for one
reason: an ``async def`` handed to a synchronous assertion has to be refused, and
:func:`_reject_awaitable` is that refusal. A second copy of it in another module
would be a second thing to keep in step with the first.

Three subjects and the two layers under them: how an exception is rendered, and
the refusal of a coroutine handed to a synchronous assertion. Each subject is
assembled from one mixin per seam.
"""

from lovely_assertions._callable._block import CaughtExpect
from lovely_assertions._callable._calling import CallableExpect
from lovely_assertions._callable._expect_raises import expect_raises
from lovely_assertions._callable._raised import RaisedExpect
from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = ["CallableExpect", "CaughtExpect", "RaisedExpect", "expect_raises"]
