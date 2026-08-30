"""A memo that forgets everything rather than choosing what to forget.

The answers here are keyed by class object, and a cache keyed on classes keeps
every class it has seen alive. A suite that builds a class per test would grow
one entry per test for the length of the run, which is a leak the test author
never wrote and cannot see.

So the bound is a total: past it the cache is emptied wholesale rather than
evicted one entry at a time. The answers are cheap to rebuild, and an eviction
policy that has to be *right* is worse than one that only has to be *bounded*.
"""

from typing import Final

from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Sentinel for a cache miss, so that a remembered ``None`` -- a real answer for
#: the callers that have one -- is told apart from nothing remembered at all.
UNCACHED: Final = object()


#: Types held in a cache before it is emptied. A cache keyed on class objects
#: keeps every class it has seen alive, and a suite that builds a class per test
#: would otherwise grow one entry per test for the length of the run. Cleared
#: wholesale rather than evicted one at a time: the answers are cheap to rebuild
#: and a policy that has to be right is worse than one that has to be bounded.
_MAX_CACHED_TYPES: Final = 4096


def remember[Answer](cache: dict[type, Answer], subject_type: type, answer: Answer, /) -> None:
    """Record one type's answer, keeping the cache bounded."""
    if len(cache) >= _MAX_CACHED_TYPES:
        cache.clear()
    cache[subject_type] = answer
