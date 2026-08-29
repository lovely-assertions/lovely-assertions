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

import sys
from collections.abc import Callable, Iterable, Mapping
from types import CodeType, FrameType
from typing import TYPE_CHECKING, Any

from lovely_assertions._exceptions import hide_internal_frames

if TYPE_CHECKING:
    import ast

    from lovely_assertions._core import Expect

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

#: Rendered in place of the subject name when the expression cannot be recovered
#: unambiguously.
FALLBACK_SUBJECT_NAME = "the value"

#: Attribute set on callables marked with :func:`custom_assertion`.
CUSTOM_ASSERTION_FLAG = "__lovely_custom_assertion__"

_PACKAGE = __name__.partition(".")[0]
#: Concatenated rather than f-string-formatted so the whole library can hold to
#: one flat rule: an f-string is a failure message, and a failure message is
#: built inside the branch that reports it, never before the branch is taken.
_PACKAGE_PREFIX = _PACKAGE + "."

#: Calls that are known to build a subject regardless of what they resolve to.
_ENTRY_POINTS = frozenset({"expect", "expect_raises"})

#: Code objects of user assertions marked with :func:`custom_assertion`. Written
#: once, when the decorator runs at import time: library state a test could
#: mutate stops being safe the moment the runner goes parallel.
_CUSTOM_ASSERTION_CODES: set[CodeType] = set()

#: filename -> the index built for the exact lines `linecache` last handed back.
#: Failure path only. See :class:`_SourceIndex` for why the *lines* rather than
#: the filename are what decides whether an entry is still good.
_FILE_INDEXES: dict[str, "_SourceIndex"] = {}

#: Cleared wholesale past this many files, the way `_subjects` caps its own
#: memoised answers. The cap is much tighter than that one's because an entry
#: here is much bigger: a parsed tree dwarfs the text it was parsed from, so
#: these are the largest objects the library ever retains, and a long-lived
#: process failing assertions across a whole repository would otherwise pin every
#: file it touched. Thirty-two is well past the handful of files one failing run
#: reads, and the price of overshooting it is one re-parse each of the files
#: still in play.
_MAX_FILE_INDEXES = 32

_MISSING = object()


class _SourceIndex:
    """One source file, arranged so a failure can be answered by line number.

    Three things, all derived from a single ``ast.walk``, so that no failure has
    to walk the tree itself:

    * ``lines`` -- the list ``linecache`` handed back, kept both to slice source
      text out of and, more importantly, as this entry's *identity*;
    * ``statements`` -- line number to the innermost statement spanning it, which
      is what :func:`_subject_expression` needs;
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


def custom_assertion[F: Callable[..., Any]](func: F, /) -> F:
    """Mark a user-defined assertion function so its frame is skipped when naming the subject.

    Equivalent of FluentAssertions' ``[CustomAssertion]``. Without it, an
    extension method's own frame would be treated as the caller's, and the
    failure message would name a local of the extension instead of the variable
    the test actually asserted on.

    Skipping a frame means recognising the code object behind it, so the skip
    reaches a function, a method or a lambda and nothing else. Any other
    callable -- an instance with ``__call__``, a ``functools.partial``, a
    ``staticmethod`` object -- carries the mark but has no code of its own to
    register, so its frame is not skipped and a failure raised inside it is
    named from its own body. Marking one is accepted rather than refused
    because this decorator runs at import time, where a naming nicety that
    raises would cost the whole module.

    The decorator is signature-transparent: the decorated method keeps its exact
    type, ``Self`` returns and keyword-only ``because`` included.
    """
    marked: Any = func
    setattr(marked, CUSTOM_ASSERTION_FLAG, True)
    code = getattr(marked, "__code__", None)
    if isinstance(code, CodeType):
        _CUSTOM_ASSERTION_CODES.add(code)
    return func


def resolve_subject_name() -> str | None:
    """Recover the source text of the current subject's expression.

    Returns ``None`` when the caller cannot be located, the source is
    unavailable, the statement contains anything other than exactly one
    subject-building call, or that one call was handed no positional argument:
    a subject that supplies its own value has no expression to be named by.

    **And when anything at all goes wrong**, which is the point of the guard
    rather than an apology for it. Everything below this line is a nicety: the
    caller has already failed an assertion, the message is already written, and
    all this adds is the name the reader wrote instead of
    :data:`FALLBACK_SUBJECT_NAME`. There is no failure here worth more than that
    message, and two of them cost far more.

    Unguarded, an exception raised while recovering a name *replaces* the
    ``AssertionFailure`` -- the reader is shown a traceback from this module
    where their own assertion's account of what went wrong should be. Inside a
    soft scope it is worse: the exception leaves
    :meth:`~lovely_assertions.SoftScope.__exit__` by the wrong door and every
    failure collected before it is discarded, so a block that found four
    problems reports none of them and one unrelated error.

    The rest of this module is already written as a sequence of ways to give up.
    This is the last of them, and the only one that has to hold whatever the
    interpreter is doing: ``ast.parse`` raises ``RecursionError`` rather than
    ``SyntaxError`` on deeply nested generated source, ``linecache`` can hand
    back a file that has been rewritten since the frame was captured, and a
    subject built inside ``exec`` has a filename that names nothing at all.
    """
    try:
        frame = _caller_frame()
        if frame is None:
            return None
        return _subject_expression(frame)
    # A name is never worth an assertion's message.
    except Exception:
        return None


def _caller_frame() -> FrameType | None:
    """The nearest frame that is neither ours nor a marked user assertion."""
    # `sys._getframe` is underscored but is the documented, allocation-free way
    # to walk the stack; `inspect.currentframe()` is a thin wrapper over it that
    # would drag the whole `inspect` module in on the first failure for no gain.
    frame: FrameType | None = sys._getframe(1)  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
    while frame is not None:
        module = frame.f_globals.get("__name__", "")
        ours = module == _PACKAGE or module.startswith(_PACKAGE_PREFIX)
        if not ours and frame.f_code not in _CUSTOM_ASSERTION_CODES:
            return frame
        frame = frame.f_back
    return None


def _subject_expression(frame: FrameType) -> str | None:
    import ast  # noqa: PLC0415  (failure path only: this package must not import ast)
    import linecache  # noqa: PLC0415  (failure path only: this package must not import it)

    filename = frame.f_code.co_filename
    lines = linecache.getlines(filename, frame.f_globals)
    if not lines:
        # A `-c` command, a REPL, an `exec`'d string: no file, nothing to read.
        return None
    index = _index_for(filename, lines)
    if index is None:
        return None
    line = frame.f_lineno
    statement = index.statements.get(line)
    if statement is None:
        return None

    # Both of these are asked for once per failure rather than once per node.
    # `frame.f_locals` builds a fresh proxy object on every access (PEP 667), and
    # an `import` statement is a `sys.modules` lookup plus an attribute fetch; a
    # statement of any size pays either of them a dozen times over.
    from lovely_assertions._core import Expect  # noqa: PLC0415  (breaks an import cycle)

    namespaces = (frame.f_locals, frame.f_globals, frame.f_builtins)

    chosen: ast.Call | None = None
    for node in _searchable(statement):
        if isinstance(node, ast.Call) and _is_subject_call(node, namespaces, Expect):
            if chosen is not None:
                # More than one subject in the statement: we cannot tell which
                # one failed, so do not guess.
                return None
            chosen = node
    if chosen is None:
        # We did not recognise the entry point.
        return None
    if _shares_its_line(index, line, chosen, namespaces, Expect):
        return None
    arguments = chosen.args
    if not arguments:
        return None
    return _source_segment(index.lines, arguments[0])


def _index_for(filename: str, lines: list[str], /) -> "_SourceIndex | None":
    """The index for ``lines``, building it if this file has moved or is new.

    ``lines is index.lines`` rather than ``==``: see :class:`_SourceIndex`. The
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

    index = _SourceIndex(lines, statements, calls)
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


