"""How a member's position in the two graphs is spelled.

A finding is worth what the string naming its location is worth, and that string
does double duty: the walk builds it while descending, the report prints it, and
the reader is expected to paste it straight back into
:meth:`Equivalency.excluding_path`. Both of this file's constraints fall out of
that. Paths are built during the walk, which is the route a *passing* comparison
takes, so nothing here reads
:func:`~lovely_assertions.current_formatting` -- whatever needs a bound gets a
constant instead. And a path is text a caller retypes, so a key is spelled by
``repr`` rather than through the formatter registry, which would otherwise let a
registered formatter print a path the API does not match.

The notation, and the one rule for matching it, are all this file owns: a dot for
a name, brackets for anything else, a phrase for the root, and the prefix rule
that decides when an excluded path takes a whole branch with it. Which members
that rule is asked about is the walk's business; nothing here compares two
values.
"""

from typing import Final

from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Characters of one rendered mapping key inside a *path*. Paths are built during
#: the walk, which is the route a *passing* assertion takes, and reading
#: ``current_formatting()`` there is a ``ContextVar`` lookup nobody who is not
#: failing should pay for -- so this bound is a constant rather than an option. A
#: key long enough to hit it cannot be addressed with
#: :meth:`Equivalency.excluding_path`; a string key is still reachable by
#: :meth:`Equivalency.excluding`, which names the key rather than the path.
_MAX_PATH_KEY_CHARS: Final = 80


#: How the root of the two graphs reads. The root has no path -- there is no
#: member to name -- and "" would render as a line beginning with a colon.
ROOT: Final = "the value itself"


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
def attribute_path(parent: str, name: str, /) -> str:
    """``user.address.city``. The root is the empty path, so it grows no leading dot."""
    if not parent:
        return name
    return parent + "." + name


def index_path(parent: str, index: int, /) -> str:
    """``items[3]``. An index has no name, so it is always bracketed."""
    return parent + "[" + str(index) + "]"


def key_path(parent: str, key: object, /) -> str:
    """``rows.id`` for a key that could be written as a name, ``rows[3]`` otherwise.

    The dot for identifier-like string keys is not sugar. A path is printed so
    that it can be pasted into :meth:`Equivalency.excluding_path`, and a reader
    holding ``{"user": {"city": ...}}`` writes ``user.city`` -- the notation is
    worth nothing if it is not the one they would have reached for. Keys that are
    not names keep their ``repr`` inside brackets, which is likewise what they
    would type.

    The cost is that ``rows.id`` no longer says whether ``id`` was a key or an
    attribute. That ambiguity is real and is accepted: the two are the same member
    to the reader, and it is exactly the case where the two notations would
    otherwise disagree about the same graph.
    """
    if isinstance(key, str) and key.isidentifier():
        return attribute_path(parent, key)
    return parent + "[" + _path_key_text(key) + "]"


def _path_key_text(key: object, /) -> str:
    """One key inside a path: its ``repr``, bounded by a constant.

    ``repr`` rather than ``format_value``, because this is text a user has to be
    able to type back: a registered formatter renders a key for a *reader*, and
    the two must not diverge in the one string the API matches against.
    """
    try:
        text = repr(key)
    # a hostile __repr__ costs the key's name, not the walk
    except Exception:
        return "<unreadable key>"
    if len(text) <= _MAX_PATH_KEY_CHARS:
        return text
    return text[:_MAX_PATH_KEY_CHARS] + "... (" + str(len(text) - _MAX_PATH_KEY_CHARS) + " more)"


def path_excluded(path: str, excluded: frozenset[str], /) -> bool:
    """Whether a path, or a branch it hangs off, was excluded.

    A prefix rule rather than an equality one: ``excluding_path("user.address")``
    excludes ``user.address.city`` with it. The character after the prefix has to
    be a separator, or ``excluding_path("user")`` would take ``username`` with it
    -- a member the caller never named, silently dropped from the comparison, and
    the one way an exclusion can turn into a wrong pass. Index paths are already
    unambiguous, because the closing bracket keeps ``items[1]`` from being a prefix
    of ``items[10]`` at all; it is names that need the rule.
    """
    if not excluded or not path:
        return False
    for candidate in excluded:
        if path == candidate:
            return True
        if path.startswith(candidate) and path[len(candidate) : len(candidate) + 1] in (".", "["):
            return True
    return False
