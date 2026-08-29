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

from typing import TYPE_CHECKING

from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    import re
    from collections.abc import Callable

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = [
    "count_of",
    "holds_any",
    "holds_every",
    "length_note",
    "matches_wildcard",
    "pattern_text",
    "regex_matcher",
    "wildcard_matcher",
]


def holds_every(subject: str, values: "tuple[str, ...]", /) -> bool:
    """Whether every one of ``values`` appears in ``subject``.

    Spelled as a loop rather than ``all(value in subject for value in values)``
    because this runs on the happy path: the tidier spelling allocates a generator
    object on every *passing* call, and a passing assertion is meant to cost a
    comparison and nothing more. ``_collection._none_outside`` answers the same
    question about a collection, as the same loop, for the same reason.
    """
    for value in values:  # noqa: SIM110  (a generator expression would allocate)
        if value not in subject:
            return False
    return True


def holds_any(subject: str, values: "tuple[str, ...]", /) -> bool:
    """Whether at least one of ``values`` appears in ``subject``.

    A loop for the reason :func:`holds_every` gives.
    """
    for value in values:  # noqa: SIM110  (a generator expression would allocate)
        if value in subject:
            return True
    return False


def count_of(total: int, noun: str, /) -> str:
    """``"1 item"`` or ``"4 items"``.

    A message that says "1 items" reads as a message nobody looked at, which is
    a poor advertisement for one whose whole job is to be read.
    """
    if total == 1:
        return "1 " + noun
    return str(total) + " " + noun + "s"


def length_note(length: int, /) -> str:
    """The ``(truncated from N characters)`` tail that follows an elided value."""
    return " (truncated from " + str(length) + " characters)"


def clipped(text: str, limit: int, /) -> str:
    """Cut an over-long rendering down, saying how much was cut.

    One implementation, because two truncation tails in one message that word
    themselves differently only make the reader wonder whether they mean
    different things -- and because a bound that exists in some renderers and not
    others is the shape the collection renderer was missing when a ten-item list
    of long values produced half a megabyte.
    """
    if len(text) <= limit:
        return text
    return text[:limit] + "... (" + str(len(text) - limit) + " more characters)"


def pattern_text(pattern: "str | re.Pattern[str]", /) -> str:
    """The source text of a regex, whether it arrived compiled or not."""
    return pattern if isinstance(pattern, str) else pattern.pattern


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


def _wildcard_source(pattern: str, escape: "Callable[[str], str]", /) -> str:
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


#: Compiled wildcards, remembered between calls. Two tables rather than one keyed
#: by ``(pattern, ignoring_case)``, because that tuple would be an allocation on
#: every *passing* call and a passing assertion is allowed none. The flag is the
#: only thing that changes what a pattern means, so splitting on it leaves the
#: pattern string itself as the key -- and a string that came from the caller is
#: already allocated.
_MATCHERS: "dict[str, re.Pattern[str]]" = {}
_MATCHERS_IGNORING_CASE: "dict[str, re.Pattern[str]]" = {}

#: Cleared wholesale past this many entries in either table, the way
#: ``_subjects._LAZY_ANSWERS`` is and for the same reason -- which is also the
#: bound ``re`` puts on its own pattern cache.
#:
#: A wildcard is nearly always a literal in a test's source, so the live set is a
#: handful of patterns and this is never reached. What it protects against is the
#: suite that *builds* patterns -- ``matches_wildcard(f"{tenant}-*")`` inside a
#: loop over ten thousand tenants -- where an unbounded table would pin a compiled
#: regex per tenant for the life of the process. Clearing costs one recompile of a
#: table that is a few entries deep in practice, which is why it is a clear rather
#: than an eviction policy: an LRU needs a per-lookup write, and the lookup is the
#: thing being made cheap.
_MAX_MATCHERS = 512


#: Compiled regular expressions, keyed by whatever the caller passed. Same
#: mechanism and same bound as :data:`_MATCHERS` above, for the assertions that
#: take a pattern from the caller rather than translating a wildcard into one.
_REGEXES: "dict[str | re.Pattern[str], re.Pattern[str]]" = {}


