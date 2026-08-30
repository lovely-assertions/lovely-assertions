"""Subject-name recovery: the Python answer to C#'s ``[CallerArgumentExpression]``.

Every function in this module runs on the **failure path only**. ``ast`` and
``linecache`` are therefore imported lazily, inside the functions that need them,
never at module level, so that importing this package imports neither of them.

The strategy: at failure time, walk out of the package to the caller's frame,
parse the statement being executed, and return the expression that was handed to
the call which built the subject. Zero or several candidates means the answer is
ambiguous, and an ambiguous answer would be a *wrong* name in a failure message,
so we say ``the value`` instead.

**What a failure is allowed to cost.** Recovering the name is the expensive half
of a failure, and the cost has to stay proportional to the *statement* rather
than to the caller's file. Joining the file back into one string, comparing it
against a cached copy, walking its whole tree, and re-splitting it to slice out a
source segment are each a full pass over the module -- and a failing assertion in
a very large test file pays them all again, as does every one of the failures a
soft scope collects out of that file. Nothing about naming one expression needs
to look at the rest of the file, so :class:`_SourceIndex` does that work once per
file and answers by line number afterwards; see it for how staleness is handled,
which is the only part of this that is delicate.
"""

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._names._frames import CUSTOM_ASSERTION_FLAG, custom_assertion
from lovely_assertions._names._resolution import FALLBACK_SUBJECT_NAME, resolve_subject_name

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = [
    "CUSTOM_ASSERTION_FLAG",
    "FALLBACK_SUBJECT_NAME",
    "custom_assertion",
    "resolve_subject_name",
]
