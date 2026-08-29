"""Recovering the subject's name from the caller's source.

The Python answer to ``[CallerArgumentExpression]``: at failure time, walk out of
the package, parse the caller's statement, and report the expression that was
handed to ``expect(...)``. When that is ambiguous, say ``the value`` rather than
guess.
"""

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Self, cast

import pytest

from lovely_assertions import (
    AssertionFailure,
    Expect,
    _names,
    custom_assertion,
    expect,
    expect_raises,
    soft_assertions,
)


def test_simple_variable() -> None:
    balance = 4
    with pytest.raises(AssertionFailure) as caught:
        expect(balance).is_equal_to(3)
    assert "Expected balance " in str(caught.value)


def test_attribute_path_is_kept_verbatim() -> None:
    class Account:
        balance = 4

    account = Account()
    with pytest.raises(AssertionFailure) as caught:
        expect(account.balance).is_equal_to(3)
    assert "Expected account.balance " in str(caught.value)


def test_call_expression_is_kept_verbatim() -> None:
    values = [1, 2, 3]
    with pytest.raises(AssertionFailure) as caught:
        expect(len(values)).is_equal_to(4)
    assert "Expected len(values) " in str(caught.value)


def test_subscript_is_kept_verbatim() -> None:
    rows = {"a": 1}
    with pytest.raises(AssertionFailure) as caught:
        expect(rows["a"]).is_equal_to(2)
    assert 'Expected rows["a"] ' in str(caught.value)


def test_multiline_statement_is_handled() -> None:
    balance = 4
    with pytest.raises(AssertionFailure) as caught:
        expect(
            balance,
        ).is_equal_to(
            3,
        )
    assert "Expected balance " in str(caught.value)


def test_two_expects_on_one_statement_fall_back() -> None:
    """Ambiguous means ambiguous. Guessing here would produce a wrong name."""
    left = 4
    right = 5
    with pytest.raises(AssertionFailure) as caught:
        expect(left).is_equal_to(expect(right).subject)
    assert "Expected the value " in str(caught.value)


def test_fallback_when_source_is_unavailable() -> None:
    """Sources compiled from a string have no file to parse."""
    namespace: dict[str, object] = {"expect": expect}
    code = compile("expect(4).is_equal_to(3)", "<generated>", "exec")
    with pytest.raises(AssertionFailure) as caught:
        exec(code, namespace)  # noqa: S102
    assert "Expected the value " in str(caught.value)


# ---------------------------------------------------------------------------
# @custom_assertion: the extension's own frame must not be named as the subject
# ---------------------------------------------------------------------------
class AccountExpect(Expect[int]):
    __slots__ = ()

    @custom_assertion
    def is_solvent(self, *, because: str = "") -> Self:
        if self._subject >= 0:
            return self
        return self._fail(f"to be solvent, but was {self._subject}", because)

    def is_solvent_unmarked(self, *, because: str = "") -> Self:
        if self._subject >= 0:
            return self
        return self._fail(f"to be solvent, but was {self._subject}", because)


def test_custom_assertion_names_the_callers_variable() -> None:
    balance = -4
    with pytest.raises(AssertionFailure) as caught:
        AccountExpect(balance).is_solvent()
    assert str(caught.value) == "Expected balance to be solvent, but was -4."


def test_custom_assertion_is_signature_transparent() -> None:
    """The decorator must not eat ``because`` or change the return value."""
    subject = AccountExpect(1)
    assert subject.is_solvent(because="it should be") is subject


def test_decorator_marks_the_function() -> None:
    assert getattr(AccountExpect.is_solvent, "__lovely_custom_assertion__", False) is True
    assert getattr(AccountExpect.is_solvent_unmarked, "__lovely_custom_assertion__", False) is False


