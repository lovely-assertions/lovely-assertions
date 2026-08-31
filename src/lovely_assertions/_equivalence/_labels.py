"""The small renderings a report and an options object are both built out of.

Sorting a set of names, naming a comparator, spelling a computed list of members,
cutting an over-long rendering down and saying how much came off. None of it is
about equivalence, and all of it is wanted in two places: the block
:func:`compare` returns, and :meth:`Equivalency.__repr__`. The block already
reads the options -- it prints the configuration in force as its last line -- so
a helper kept beside the block would have the options importing it back, and the
two would be a cycle. These sit below both instead.

One set of names gets two functions rather than one with a flag. A message is
bounded, because the scope's ``max_items`` decides how much of a set is worth
reading; a ``repr`` is not, because Python's own reprs do not truncate and an
elided one reads like the call that built the options while not being it. So only
the message-facing half reads :func:`~lovely_assertions.current_formatting`, and
every caller of that half is on the reporting path -- the lookup is a
``ContextVar`` read, and an assertion that passes must not pay for one.

The clipping, the counting and the item rendering are ``_diff``'s conventions
rather than this engine's own, reimplemented here to the same behaviour instead
of imported: a handful of names cross out of that package, and reaching around
them for a leaf helper would tie this engine to an arrangement the diff engine is
free to change. The one that *is* shared, ``render_operand``, is reached through
:mod:`lovely_assertions._engine`, so naming it here costs no import until
something has actually failed.
"""

from typing import TYPE_CHECKING, Final

from lovely_assertions import _engine
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatting import current_formatting

if TYPE_CHECKING:
    from collections.abc import Iterable

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: One level of the block. The whole thing is indented under a one-line message,
#: the way ``_diff``'s block is.
INDENT: Final = "  "


def callable_name(comparator: object, /) -> str:
    """Name a comparator for a rendering; ``<comparator>`` when it will not say."""
    name = getattr(comparator, "__name__", None)
    if isinstance(name, str) and name != "<lambda>":
        return name
    return "<comparator>"


def render_names(names: "Iterable[str]", /) -> str:
    """A set of names for a *message*: sorted, so two runs read the same, and bounded."""
    ordered = sorted(names)
    max_items = current_formatting().max_items
    shown = [repr(name) for name in ordered[:max_items]]
    elided = len(ordered) - max_items
    if elided > 0:
        return ", ".join(shown) + ", ... (" + str(elided) + " more)"
    return ", ".join(shown)


def names_text(names: "Iterable[str]", /) -> str:
    """The same names for a ``repr``: sorted, and never elided.

    A ``repr`` is a faithful account of an object, and Python's own reprs do not
    truncate. Eliding here would produce a line that reads like the call that
    built the options and is not it.
    """
    return ", ".join(repr(name) for name in sorted(names))


def render_items(items: "tuple[object, ...]", /) -> str:
    """Render a computed list of members, truncated like every other collection."""
    max_items = current_formatting().max_items
    shown = [_engine.render_operand(item) for item in items[:max_items]]
    elided = len(items) - max_items
    if elided > 0:
        return "[" + ", ".join(shown) + ", ... (" + str(elided) + " more)]"
    return "[" + ", ".join(shown) + "]"


def clip(text: str, /) -> str:
    """Cut an over-long rendering down, saying how much was cut."""
    max_chars = current_formatting().max_chars
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "... (" + str(len(text) - max_chars) + " more characters)"
