"""The callable subject: what calling it does.

Two seams, and they are not symmetric. What a call *raises* is the question this
subject exists for; what it *warns* is the same question asked of the warning
machinery, and is spelled the same way so a reader who knows one knows the other.
"""

from collections.abc import Callable

from lovely_assertions._callable._raising import RaisingAssertions
from lovely_assertions._callable._warning_form import WarningFormAssertions
from lovely_assertions._core import Expect
from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


class CallableExpect(
    RaisingAssertions,
    WarningFormAssertions,
    Expect[Callable[..., object]],
):
    """Assertions about what calling the subject does.

    The subject is normally a zero-argument thunk -- ``lambda: parse("x")`` --
    because the assertion has to do the calling itself. A callable that needs
    arguments is wrapped in one; a generator function needs draining as well, and
    ``expect(lambda: list(rows()))`` is how: calling a generator function only
    builds a generator, so nothing it would raise has happened yet.

    Every assertion here calls the subject exactly once, so a chain of them calls
    it once per link -- which is what a reader wants from a thunk and what makes a
    callable with side effects worth wrapping in a fresh lambda each time.
    """

    __slots__ = ()