def test_a_marked_callable_with_no_code_object_is_still_marked() -> None:
    """A user assertion need not be a function, and one that is not must not raise.

    An object with ``__call__`` carries no ``__code__`` of its own, so there is
    nothing to register and its frame is not skipped: the message names
    ``amount``, the helper's own parameter, rather than the caller's expression.
    Marking it still has to be accepted -- a decorator runs at import time, and a
    naming nicety that can break a module there is worse than no name.
    """

    class Solvency:
        def __call__(self, amount: int) -> None:
            AccountExpect(amount).is_solvent()

    marked = custom_assertion(Solvency())

    assert getattr(marked, _names.CUSTOM_ASSERTION_FLAG, False) is True
    with pytest.raises(AssertionFailure) as caught:
        marked(-4)

    assert str(caught.value) == "Expected amount to be solvent, but was -4."


def test_a_marked_partial_does_not_mark_the_function_it_wraps() -> None:
    """Marking a wrapper marks nothing that actually runs.

    ``functools.partial`` carries no ``__code__`` of its own, and the frame that
    would have to be skipped is not even the partial's: the assertion runs in
    the wrapped function, which was never marked. So the message names
    ``amount``, that function's parameter, rather than the caller's expression.
    """
    import functools

    def solvency(amount: int) -> None:
        AccountExpect(amount).is_solvent()

    marked = custom_assertion(functools.partial(solvency))

    assert getattr(marked, _names.CUSTOM_ASSERTION_FLAG, False) is True
    with pytest.raises(AssertionFailure) as caught:
        marked(-4)

    assert str(caught.value) == "Expected amount to be solvent, but was -4."


def test_nested_custom_assertions_are_all_skipped() -> None:
    class Nested(Expect[int]):
        __slots__ = ()

        @custom_assertion
        def outer(self) -> Self:
            return self.inner()

        @custom_assertion
        def inner(self) -> Self:
            return self._fail("to pass", "")

    balance = 1
    with pytest.raises(AssertionFailure) as caught:
        Nested(balance).outer()
    assert str(caught.value) == "Expected balance to pass."


# ---------------------------------------------------------------------------
# A `with` block reports on the way out, so its header is what gets named
# ---------------------------------------------------------------------------
def test_a_context_manager_is_named_from_its_header_not_its_body() -> None:
    """The body may hold assertions of its own; they must not make it ambiguous.

    ``expect_raises`` reports its failure during ``__exit__``, when the frame's
    line is the ``with`` header. The search has to stay inside that header: take
    the body in as well and every ``expect(...)`` in it counts as one more
    candidate, the answer is called ambiguous, and the message degrades to
    ``Expected the value to be raised, but nothing was raised`` -- a sentence
    that names nothing at all.
    """
    # Deliberately nested rather than combined: a lone `expect_raises` header is
    # the shape under test, and merging the two would put a second item in it.
    with pytest.raises(AssertionFailure) as caught:  # noqa: SIM117
        with expect_raises(ValueError):
            expect(1).is_equal_to(1)
            expect("x").is_equal_to("x")
    assert str(caught.value) == "Expected ValueError to be raised, but nothing was raised."


def test_a_context_manager_with_an_empty_body_is_named_the_same_way() -> None:
    with pytest.raises(AssertionFailure) as caught:  # noqa: SIM117
        with expect_raises(KeyError):
            pass
    assert str(caught.value) == "Expected KeyError to be raised, but nothing was raised."


# ---------------------------------------------------------------------------
# The per-file index: a failure must cost the same in any size of file
#
# Naming a subject means parsing the caller's module, so that work is done once
# per file and answered by line number afterwards -- rather than re-reading it,
# re-joining it, walking the whole tree twice and re-splitting inside
# `ast.get_source_segment` on every failure. These tests hold the two halves of
# that: the answers never change, and the cost does not follow the size of the file.
# ---------------------------------------------------------------------------
def _padded(padding: int, name: str = "balance") -> str:
    """A module whose failing statement sits under ``padding`` lines of padding.

    Real statements rather than comments, because one of the two costs guarded
    against here is counted in tree nodes, and comments produce none.
    """
    return "".join(
        [
            *(f"padding_{i} = {i}\n" for i in range(padding)),
            "def run() -> None:\n",
            f"    {name} = 4\n",
            f"    expect({name}).is_equal_to(3)\n",
        ]
    )