def _shares_its_line(
    index: "_SourceIndex",
    line: int,
    chosen: "ast.Call",
    namespaces: "tuple[Mapping[str, Any], ...]",
    base: "type[Expect[Any]]",
    /,
) -> bool:
    """Whether another subject-building call starts on the reporting line.

    The index returns the *innermost* statement spanning the line, and two
    statements separated by a semicolon both span zero lines -- so the first one
    wins a tie it should never have been allowed to win. Unguarded, the name that
    comes out is not merely unhelpful but wrong:

        expect(first).is_equal_to(2); expect(second).is_equal_to(1)
        -> "Expected first to equal 1, but was 3"

    where the subject is ``second``. A confidently wrong name is worse than no
    name at all, so a second candidate on the line means the answer is ambiguous
    and :data:`FALLBACK_SUBJECT_NAME` is used instead.

    Only calls *starting* on the reporting line count. A statement broken over
    several lines has its ``expect(`` on one of them and nothing else there, so
    the common multi-line case is untouched.
    """
    found = 0
    for node in index.calls.get(line, ()):
        if node is chosen or _is_subject_call(node, namespaces, base):
            found += 1
            if found > 1:
                return True
    return False


def _searchable(statement: "ast.stmt", /) -> "Iterable[ast.AST]":
    """The part of ``statement`` that can hold the subject.

    Normally the whole statement. A ``with`` block is the exception: a context
    manager reports its failure on the way out, so the frame's line is the
    ``with`` header while the body may span a hundred lines of ordinary
    assertions. Walking all of it would find every ``expect(...)`` in the body,
    call the answer ambiguous, and fall back to "the value" -- turning

        Expected ValueError to be raised, but nothing was raised.

    into a sentence that names nothing. The header is a different statement from
    the body for naming purposes, so only the items are searched.
    """
    import ast  # noqa: PLC0415  (failure path only: this package must not import ast)

    if isinstance(statement, ast.With | ast.AsyncWith):
        return [node for item in statement.items for node in ast.walk(item)]
    return ast.walk(statement)


def _source_segment(lines: list[str], node: "ast.expr", /) -> str | None:
    """The source text of ``node``, sliced straight out of ``linecache``'s lines.

    ``ast.get_source_segment`` does exactly this, but it takes the whole file as
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


def _is_subject_call(
    call: "ast.Call",
    namespaces: "tuple[Mapping[str, Any], ...]",
    base: "type[Expect[Any]]",
    /,
) -> bool:
    """Whether ``call`` produces a subject.

    Two things qualify: the library's own entry points, and any call to something
    that resolves, in the caller's own namespaces, to an ``Expect`` subclass. The
    second case is what makes name recovery work for an extension subject
    constructed directly, which is how the extension API is meant to be used.
    """
    import ast  # noqa: PLC0415  (failure path only: this package must not import ast)

    func = call.func
    if isinstance(func, ast.Name):
        name = func.id
    elif isinstance(func, ast.Attribute):
        name = func.attr
    else:
        return False
    if name in _ENTRY_POINTS:
        return True
    for namespace in namespaces:
        target = namespace.get(name, _MISSING)
        if target is not _MISSING:
            return isinstance(target, type) and issubclass(target, base)
    return False
