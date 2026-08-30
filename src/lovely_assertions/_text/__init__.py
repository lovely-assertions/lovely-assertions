"""Text rendering and matching shared between subjects.

One question, one answer. FluentAssertions' wildcard reaches this library through
both :meth:`~lovely_assertions.StringExpect.matches_wildcard` and
:meth:`~lovely_assertions.CollectionExpect.contains_match`, and a library that
answers the same question differently depending on which subject you asked is
worse than one that answers it badly. So the wildcard translation, the compiled
matcher tables, the truncation tail and the regex-source helper live here, once,
and every subject that needs them reaches for the same one.

Nothing here is an assertion and nothing here builds a whole message: this module
hands back booleans, compiled patterns and message *fragments*, and the subject
modules assemble the sentence. It is also where the regex engine is kept off
import time -- every ``import re`` sits inside the branch that compiles, so a
suite that never writes a pattern never pays for the module.
"""

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._text._compiled import (
    matches_wildcard,
    regex_matcher,
    wildcard_matcher,
)
from lovely_assertions._text._fragments import (
    clipped,
    count_of,
    holds_any,
    holds_every,
    length_note,
    pattern_text,
)

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = [
    "clipped",
    "count_of",
    "holds_any",
    "holds_every",
    "length_note",
    "matches_wildcard",
    "pattern_text",
    "regex_matcher",
    "wildcard_matcher",
]