def _compiled(path: Path, source: str) -> Callable[[], None]:
    """Write ``source`` to ``path`` and return its ``run`` as the file would run it.

    ``linecache.checkcache`` after the write is not tidiness: it is the call that
    a rendered traceback makes, and it is what makes ``linecache`` notice a file
    it has already read has moved. The index keys on the lines ``linecache``
    hands back, so this is also what makes the index notice.
    """
    import linecache

    path.write_text(source)
    linecache.checkcache(str(path))
    namespace: dict[str, object] = {"expect": expect}
    exec(compile(source, str(path), "exec"), namespace)  # noqa: S102
    return cast("Callable[[], None]", namespace["run"])


def _message(run: Callable[[], None]) -> str:
    with pytest.raises(AssertionFailure) as caught:
        run()
    return str(caught.value)


def test_an_edited_file_is_named_from_what_it_says_now(tmp_path: Path) -> None:
    """The whole risk of caching a parse: an edited file must not be served stale."""
    path = tmp_path / "edited.py"
    assert "Expected balance " in _message(_compiled(path, _padded(0, "balance")))
    assert "Expected holdings " in _message(_compiled(path, _padded(7, "holdings")))
    # And back again, to a file shorter than the one just indexed.
    assert "Expected balance " in _message(_compiled(path, _padded(0, "balance")))


def test_the_index_is_keyed_on_the_lines_linecache_handed_back(tmp_path: Path) -> None:
    """Not on the filename, and not on the text: on the list itself, by identity.

    That key is what ties this cache's staleness to ``linecache``'s own, so the
    name in the message and the source line in the traceback beside it can never
    disagree about which version of the file they are describing.
    """
    import linecache

    from lovely_assertions._names import (
        _FILE_INDEXES,  # pyright: ignore[reportPrivateUsage]
    )

    path = tmp_path / "keyed.py"
    _message(_compiled(path, _padded(0, "balance")))
    first = _FILE_INDEXES[str(path)]
    assert first.lines is linecache.getlines(str(path))

    _message(_compiled(path, _padded(7, "holdings")))
    second = _FILE_INDEXES[str(path)]
    assert second is not first
    assert second.lines is linecache.getlines(str(path))


def test_a_file_that_vanishes_falls_back_rather_than_raising(tmp_path: Path) -> None:
    """A deleted source is a missing name, never a crash on top of a failure."""
    import linecache

    path = tmp_path / "doomed.py"
    run = _compiled(path, _padded(0, "balance"))
    assert "Expected balance " in _message(run)

    path.unlink()
    linecache.checkcache(str(path))
    assert "Expected the value " in _message(run)


@pytest.mark.parametrize(
    ("label", "filename"),
    [
        ("a -c command", "-c"),
        ("a REPL line", "<stdin>"),
        ("an exec'd string", "<string>"),
    ],
)
def test_sources_with_no_file_behind_them_fall_back(label: str, filename: str) -> None:
    """``python -c``, the REPL and ``exec`` have nothing on disk to name from."""
    namespace: dict[str, object] = {"expect": expect}
    code = compile("expect(4).is_equal_to(3)", filename, "exec")
    with pytest.raises(AssertionFailure) as caught:
        exec(code, namespace)  # noqa: S102
    assert "Expected the value " in str(caught.value), label


def test_two_threads_failing_in_the_same_file_both_get_their_own_name(
    tmp_path: Path,
) -> None:
    """Building an index is unsynchronised, so both threads may build one.

    Losing that race costs a duplicated parse and nothing else -- the two indexes
    describe the same lines -- which is why there is no lock here to be held
    across a parse.
    """
    import threading

    from lovely_assertions._names import (
        _FILE_INDEXES,  # pyright: ignore[reportPrivateUsage]
    )

    path = tmp_path / "threaded.py"
    source = (
        *(f"# padding line {i}\n" for i in range(400)),
        "def run_left() -> None:\n",
        "    left = 4\n",
        "    expect(left).is_equal_to(3)\n",
        "\n",
        "def run_right() -> None:\n",
        "    right = 5\n",
        "    expect(right).is_equal_to(3)\n",
    )
    path.write_text("".join(source))
    namespace: dict[str, object] = {"expect": expect}
    exec(compile("".join(source), str(path), "exec"), namespace)  # noqa: S102
    _FILE_INDEXES.pop(str(path), None)

    barrier = threading.Barrier(2)
    seen: dict[str, set[str]] = {"left": set(), "right": set()}

    def hammer(key: str) -> None:
        run = cast("Callable[[], None]", namespace[f"run_{key}"])
        barrier.wait()
        for _ in range(50):
            seen[key].add(_message(run))

    threads = [threading.Thread(target=hammer, args=(key,)) for key in seen]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert seen["left"] == {"Expected left to equal 3, but was 4."}
    assert seen["right"] == {"Expected right to equal 3, but was 5."}


