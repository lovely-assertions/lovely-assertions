"""The vocabulary every failure message about a class is assembled from.

A class's name, a value clipped to what the reader will actually read, and a run
of names laid out in a sentence. Nothing here decides anything: the walk up the
MRO, the lookup in the class dictionaries and the protocol question each own a
module and hand a finding back, and this is where a finding becomes words.

One file because the bounds have to be read in one place. This is the only module
in the package that reads the formatting scope, so a block that opened
``formatting(...)`` is honoured without any of the assertion mixins remembering to
ask -- and two truncations in the same failure cannot stop at different lengths
and leave the reader wondering whether they mean different things. The mixins are
independent, no assertion calling another, so a shared rendering is what keeps
their messages sounding like one library rather than four.

:data:`MISSING` sits here rather than beside either of the two modules that use it
for the same reason: absence is what these renderings most often have to describe,
and a class that does not define a name and one that defines it as ``None`` are
different findings only for as long as both callers spell the difference the same
way.
"""

from typing import TYPE_CHECKING, Final

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._formatting import current_formatting
from lovely_assertions._text import length_note

if TYPE_CHECKING:
    from collections.abc import Sequence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Distinguishes "the class has no such attribute" from "it has one whose value
#: is ``None``". ``hasattr`` followed by ``getattr`` would answer both questions
#: at the cost of two lookups; one ``getattr`` with a sentinel answers them at the
#: cost of one.
MISSING: Final = object()


# ---------------------------------------------------------------------------
# Rendering -- failure path only.
#
# No f-strings here: an f-string is a message, a message belongs inside a `_fail`
# call, and none of these helpers may run before an assertion has already failed.
# ---------------------------------------------------------------------------
def rendered(value: object, /) -> str:
    """Render a value for a failure message, bounded by the formatting scope.

    ``max_chars`` is read here rather than frozen into a module constant, so a
    block that opened ``formatting(max_chars=...)`` gets the longer rendering it
    asked for -- and a passing assertion, which never reaches this function,
    still reads no ``ContextVar`` at all.
    """
    text = format_value(value)
    limit = current_formatting().max_chars
    if len(text) <= limit:
        return text
    return text[:limit] + "..." + length_note(len(text))


def listed(rendered: "Sequence[str]", /) -> str:
    """Lay a run of already-rendered names out in a sentence, bounded and counted.

    The bound is ``max_items`` from the scope in force, and what is left out is
    counted rather than dropped silently -- ``_callable._render_notes`` does the
    same for an exception's notes, and for the same reason: a message that
    truncates without saying so is a message the reader will trust wrongly.

    An empty run renders as the empty string; every caller here has already
    established that it has something to say before calling.
    """
    limit = current_formatting().max_items
    if len(rendered) <= limit:
        return ", ".join(rendered)
    left_out = len(rendered) - limit
    return ", ".join(rendered[:limit]) + ", ... (" + str(left_out) + " more)"


def named(candidate: object, /) -> str:
    """A class's name for a failure message.

    ``__name__`` rather than ``__qualname__``, matching ``is_instance_of`` and
    every other type named in a message in this library. Read with ``getattr``
    rather than as an attribute because a hand-built subject need not be a class
    at all, and a message must still come out.
    """
    name: str | None = getattr(candidate, "__name__", None)
    return name if isinstance(name, str) else rendered(candidate)
