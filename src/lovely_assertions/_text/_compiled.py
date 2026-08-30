"""The compiled patterns, and the bound on how many are kept.

Compiling is the expensive half and the same pattern is asked for in a loop, so
each table remembers what it has built. Keyed on the text, which is what the
caller wrote and what they will write again.

Bounded, and cleared wholesale rather than evicted one at a time. A suite that
builds a pattern per case would otherwise hold every one for the length of the
run, and a compiled pattern is cheap to rebuild -- this is a cache for a burst,
not a store.
"""

from typing import TYPE_CHECKING

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._text._translation import wildcard_source

if TYPE_CHECKING:
    import re

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


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


#: Compiled wildcards, remembered between calls. Two tables rather than one keyed
#: by ``(pattern, ignoring_case)``, because that tuple would be an allocation on
#: every *passing* call and a passing assertion is allowed none. The flag is the
#: only thing that changes what a pattern means, so splitting on it leaves the
#: pattern string itself as the key -- and a string that came from the caller is
#: already allocated.
_MATCHERS: "dict[str, re.Pattern[str]]" = {}


_MATCHERS_IGNORING_CASE: "dict[str, re.Pattern[str]]" = {}


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
    matcher = re.compile(wildcard_source(pattern, re.escape), flags)
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
    :func:`wildcard_source`.

    One subject, one pattern. A caller with many subjects and one pattern should
    reach for :func:`wildcard_matcher` and keep the matcher across the loop --
    this function is that, written out, and the saving is in not asking for the
    matcher a hundred times rather than in the compilation, which the table
    absorbs either way.
    """
    return wildcard_matcher(pattern, ignoring_case=ignoring_case).fullmatch(subject) is not None
