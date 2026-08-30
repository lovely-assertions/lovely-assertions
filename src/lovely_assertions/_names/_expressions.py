"""Which call in the statement built the subject, and what was written inside it.

A line can hold more than one call to :func:`expect`, and it can hold a call that
spans several lines. Deciding which one produced the subject is what separates a
message that names the reader's variable from one that names something else on
the same line -- which is worse than naming nothing, because it is confidently
wrong.

When the answer is ambiguous the honest result is no name at all. Every path here
that cannot be certain returns nothing and lets the caller fall back.
"""

from types import FrameType
from typing import TYPE_CHECKING, Any

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._names._index import index_for, source_segment

if TYPE_CHECKING:
    import ast
    from collections.abc import Iterable, Mapping

    from lovely_assertions._core import Expect
    from lovely_assertions._names._index import SourceIndex

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


_MISSING = object()


#: Calls that are known to build a subject regardless of what they resolve to.
_ENTRY_POINTS = frozenset({"expect", "expect_raises"})


def subject_expression(frame: FrameType) -> str | None:
    import ast  # noqa: PLC0415  (failure path only: this package must not import ast)
    import linecache  # noqa: PLC0415  (failure path only: this package must not import it)

    filename = frame.f_code.co_filename
    lines = linecache.getlines(filename, frame.f_globals)
    if not lines:
        # A `-c` command, a REPL, an `exec`'d string: no file, nothing to read.
        return None
    index = index_for(filename, lines)
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
    return source_segment(index.lines, arguments[0])


def _shares_its_line(
    index: "SourceIndex",
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
