"""One source file, arranged so a failure can be answered by line number.

The file is parsed once and every call in it filed under the line it starts on,
because the question asked here is always "which call is on line N" and answering
it by walking the tree each time would pay for the whole file per assertion.

Bounded, and cleared wholesale when it is full. A suite that generates modules
would otherwise hold every one of them parsed for the length of the run, and the
index is cheap to rebuild -- this is a cache for a burst of failures in one file,
not a store.
"""

from typing import TYPE_CHECKING

from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    import ast

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


#: Cleared wholesale past this many files, the way `_subjects` caps its own
#: memoised answers. The cap is much tighter than that one's because an entry
#: here is much bigger: a parsed tree dwarfs the text it was parsed from, so
#: these are the largest objects the library ever retains, and a long-lived
#: process failing assertions across a whole repository would otherwise pin every
#: file it touched. Thirty-two is well past the handful of files one failing run
#: reads, and the price of overshooting it is one re-parse each of the files
#: still in play.
_MAX_FILE_INDEXES = 32


#: filename -> the index built for the exact lines `linecache` last handed back.
#: Failure path only. See :class:`SourceIndex` for why the *lines* rather than
#: the filename are what decides whether an entry is still good.
_FILE_INDEXES: dict[str, "SourceIndex"] = {}


class SourceIndex:
    """One source file, arranged so a failure can be answered by line number.

    Three things, all derived from a single ``ast.walk``, so that no failure has
    to walk the tree itself:

    * ``lines`` -- the list ``linecache`` handed back, kept both to slice source
      text out of and, more importantly, as this entry's *identity*;
    * ``statements`` -- line number to the innermost statement spanning it, which
      is what :func:`subject_expression` needs;
    * ``calls`` -- line number to the calls *starting* on it, which is what
      :func:`_shares_its_line` needs.

    **Why the identity of the line list is the cache key.** The lines are already
    ``linecache``'s to invalidate: it re-reads a file only when
    ``linecache.checkcache`` notices the size or mtime moved, and it hands back a
    brand-new list when it does. Keying on that list -- by identity, with a
    strong reference so the identity cannot be recycled onto some other list --
    means this cache is stale exactly when ``linecache`` is stale and never a
    moment longer, which is the same guarantee the tracebacks printed next to the
    message already carry. Comparing the source text instead would buy nothing
    over that and would cost a full-file join and a full-file compare on every
    single failure.
    """

    __slots__ = ("calls", "lines", "statements")

    def __init__(
        self,
        lines: list[str],
        statements: "dict[int, ast.stmt]",
        calls: "dict[int, list[ast.Call]]",
        /,
    ) -> None:
        self.lines = lines
        self.statements = statements
        self.calls = calls


def index_for(filename: str, lines: list[str], /) -> "SourceIndex | None":
    """The index for ``lines``, building it if this file has moved or is new.

    ``lines is index.lines`` rather than ``==``: see :class:`SourceIndex`. The
    read and the write are each a single dict operation, so two threads failing
    in the same file at once either share one index or build two identical ones
    and keep the last -- both correct, and cheaper than holding a lock across a
    parse.
    """
    import ast  # noqa: PLC0415  (failure path only: this package must not import ast)

    index = _FILE_INDEXES.get(filename)
    if index is not None and index.lines is lines:
        return index
    try:
        tree = ast.parse("".join(lines))
    # What ``linecache`` hands back is not guaranteed to be the Python that
    # ran: with no file on disk it answers from the module's ``__loader__``, and
    # a loader for generated or packed code can return text that does not parse.
    except SyntaxError:
        return None

    statements: dict[int, ast.stmt] = {}
    calls: dict[int, list[ast.Call]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            calls.setdefault(node.lineno, []).append(node)
            continue
        if not isinstance(node, ast.stmt):
            continue
        end = node.end_lineno
        if end is None:
            continue
        # Innermost, not first: a chained call broken over several lines belongs
        # to one statement, and that whole statement is the right place to look
        # for the subject -- but a nested function body should not swallow its
        # enclosing `def`. `ast.walk` is breadth-first, so among statements of
        # equal span the outer one is seen first and keeps the line; that is what
        # gives `if x: y = 1` the `if` and two statements on one line the first,
        # and `_shares_its_line` is the guard on that second case.
        span = end - node.lineno
        for lineno in range(node.lineno, end + 1):
            incumbent = statements.get(lineno)
            if incumbent is None or span < _span(incumbent):
                statements[lineno] = node

    index = SourceIndex(lines, statements, calls)
    if len(_FILE_INDEXES) >= _MAX_FILE_INDEXES:
        _FILE_INDEXES.clear()
    _FILE_INDEXES[filename] = index
    return index


def _span(statement: "ast.stmt", /) -> int:
    """How many lines past its first ``statement`` runs.

    Only ever asked of a statement already in the index, and nothing gets in
    there with an unset ``end_lineno``; the branch is what tells the checkers so.
    """
    end = statement.end_lineno
    if end is None:  # pragma: no cover - filtered out on the way in
        return 0
    return end - statement.lineno


def source_segment(lines: list[str], node: "ast.expr", /) -> str | None:
    """The source text of ``node``, sliced straight out of ``linecache``'s lines.

    ``ast.getsource_segment`` does exactly this, but it takes the whole file as
    a string and re-splits it into lines on every call, which made naming one
    argument cost a pass over the module. The lines are already split -- that is
    what ``linecache`` stores -- and they are the same lines the parser saw,
    because the tree was parsed from their join and ``linecache`` has already
    translated every newline convention to ``\\n``.

    ``col_offset`` counts *bytes*, not characters, so a line carrying anything
    outside ASCII has to be encoded before it can be cut. ``str.isascii`` reads a
    flag on the string object rather than scanning it, so the common line pays
    nothing for the check.

    Failure path only.
    """
    end_lineno = node.end_lineno
    end_col = node.end_col_offset
    if end_lineno is None or end_col is None:  # pragma: no cover - set by the parser
        return None
    first = node.lineno - 1
    last = end_lineno - 1
    line = lines[first]
    if first == last:
        if line.isascii():
            return line[node.col_offset : end_col]
        return line.encode()[node.col_offset : end_col].decode()
    head = line[node.col_offset :] if line.isascii() else line.encode()[node.col_offset :].decode()
    tail = lines[last]
    tail = tail[:end_col] if tail.isascii() else tail.encode()[:end_col].decode()
    return "".join([head, *lines[first + 1 : last], tail])
