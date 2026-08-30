"""Turning a wildcard into regular-expression source, safely.

``*`` and ``?`` are what a reader means by a pattern nine times in ten, and they
are not a regex -- so the caller's text is escaped whole and only the two
metacharacters are put back. Escaping first is the point: a caller who writes a
``.`` means a full stop, and a translation that let it through would match any
character and pass a test that ought to fail.

``*`` becomes a lazy any-run rather than a greedy one, because a greedy run
backtracks over the whole string for every following literal and a pattern with
several of them turns a failing assertion into a hang.
"""

from typing import TYPE_CHECKING

from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    from collections.abc import Callable

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


def _literal_source(segment: str, escape: "Callable[[str], str]", /) -> str:
    """One ``*``-free run of a wildcard pattern, as regex source.

    ``?`` is the only thing left in here with a meaning of its own; everything
    else, ``.`` and ``[`` included, is escaped down to itself. ``escape`` is
    ``re.escape``, handed in rather than imported so that every ``import re`` in
    this module stays inside a function that compiles, and the regex engine stays
    off import time.
    """
    if "?" not in segment:
        return escape(segment)
    return ".".join([escape(run) for run in segment.split("?")])


def wildcard_source(pattern: str, escape: "Callable[[str], str]", /) -> str:
    """A regex source for ``pattern`` that no subject can make backtrack.

    Translating every ``*`` to a bare ``.*`` is correct and catastrophic. On a
    pattern that ultimately *fails*, each ``.*`` re-tries every split of the text
    that the next one has already rejected, so the work doubles with every added
    wildcard: a pattern carrying a handful of them stops answering at all against
    a subject only a few dozen characters long. ``_collection.contains_match``
    pays that per item, which turns a collection assertion into what looks, from
    the outside, like an infinite loop in the caller's own code.

    Two things from ``fnmatch.translate``'s construction remove it, and neither
    changes what a pattern means:

    * Consecutive ``*`` collapse into one. A run of them says nothing that a
      single one does not.
    * Every ``*`` but the last is emitted as an atomic group over the literal run
      that follows it -- ``(?>.*?abc)`` -- which commits to the *first* ``abc``
      and forbids the engine from ever coming back for a later one.

    That commitment is safe precisely because whatever follows an interior ``*``
    group starts with another ``*``: if a match exists with the run placed later,
    the same match exists with it placed at the first opportunity, because the
    next ``*`` absorbs the difference. Only the final ``*`` is left free to
    backtrack, and one free ``.*`` is linear, not exponential.
    """
    segments = pattern.split("*")
    final = len(segments) - 1
    if final == 0:
        return _literal_source(pattern, escape)
    head = _literal_source(segments[0], escape)
    tail = _literal_source(segments[final], escape)
    if final == 1:
        return head + ".*" + tail
    translated: list[str] = [head]
    for index in range(1, final):
        segment = segments[index]
        if segment:
            translated.append("(?>.*?" + _literal_source(segment, escape) + ")")
    translated.append(".*")
    translated.append(tail)
    return "".join(translated)