def test_the_index_cache_is_bounded(tmp_path: Path) -> None:
    """A session failing across thousands of files must not pin all of them.

    Parsed modules are the largest objects this library retains, so the cap is
    tight and, like ``_subjects._SHAPE_ANSWERS``, it clears wholesale rather than
    evicting: the cost of overshooting is a re-parse, not a wrong answer.
    """
    from lovely_assertions._names import (
        _FILE_INDEXES,  # pyright: ignore[reportPrivateUsage]
        _MAX_FILE_INDEXES,  # pyright: ignore[reportPrivateUsage]
        _index_for,  # pyright: ignore[reportPrivateUsage]
    )

    _FILE_INDEXES.clear()
    try:
        for i in range(_MAX_FILE_INDEXES * 2 + 3):
            assert _index_for(f"<synthetic {i}>", ["value = 1\n"]) is not None
            assert len(_FILE_INDEXES) <= _MAX_FILE_INDEXES
    finally:
        _FILE_INDEXES.clear()
    # Still usable afterwards -- clearing loses work, never correctness.
    assert "Expected balance " in _message(_compiled(tmp_path / "after.py", _padded(0)))


def test_a_statement_the_parser_could_not_place_costs_only_itself(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One unplaceable statement must not take the whole file's names with it.

    The index is a line-number table, and it is built by subtracting one
    position from another. A statement carrying no end position has no lines to
    file itself under, so it is dropped; fold it in instead and the subtraction
    raises, the guard around name recovery turns that into no name at all, and
    every assertion in the file reports ``the value`` because of one statement
    nobody asked about.

    CPython's parser places every statement it produces, so the tree here is
    doctored to carry one that is not placed -- the shape a generated or
    rewritten tree can have, and the only thing the branch is there for.
    """
    import ast

    real_parse = ast.parse

    def parse_leaving_the_first_statement_unplaced(source: str) -> ast.Module:
        tree = real_parse(source)
        tree.body[0].end_lineno = None
        return tree

    run = _compiled(
        tmp_path / "unplaced.py",
        "marker = 1\ndef run() -> None:\n    balance = 4\n    expect(balance).is_equal_to(3)\n",
    )

    monkeypatch.setattr(ast, "parse", parse_leaving_the_first_statement_unplaced)
    try:
        # Undone before anything is asserted: pytest parses the source of a
        # failing test to report it, so a stub left standing would answer that
        # call too and bury the assertion under an error from inside the runner.
        message = _message(run)
    finally:
        monkeypatch.undo()

    assert message == "Expected balance to equal 3, but was 4."


def test_a_recovered_segment_matches_the_stdlib_it_replaces(tmp_path: Path) -> None:
    """``_source_segment`` is ``ast.get_source_segment`` without the re-split.

    Held against the original over a file chosen to break a naive slice: CRLF
    endings, characters outside ASCII (``col_offset`` counts bytes), expressions
    spanning several lines with and without ASCII at the two ends of them, and no
    newline at the end.
    """
    import ast
    import linecache

    from lovely_assertions._names import (
        _source_segment,  # pyright: ignore[reportPrivateUsage]
    )

    path = tmp_path / "awkward.py"
    path.write_bytes(
        (
            "accent = 'éé'\r\n"
            "def widen(rows):\r\n"
            "    return [\r\n"
            "        'ü' + row\r\n"
            "        for row in rows\r\n"
            "    ]\r\n"
            "banner = ('é'\r\n"
            "          'ü' + accent)\r\n"
            "total = widen(['a', 'é']) + [accent, banner, 'ü' * 3]"
        ).encode()
    )
    linecache.checkcache(str(path))
    lines = linecache.getlines(str(path))
    joined = "".join(lines)
    tree = ast.parse(joined)

    compared = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.expr):
            continue
        compared += 1
        assert _source_segment(lines, node) == ast.get_source_segment(joined, node)
    assert compared >= 20


def test_a_failure_reads_only_its_own_statement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Counted rather than timed, so it says the same thing on a loaded machine.

    Both files are failed in once first, which is what builds their index; from
    then on a failure walks the statement it is standing on and nothing else, so
    the node count is identical in a twenty-line file and a five-thousand-line
    one. Walk the whole module instead and this number tracks the size of the
    file, which is exactly what the two sizes here exist to expose.
    """
    import ast

    small = _compiled(tmp_path / "small_counted.py", _padded(20))
    large = _compiled(tmp_path / "large_counted.py", _padded(5000))
    _message(small)
    _message(large)

    visited = 0
    real_walk = ast.walk

    def counting_walk(node: ast.AST) -> Iterator[ast.AST]:
        nonlocal visited
        for child in real_walk(node):
            visited += 1
            yield child

    monkeypatch.setattr(ast, "walk", counting_walk)

    _message(small)
    small_nodes = visited
    visited = 0
    _message(large)
    large_nodes = visited

    assert small_nodes > 0
    assert large_nodes == small_nodes


def test_a_failure_costs_the_same_in_a_large_file_as_in_a_small_one(
    tmp_path: Path,
) -> None:
    """The counted invariant, confirmed on the clock once.

    The bound is deliberately loose -- four times, for two files whose real cost
    is the same -- because this runs on whatever machine the suite runs on. A
    failure that re-read the whole module would put these two orders of magnitude
    apart, so the margin is not what makes this test pass.
    """
    import timeit

    small = _compiled(tmp_path / "small_timed.py", _padded(20))
    large = _compiled(tmp_path / "large_timed.py", _padded(5000))

    def swallow(run: Callable[[], None]) -> None:
        try:
            run()
        except AssertionFailure:
            return

    for run in (small, large):
        swallow(run)  # warm the index and linecache

    best_small = min(timeit.repeat(lambda: swallow(small), number=20, repeat=5))
    best_large = min(timeit.repeat(lambda: swallow(large), number=20, repeat=5))
    assert best_large < best_small * 4, (best_small, best_large)


# ---------------------------------------------------------------------------
# Ambiguity, the other half of naming: zero or more than one candidate -> `the value`
#
# Two guards implement that rule. `_shares_its_line` reads a dict of calls keyed on
# the line each one *starts* on; the candidate loop stops at the second subject it
# finds rather than collecting them all and counting. Both are easy to get wrong in
# a way nothing else in the suite can see -- key those calls on the line they *end*
# on, or wait for a third call before calling a line ambiguous, and every test stays
# green while the message states a confidently wrong name. These four pin the shapes
# that separate a working version from a broken one.
# `test_two_expects_on_one_statement_fall_back` above does not: both of its calls
# start on the same line, so `_shares_its_line` answers it before the candidate loop
# is ever consulted.
#
# The literal layout is the subject under test here, hence `fmt: off` -- the
# formatter would rewrite every one of these lines into the case that already
# passes.
# ---------------------------------------------------------------------------
# fmt: off
def test_two_statements_on_one_line_fall_back() -> None:
    """The wrong-name case `_shares_its_line` exists for, in its own words.

    The reporting line carries two whole statements, both spanning zero lines, so
    the index's smallest-span rule has no way to prefer the right one and hands
    back whichever it saw first. Naming from it would report `first` when the
    failure is `second`'s, or the reverse. There is no honest answer, so there is
    no name.
    """
    first = 3
    second = 3
    with pytest.raises(AssertionFailure) as caught:
        expect(first).is_equal_to(2); expect(second).is_equal_to(1)  # noqa: E702
    assert str(caught.value) == "Expected the value to equal 2, but was 3."


def test_a_line_shared_with_a_statement_that_runs_on_falls_back() -> None:
    """Same ambiguity, with the second statement carried over several lines.

    This is the shape that says which line a call is filed under. The second
    ``expect(`` opens on the reporting line and closes two lines below it; index
    it by where it ends and the reporting line looks like it holds exactly one
    subject, which is how a wrong name gets stated with confidence.
    """
    first = 3
    second = 3
    with pytest.raises(AssertionFailure) as caught:
        expect(first).is_equal_to(2); expect(  # noqa: E702
            second
        ).is_equal_to(1)
    assert str(caught.value) == "Expected the value to equal 2, but was 3."


def test_two_subjects_in_one_statement_fall_back_across_lines() -> None:
    """Two candidates, deliberately not on the same line as each other.

    With both on one line `_shares_its_line` reaches the fallback first and the
    candidate loop is never asked. Split them and the loop is the only thing
    standing between the reader and a message that names ``left`` for a failure
    about ``right``.
    """
    left = 4
    right = 5
    with pytest.raises(AssertionFailure) as caught:
        expect(
            left
        ).is_equal_to(expect(right).subject)
    assert str(caught.value) == "Expected the value to equal 5, but was 4."


def test_a_header_written_on_one_line_with_its_body_keeps_its_name() -> None:
    """A tie the index must break the other way: outermost, not innermost.

    ``with cm: body`` written on a single line puts the header and the body on
    that one line, spanning zero lines each. The subject sits in the header, so
    the tie has to go to the statement seen first -- the enclosing one. Break it
    the other way and the search runs over a body that never mentions
    ``expect_raises``, and this spelling silently loses the name that the two
    multi-line spellings above keep:

        Expected the value to be raised, but nothing was raised.
    """
    with pytest.raises(AssertionFailure) as caught:  # noqa: SIM117
        with expect_raises(KeyError): pass  # noqa: E701
    assert str(caught.value) == "Expected KeyError to be raised, but nothing was raised."
# fmt: on


def _explode(*_args: object, **_kwargs: object) -> object:
    """Stand in for a step of name recovery that fails outright."""
    message = "name recovery exploded"
    raise RuntimeError(message)


def test_a_failure_to_recover_a_name_never_costs_the_assertion_its_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The name is a nicety; the message is the product.

    Everything in ``_names`` runs *after* an assertion has already failed and its
    message has already been written. All it adds is the expression the reader
    wrote, in place of ``the value``. Unguarded, an exception there replaces the
    ``AssertionFailure`` with a traceback out of this library, and the reader
    loses the account of what actually went wrong to keep a cosmetic one.

    Catching ``SyntaxError`` around ``ast.parse`` is not enough, because it is
    far from the only thing that can happen: ``ast.parse`` raises
    ``RecursionError`` rather than ``SyntaxError`` on deeply nested generated
    source, ``linecache`` can hand back a file rewritten since the frame was
    captured, and a subject built inside ``exec`` has a filename naming nothing
    at all. The guard is therefore over everything, not over one exception type.
    """
    monkeypatch.setattr(_names, "_caller_frame", _explode)
    balance = 4
    with pytest.raises(AssertionFailure) as caught:
        expect(balance).is_equal_to(3)
    assert str(caught.value) == "Expected the value to equal 3, but was 4."


def test_a_failure_to_recover_a_name_does_not_discard_a_soft_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same guard, where its absence cost the most.

    Inside a soft scope the exception leaves ``__exit__`` by the wrong door, so
    every failure collected before it goes with it: a block that found three
    problems would report none of them and one unrelated ``RuntimeError``.
    """
    with pytest.raises(AssertionFailure) as caught, soft_assertions():
        expect(1).is_equal_to(2)
        expect("a").is_equal_to("b")
        monkeypatch.setattr(_names, "_caller_frame", _explode)
        expect(3).is_equal_to(4)

    report = str(caught.value)
    assert "3 assertions failed" in report, report
    assert "to equal 2, but was 1" in report, report
    assert "to equal 'b', but was 'a'" in report, report
    assert "to equal 4, but was 3" in report, report


# ---------------------------------------------------------------------------
# The remaining ways name recovery declines to answer
#
# Ambiguity above is the interesting one. These three are the cases where there
# is nothing to read at all: no frame outside the library, no source that parses,
# no argument in the call that built the subject. Each ends in the same anonymous
# sentence -- never a guess, and never an exception on top of the failure the
# reader is already being shown.
# ---------------------------------------------------------------------------
def test_a_stack_with_nobody_left_to_name_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """The walk out of the library can reach the bottom having found no caller.

    Two kinds of frame are skipped on the way out: this package's own, and a user
    assertion marked with ``@custom_assertion``. When the two account for the
    whole stack there is no source line left to read an expression off. That
    happens for real at the bottom of a thread started through
    ``_thread.start_new_thread``, whose only frame is its target's -- none of the
    ``threading`` bootstrap that would otherwise answer the walk sits under it --
    and it is arranged here by marking every frame currently on the stack, which
    puts the same shape on the main thread.

    The caller's file is this one, and it is perfectly readable; the name is lost
    to the walk rather than to the source.
    """
    import inspect

    here = inspect.currentframe()
    assert here is not None, "CPython always has a current frame"
    marked = {here.f_code}
    frame = here.f_back
    while frame is not None:
        marked.add(frame.f_code)
        frame = frame.f_back

    monkeypatch.setattr(_names, "_CUSTOM_ASSERTION_CODES", marked)

    balance = 4
    with pytest.raises(AssertionFailure) as caught:
        expect(balance).is_equal_to(3)

    assert str(caught.value) == "Expected the value to equal 3, but was 4."


def test_source_that_does_not_parse_falls_back(tmp_path: Path) -> None:
    """What a loader hands back is not guaranteed to be the Python that ran.

    With no file on disk, ``linecache`` asks the module's ``__loader__`` -- and a
    loader for generated, packed or otherwise synthesised code answers with
    whatever it has, which need not parse. It is read on the failure path, on top
    of an assertion that has already failed, so the parse failing is a missing
    name and nothing more.
    """
    import linecache

    class DisagreeingLoader:
        """Hands back source that is not the code that ran, and does not parse."""

        def get_source(self, name: str) -> str:
            del name
            return "this is not ( python\n"

    filename = str(tmp_path / "never_written.py")
    source = "def run():\n    balance = 4\n    expect(balance).is_equal_to(3)\n"
    namespace: dict[str, object] = {
        "__name__": "never_written",
        "__loader__": DisagreeingLoader(),
        "expect": expect,
    }
    exec(compile(source, filename, "exec"), namespace)  # noqa: S102
    run = cast("Callable[[], None]", namespace["run"])

    try:
        assert linecache.getlines(filename, namespace) == ["this is not ( python\n"]

        assert _message(run) == "Expected the value to equal 3, but was 4."
    finally:
        linecache.cache.pop(filename, None)


def test_source_that_does_not_parse_yields_no_index() -> None:
    """The parse is given up on where it fails, not left to the outer guard.

    ``resolve_subject_name`` catches everything, so a ``SyntaxError`` allowed to
    escape the index would end in the same fallback name and the same message.
    Asking the index directly is the only thing that tells declining apart from
    unwinding.
    """
    from lovely_assertions._names import (
        _index_for,  # pyright: ignore[reportPrivateUsage]
    )

    index = _index_for("<not python>", ["this is not ( python\n"])

    assert index is None


def test_a_subject_built_with_no_arguments_falls_back() -> None:
    """The name is the first argument of the call, and there need not be one.

    A subject that carries its own value takes nothing to construct, so there is
    no expression in the source to name it by -- and the reader wrote no name
    either, which is exactly what the anonymous form says.
    """

    class EnvironmentExpect(Expect[int]):
        __slots__ = ()

        def __init__(self) -> None:
            super().__init__(0)

    with pytest.raises(AssertionFailure) as caught:
        EnvironmentExpect().is_equal_to(1)

    assert str(caught.value) == "Expected the value to equal 1, but was 0."
