"""Whose frame asked, and which frames are the library's own.

Walking out of the stack has to stop at the first frame that is not ours, and
"ours" is not simply "in this package": an assertion a user wrote themselves and
marked with :func:`custom_assertion` is theirs by authorship and ours by
position, so the name in *their* caller's source is the one worth reporting.

The mark is a flag on the function's code object rather than a registry. A
registry would have to be consulted by identity and kept from growing; a flag
travels with the function, costs one attribute lookup, and cannot go stale.
"""

import sys
from collections.abc import Callable
from types import CodeType, FrameType
from typing import Any

from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


_PACKAGE = __name__.partition(".")[0]


#: Concatenated rather than f-string-formatted so the whole library can hold to
#: one flat rule: an f-string is a failure message, and a failure message is
#: built inside the branch that reports it, never before the branch is taken.
_PACKAGE_PREFIX = _PACKAGE + "."


#: Attribute set on callables marked with :func:`custom_assertion`.
CUSTOM_ASSERTION_FLAG = "__lovely_custom_assertion__"


#: Code objects of user assertions marked with :func:`custom_assertion`. Written
#: once, when the decorator runs at import time: library state a test could
#: mutate stops being safe the moment the runner goes parallel.
_CUSTOM_ASSERTION_CODES: set[CodeType] = set()


def custom_assertion[F: Callable[..., Any]](func: F, /) -> F:
    """Mark a user-defined assertion function so its frame is skipped when naming the subject.

    Equivalent of FluentAssertions' ``[CustomAssertion]``. Without it, an
    extension method's own frame would be treated as the caller's, and the
    failure message would name a local of the extension instead of the variable
    the test actually asserted on.

    Skipping a frame means recognising the code object behind it, so the skip
    reaches a function, a method or a lambda and nothing else. Any other
    callable -- an instance with ``__call__``, a ``functools.partial``, a
    ``staticmethod`` object -- carries the mark but has no code of its own to
    register, so its frame is not skipped and a failure raised inside it is
    named from its own body. Marking one is accepted rather than refused
    because this decorator runs at import time, where a naming nicety that
    raises would cost the whole module.

    The decorator is signature-transparent: the decorated method keeps its exact
    type, ``Self`` returns and keyword-only ``because`` included.
    """
    marked: Any = func
    setattr(marked, CUSTOM_ASSERTION_FLAG, True)
    code = getattr(marked, "__code__", None)
    if isinstance(code, CodeType):
        _CUSTOM_ASSERTION_CODES.add(code)
    return func


def caller_frame() -> FrameType | None:
    """The nearest frame that is neither ours nor a marked user assertion."""
    # `sys._getframe` is underscored but is the documented, allocation-free way
    # to walk the stack; `inspect.currentframe()` is a thin wrapper over it that
    # would drag the whole `inspect` module in on the first failure for no gain.
    frame: FrameType | None = sys._getframe(1)  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
    while frame is not None:
        module = frame.f_globals.get("__name__", "")
        ours = module == _PACKAGE or module.startswith(_PACKAGE_PREFIX)
        if not ours and frame.f_code not in _CUSTOM_ASSERTION_CODES:
            return frame
        frame = frame.f_back
    return None