def regex_matcher(pattern: "str | re.Pattern[str]", /) -> "re.Pattern[str]":
    """The compiled matcher for one regular expression.

    ``re.search(pattern, subject)`` is not the cheap call it looks like: it
    compiles through ``re``'s own cache, which is a lookup, a lock and a function
    call before the match begins. Measured on a passing ``matches("wor")``, a
    lookup here plus ``matcher.search`` costs less than half of ``import re`` plus
    ``re.search`` -- the assertion's own body more than halved, on the branch
    where it succeeds.

    A ``re.Pattern`` handed in maps to itself, since ``re.compile`` returns a
    compiled pattern unchanged. That costs one entry and keeps the fast path a
    single lookup for both spellings.

    The miss goes through :func:`_compile_regex` for the reason
    :func:`wildcard_matcher`'s does: an ``import re`` is still a ``sys.modules``
    probe when the module is loaded, and writing it here would put that back on
    every hit.
    """
    try:
        return _REGEXES[pattern]
    except KeyError:
        return _compile_regex(pattern)


def _compile_regex(pattern: "str | re.Pattern[str]", /) -> "re.Pattern[str]":
    """Compile one pattern and remember it. Once per pattern."""
    import re  # noqa: PLC0415  (kept off import time; only regex assertions pay for `re`)

    if len(_REGEXES) >= _MAX_MATCHERS:
        _REGEXES.clear()
    compiled = re.compile(pattern)
    _REGEXES[pattern] = compiled
    return compiled


def wildcard_matcher(pattern: str, /, *, ignoring_case: bool) -> "re.Pattern[str]":
    """The compiled matcher for one wildcard pattern, translated once.

    Hoist this above a loop when the same pattern is applied to many subjects.
    :meth:`~lovely_assertions._collection.CollectionExpect.contains_match` does,
    and that is where it was earned: without hoisting, a scan over a collection
    asks for the same matcher once per item.

    The remembering is not what makes it safe to hoist -- being a pure function
    of ``(pattern, ignoring_case)`` is. The table is what makes the *unhoisted*
    callers cheap too, ``StringExpect.matches_wildcard`` included, which is most
    of the calls.

    A miss goes through :func:`_compile_wildcard` rather than being handled here,
    so that the hot path is a dictionary lookup and nothing else. An ``import re``
    is still a ``sys.modules`` probe even when the module is already loaded, and
    measured against a function this small that probe is a sizeable fraction of
    it -- paid on every hit, for a name only the miss needs.
    """
    matchers = _MATCHERS_IGNORING_CASE if ignoring_case else _MATCHERS
    try:
        return matchers[pattern]
    except KeyError:
        return _compile_wildcard(matchers, pattern, ignoring_case=ignoring_case)


def _compile_wildcard(
    matchers: "dict[str, re.Pattern[str]]", pattern: str, /, *, ignoring_case: bool
) -> "re.Pattern[str]":
    """Translate and compile a pattern, and remember it. Once per pattern."""
    import re  # noqa: PLC0415  (kept off import time; only regex assertions pay for `re`)

    flags = re.DOTALL | re.IGNORECASE if ignoring_case else re.DOTALL
    matcher = re.compile(_wildcard_source(pattern, re.escape), flags)
    if len(matchers) >= _MAX_MATCHERS:
        matchers.clear()
    matchers[pattern] = matcher
    return matcher


def matches_wildcard(subject: str, pattern: str, /, *, ignoring_case: bool) -> bool:
    """Whether the whole of ``subject`` matches a FluentAssertions-style wildcard.

    ``*`` stands for any run of characters and ``?`` for exactly one; everything
    else is literal, so a ``.`` in the pattern is a full stop and not a regex
    metacharacter.

    ``fnmatch`` is deliberately not used, tempting as it looks. It adds ``[...]``
    character classes that a user writing ``*`` and ``?`` does not expect, and
    ``fnmatch.fnmatch`` normalises case according to the host filesystem -- an
    assertion must not mean different things on different machines. ``DOTALL`` is
    set so that "any character" includes a newline. What *is* borrowed from
    ``fnmatch`` is the shape of the translation, and only for its cost: see
    :func:`_wildcard_source`.

    One subject, one pattern. A caller with many subjects and one pattern should
    reach for :func:`wildcard_matcher` and keep the matcher across the loop --
    this function is that, written out, and the saving is in not asking for the
    matcher a hundred times rather than in the compilation, which the table
    absorbs either way.
    """
    return wildcard_matcher(pattern, ignoring_case=ignoring_case).fullmatch(subject) is not None
