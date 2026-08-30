"""How much a failure message may print, and how a block asks for more.

Every rendering in the library is bounded: a collection prints its first few
items and counts the rest, one value prints about a terminal line of characters, a
unified diff prints a screenful, and a difference descends a couple of levels into
nested structure. Those defaults are chosen for the message a reader *skims* --
the one that says at a glance which assertion went wrong -- and they are exactly
wrong for the message they are *debugging*. A four-hundred-element list that shows
the first handful is least helpful precisely when the row that matters is the four
hundredth, which is the moment the reader is looking.

So the bounds stop being constants and become a scope::

    with formatting(max_items=100):
        expect(rows).contains(missing)

Four rules shape everything here.

**Nothing here runs for a passing assertion.** :func:`current_formatting` is read
from a failure branch and from nowhere else, so an open scope changes what a
*failing* assertion prints and costs a passing one nothing at all -- no
``ContextVar`` read, no allocation.

**Scoping is per context, not per process.** The options in force live in a
``ContextVar``, for the reason every other piece of scoped state in the package is
one: one thread's or one asyncio task's rendering must never reach another's
messages, or a parallel run turns a fixed message into a flaky one. It is also why
there is no global setter here -- shared assertion state that each test mutates
stops being safe the moment the suite runs in parallel.

**Nesting composes.** A scope resolves against whatever is in force when it is
*entered*, so an inner block that raises ``max_items`` alone keeps the outer
block's ``max_chars``. Asking for one bound is not a request to reset the others.

**A limit is a caller's decision, and a bad one is reported.** ``max_items=0``
would announce a failure and then decline to say anything about it. That is a bug
in the test, not a rendering preference, so it raises instead of quietly doing
nothing.

Two house rules show up in the shape of the code. :class:`FormattingOptions` would
obviously be a frozen dataclass, but importing this package must not drag in
``dataclasses`` -- so ``__setattr__``, ``__delattr__``, ``__eq__``, ``__hash__``
and ``__repr__`` are written out by hand. And f-strings are confined to arguments
of ``_fail``, the one call reached only once a failure is certain; nothing here
calls it, so every message here is concatenated instead (``_formatters.py`` and
``_diff`` do the same).
"""

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatting._options import FormattingOptions
from lovely_assertions._formatting._scope import current_formatting, formatting

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = ["FormattingOptions", "current_formatting", "formatting"]
