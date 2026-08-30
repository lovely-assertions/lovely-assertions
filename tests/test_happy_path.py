"""A passing assertion costs a comparison and a ``return self``, and nothing more.

This is enforced three ways -- one dynamic, two structural -- because each one
alone is escapable, and rule A needs three arms for the same reason.

*Dynamically* -- every machine the failure path needs is replaced with a booby
trap, and then **every public assertion** is called in a way that passes. A
passing assertion that touches subject-name recovery, the scope ``ContextVar``,
``_fail`` or ``_fail_narrowing`` blows up. The call table is built by
introspection over the subject classes, so an assertion added tomorrow with no
happy-path exercise turns this red and names itself. That derivation is the
guard: a hand-picked sample of assertions leaves most of the public surface
untouched, and the assertions nobody thought to list are where a violation
survives. The enumeration is keyed by implementation rather than by each class
that inherits one, and the subject classes it walks are read off the package
rather than listed -- which is what reaches the overrides on ``_CaughtExpect``,
the handle that ``with expect_raises(...) as caught`` binds. Six assertions
cannot have a passing exercise at all, and each is named with its reason in
``NO_HAPPY_PATH``.

*Structurally, rule A* -- the trap cannot see a message built **before** the
branch, as in ``self._check(cond, f"...")``: the message is evaluated on every
call, passing or not, and then thrown away. So the source is parsed, and in any
function that reports through ``_fail`` a message-building expression must sit
inside a ``_fail(...)`` argument, a ``raise``, or the part of the body that only
runs once the happy path is over. Seven shapes count as message-building: an
f-string, ``+`` (``+=`` included), ``%``, ``.format()``, ``.join()``, ``repr()``,
and a mention of a helper that declares itself a message builder. An operand
counts as text whether it is a literal or a name holding one, because this
library keeps its wording in module constants and ``_TO_EQUAL + repr(expected)``
costs exactly what the literal would.

*Rule A's third arm* -- arm 2 reads only the functions that call ``_fail``, so
the cheapest way past it is to move the message one call down, into a private
method beside the assertion. That arm follows the happy path into the subject
classes' own methods.

*Structurally, rule B* -- the helpers that build messages are allowed to build
them anywhere, which is an exemption on trust unless something checks where they
are *called* from. Rule B checks it: no message builder may be *reachable* from a
happy path, however many helpers deep, along the call edges it can resolve.

Why rule A looks for more than f-strings. A rule that walks for ``ast.JoinedStr``
and nothing else is blind to ``+``, ``%``, ``.format()`` and ``"".join(...)`` --
and the blindness is contagious, because a rule teaches a codebase to reach for
whatever it cannot see. Three helpers in this library say "concatenation rather
than an f-string" out loud, and ``message = "to equal " + repr(expected)`` on a
happy path costs exactly what the f-string would.

**What these rules still do not catch**, stated here rather than left to be
discovered: a guard read as complete is a guard nobody widens.

* *A message built in an ordinary module-level helper.* Rule A's third arm
  follows a happy path into the *methods* of the subject classes, which is where
  an extracted message goes. It does not follow one into a module-level function:
  the same scan over every reachable function reports dozens of sites, among them
  ``_text._wildcard_source`` compiling a pattern and ``_formatters._apply``
  honouring a user's format spec -- string work that is the assertion, not the
  message. So ``def _note(value): return "was " + repr(value)`` at module level,
  called above the branch, is invisible.
* *Anything named like the failure path.* :func:`_is_fail_call` matches on the
  ``_fail`` prefix, so a helper called ``_failure_note(...)`` shelters its own
  arguments wherever it is called. And an assertion that reported through
  something *not* named ``_fail...`` -- ``self._report(...)`` -- would fall
  outside rule A's scope entirely and seed nothing in rule B.
* *String work that is the comparison.* Rule A cannot tell a message from a
  normalisation. An assertion doing ``" ".join(subject.split())`` above its
  branch is reported, and the answer is to move it into a helper, which is a
  workaround rather than a fix.
* *Call shapes rule B cannot resolve.* Only a bare name and ``self.something``.
  A builder reached through a callback, a stored attribute or ``getattr`` is not
  seen. Nodes are keyed by name, not by module, so two functions sharing a name
  are one node -- which over-reports rather than under-reports, but means a
  printed chain may not be the chain that exists.
* *One passing call per assertion.* An assertion with a second passing branch
  that touches the failure machinery only on that branch is not covered; the
  enumeration proves each assertion is exercised, not that it is exercised
  thoroughly. Six assertions are exercised not at all, by name, in
  :data:`NO_HAPPY_PATH`.
* *Runtime.* Neither rule sees a message assembled by a C-level call or an
  expensive ``__str__``. ``tests/test_performance_invariants.py`` counts
  allocations and is the complement; the two genuinely see different bugs.

The call table lives in ``tests/_happy_calls.py`` rather than here, because the
allocation guard needs the same passing calls and a second copy of them would
drift into a sample of this one -- the failure both files exist to prevent. One
table, two guards; that module's docstring says the rest.
"""

import ast
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Final

import pytest

import lovely_assertions
from _happy_calls import (
    HAPPY_CALLS,
    NO_HAPPY_PATH,
    PUBLIC_ASSERTIONS,
    SUBJECT_CLASSES,
    World,
)
from _package import sources
from conftest import Detonator
from lovely_assertions import expect

REPO_ROOT: Final = Path(__file__).resolve().parent.parent

#: Functions whose whole job is to build text; they are the exception that the
#: structural rule exists to isolate. Kept as a literal for the f-string arm of
#: rule A, which is the strictest arm and is not relaxed here. Rule A's other
#: shapes and the whole of rule B use the *derived* set below, because a
#: hand-written set is the thing rule B exists to stop trusting.
MESSAGE_BUILDERS: Final = frozenset(
    {
        "_fail",
        "_fail_narrowing",
        "_render_failure",
        "_render_aggregate",
        "__repr__",
        "__str__",
    }
)


@pytest.mark.usefixtures("no_failure_machinery")
def test_passing_assertions_never_touch_the_failure_path() -> None:
    expect(3).is_equal_to(3)
    expect(3).is_not_equal_to(4)
    expect("x").is_not_none()
    expect(None).is_none()
    expect(3).is_instance_of(int)
    expect(3).is_same_as(3)
    expect(3).is_not_same_as(4)


@pytest.mark.usefixtures("no_failure_machinery")
def test_because_is_not_touched_on_the_happy_path() -> None:
    """A passing assertion must not read, strip or concatenate its ``because``.

    The reason a caller supplies is keyword-only and belongs to the failure
    message, so it costs a passing assertion nothing. The trap is what proves it:
    every route that would consume ``because`` runs through the failure
    machinery, so a passing call that formats it detonates.
    """
    expect(3).is_equal_to(3, because="the ledger must balance")
    expect(3).is_not_equal_to(4, because="because reasons are normalised on failure")


@pytest.mark.usefixtures("no_failure_machinery")
def test_chaining_stays_on_the_happy_path() -> None:
    assert expect(3).is_equal_to(3).and_.is_not_none().subject == 3


# ---------------------------------------------------------------------------
# The detonator, pointed at the whole public surface
#
# The seven calls above are a sample, and a sample misses. What follows is the
# enumeration: every public method of every subject class, each with one
# invocation that passes, all of them run under the trap.
#
# The table itself lives in ``tests/_happy_calls.py``, because
# ``tests/test_performance_invariants.py`` needs the same calls to point
# ``tracemalloc`` at and a second copy would drift into a sample of this one. One
# table, two guards; the module docstring there says why at length.
# ---------------------------------------------------------------------------


def test_the_trap_actually_detonates() -> None:
    """A rule nobody can fail is not a rule.

    A trap that has quietly stopped raising would turn every test in this file
    green while proving nothing, so both of its arms -- attribute access and
    call -- are exercised. Lives here because this is the file that points the one
    shared trap at the whole public surface.
    """
    detonator = Detonator()
    with pytest.raises(AssertionError, match="failure path"):
        _ = detonator.get()
    with pytest.raises(AssertionError, match="failure path"):
        detonator()


def test_the_enumeration_finds_the_whole_surface() -> None:
    """A guard over an empty -- or shrunken -- enumeration would pass for nothing.

    The three named entries are named on purpose: they live on classes an
    enumeration built from ``__all__`` cannot see -- two of them public in use and
    private in name, and ``WithinDelta``, which is not an :class:`Expect` at all
    though ``is_within(...).before(...)`` is a public assertion. They are the
    reason :func:`subject_classes` reads the package rather than a list, and if
    that derivation is ever narrowed back to what is exported, they go first.
    """
    assert len(PUBLIC_ASSERTIONS) > 250
    assert ("_CaughtExpect", "where") in PUBLIC_ASSERTIONS
    assert ("_TemporalExpect", "is_before") in PUBLIC_ASSERTIONS
    assert ("WithinDelta", "before") in PUBLIC_ASSERTIONS


def test_every_public_assertion_has_a_happy_path_exercise() -> None:
    """No assertion may be exercised by neither guard without saying so.

    A handful of hand-picked calls reads as covering the invariant while leaving
    most of the public surface untouched, and an assertion nobody listed is where
    a violation lives undisturbed. This fails, by name, for any assertion that has
    neither an entry in :data:`HAPPY_CALLS` nor a documented reason in
    :data:`NO_HAPPY_PATH`, so the gap cannot widen in silence.
    """
    missing = [
        f"{owner}.{name}"
        for owner, name in PUBLIC_ASSERTIONS
        if (owner, name) not in HAPPY_CALLS and (owner, name) not in NO_HAPPY_PATH
    ]
    assert not missing, (
        f"no passing invocation is registered for {missing}. Add one to "
        f"HAPPY_CALLS so the detonator covers it; only add it to NO_HAPPY_PATH "
        f"if its happy path genuinely cannot avoid the failure machinery."
    )


@pytest.mark.usefixtures("no_failure_machinery")
@pytest.mark.parametrize(
    ("owner", "name"),
    sorted(HAPPY_CALLS),
    ids=[f"{owner}.{name}" for owner, name in sorted(HAPPY_CALLS)],
)
def test_the_whole_public_surface_stays_off_the_failure_path(
    owner: str, name: str, world: World
) -> None:
    """One passing call per assertion, with the failure machinery booby-trapped."""
    HAPPY_CALLS[(owner, name)](world)


def test_the_happy_call_table_has_no_stale_entries() -> None:
    """An entry for an assertion that no longer exists is a test of nothing."""
    stale = sorted(f"{o}.{n}" for o, n in HAPPY_CALLS if (o, n) not in set(PUBLIC_ASSERTIONS))
    assert not stale, f"HAPPY_CALLS names assertions that no longer exist: {stale}"


def test_the_uncovered_list_has_no_stale_entries() -> None:
    stale = sorted(f"{o}.{n}" for o, n in NO_HAPPY_PATH if (o, n) not in set(PUBLIC_ASSERTIONS))
    assert not stale, f"NO_HAPPY_PATH names assertions that no longer exist: {stale}"


def test_the_uncovered_list_cannot_grow() -> None:
    """Shrink only.

    The exemption list is the one place where this file can be made green by
    giving up, so the count is pinned. Removing an entry means editing this number
    down; adding one means arguing for it in review rather than in a commit nobody
    reads.
    """
    assert len(NO_HAPPY_PATH) <= 6, (
        f"NO_HAPPY_PATH has grown to {len(NO_HAPPY_PATH)} entries: "
        f"{sorted(f'{o}.{n}' for o, n in NO_HAPPY_PATH)}. It is a shrinking list."
    )


# ---------------------------------------------------------------------------
# Structural half
# ---------------------------------------------------------------------------
type _Function = ast.FunctionDef | ast.AsyncFunctionDef

#: The docstring convention this codebase already keeps: dozens of helpers say
#: "Failure path only." and mean it. A better key than a literal set, because a
#: helper written tomorrow is checked without anyone remembering to add it.
_CLAIMS_THE_EXEMPTION: Final = "failure path only"

#: Message builders that do not carry the marker docstring. Named here rather
#: than in ``src/``, which this file does not own; every one of them is a
#: cross-module rendering primitive.
_UNMARKED_BUILDERS: Final = frozenset(
    {
        "count_of",
        "describe_difference",
        "describe_predicate",
        "length_note",
        "render_items",
        "render_operand",
    }
)

#: Call edges rule B may not see through, each with the reason it is legitimate.
#: :func:`test_every_exempt_edge_is_still_load_bearing` fails if one of these
#: stops being needed, so the list cannot rot into a blanket allow-list.
_EXEMPT_EDGES: Final[dict[tuple[str, str], str]] = {
    ("compare", "_render"): (
        "`compare` is both the test and the message: two object graphs cannot be "
        "shown equivalent without walking them, and the walk's findings are the "
        'message. Its `if not findings.items: return ""` does guard the '
        "rendering, but both branches return a string, so no structural rule can "
        "tell the verdict from the report."
    ),
}


def _library_sources() -> dict[str, str]:
    package_dir = Path(lovely_assertions.__file__).parent
    return {
        path.relative_to(package_dir).as_posix(): path.read_text(encoding="utf-8")
        for path in sources(package_dir)
    }


def _own_nodes(node: ast.AST) -> Iterator[ast.AST]:
    """``ast.walk``, stopping at a nested ``def`` or ``class``.

    A nested function's body does not run when the enclosing function runs, so
    folding it in would attribute a closure's cost to its owner.
    """
    for child in ast.iter_child_nodes(node):
        yield child
        if not isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            yield from _own_nodes(child)


def _call_target(node: ast.Call) -> tuple[str, str] | None:
    """What a call resolves to inside this library, as ``(kind, name)``.

    Only two shapes can be resolved without a type checker: a bare name, and
    ``self.something``. Everything else -- ``path.is_symlink()``,
    ``pattern.match()`` -- is a call on somebody else's object and is left alone.
    Resolving it by name would collide ``PathExpect.is_symlink`` with
    ``Path.is_symlink`` and turn the whole graph to noise.
    """
    func = node.func
    if isinstance(func, ast.Name):
        return ("function", func.id)
    if (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "self"
    ):
        return ("method", func.attr)
    return None


def _is_fail_call(node: ast.AST) -> bool:
    """Whether this call reports a failure, whoever owns the method.

    Looser than :func:`_call_target` on purpose. ``WithinDelta.before`` reports
    through ``self._parent._fail(...)`` -- a deliberate reach across a cooperating
    pair, documented as such -- and a shelter that only recognised ``self._fail``
    would report the message that call builds as a violation.

    The cost of the looseness, since it is a shelter: *any* call to a name
    starting with ``_fail`` shelters its arguments, wherever that call sits. A
    helper called ``_failure_note(...)`` on a happy path would hide the message
    handed to it. Narrowing the match to the three real reporters (``_fail``,
    ``_fail_narrowing``, ``_callable._fail_no_cause``) does not close that -- the
    name a contributor invents is the whole problem -- so it is left loose and
    written down instead.
    """
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
    return name.startswith("_fail")


def _sheltered(root: ast.AST) -> set[int]:
    """Nodes that cannot cost a passing assertion anything.

    Three shelters, and they are the same idea three times -- the expression only
    runs once the run has already gone wrong. A ``_fail(...)`` argument is the
    failure branch; a ``raise`` argument is a caller-bug report, the ``ValueError``
    family this library raises when an assertion is called wrongly rather than
    when it fails; an ``except`` body runs only because something was raised.
    """
    out: set[int] = set()
    for node in ast.walk(root):
        if isinstance(node, ast.Call) and _is_fail_call(node):
            out.add(id(node))
            for argument in [*node.args, *(keyword.value for keyword in node.keywords)]:
                out.update(id(inner) for inner in ast.walk(argument))
        elif isinstance(node, ast.Raise | ast.ExceptHandler):
            out.update(id(inner) for inner in ast.walk(node))
    return out


def _happy_region_end(func: _Function) -> int | None:
    """The last line on which this function may still be passing.

    Assertions here are written test / ``return self`` / ``return self._fail(...)``,
    so the last statement carrying a return that is *not* a ``_fail`` call is
    where the happy path ends. After it, the assertion has already decided to
    fail and may build whatever it likes. ``None`` means no such statement, in
    which case the whole body is still reachable while passing.
    """
    last: ast.stmt | None = None
    for statement in func.body:
        for node in [statement, *_own_nodes(statement)]:
            if not isinstance(node, ast.Return):
                continue
            if node.value is not None and _is_fail_call(node.value):
                continue
            last = statement
            break
    return last.end_lineno if last is not None else None


def _on_the_happy_path(node: ast.AST, end: int | None) -> bool:
    lineno = getattr(node, "lineno", None)
    if lineno is None:
        return False
    return end is None or lineno <= end


def _functions(tree: ast.AST) -> Iterator[tuple[_Function, ast.AST]]:
    """Every ``def`` in the tree, with the node it is defined in."""
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                yield child, parent


def _message_builders(sources: Mapping[str, str]) -> frozenset[str]:
    """The set of functions claiming the exemption, derived from the source."""
    names = set(_UNMARKED_BUILDERS)
    for source in sources.values():
        for func, _ in _functions(ast.parse(source)):
            docstring = (ast.get_docstring(func) or "").casefold().replace("*", "")
            if _CLAIMS_THE_EXEMPTION in docstring:
                names.add(func.name)
    return frozenset(names)


def _enclosing_function(tree: ast.Module, node: ast.AST) -> str | None:
    for candidate in ast.walk(tree):
        if not isinstance(candidate, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for inner in ast.walk(candidate):
            if inner is node:
                return candidate.name
    return None


def _bindings(statements: "list[ast.stmt]", *, deep: bool) -> list[tuple[list[str], ast.expr]]:
    """``(names assigned, value assigned)`` for every binding in these statements.

    ``deep`` walks into ``if``/``for``/``with`` bodies, which is right inside a
    function and wrong at module level, where a name bound inside a ``def`` is
    not a module constant.
    """
    out: list[tuple[list[str], ast.expr]] = []
    for statement in statements:
        nodes: list[ast.AST] = [statement, *_own_nodes(statement)] if deep else [statement]
        for node in nodes:
            if isinstance(node, ast.Assign):
                targets, value = list(node.targets), node.value
            elif isinstance(node, ast.AnnAssign | ast.AugAssign) and node.value is not None:
                targets, value = [node.target], node.value
            else:
                continue
            names = [target.id for target in targets if isinstance(target, ast.Name)]
            if names:
                out.append((names, value))
    return out


def _textual_names(tree: ast.Module, func: _Function) -> frozenset[str]:
    """The names that hold text where ``func`` can see them.

    A rule that insists on a string *literal* as an operand misses most of this
    library, which keeps its wording in module constants -- ``_NAN_OPERAND_NOTE``,
    ``_UNMEASURABLE_NOTE``, ``_NEEDS_VALUES``, a moduleful per family. Without
    this, ``_TO_START_WITH + prefix`` on a happy path is a message the rule cannot
    see, for no better reason than that the words are one indirection away.

    Resolved to a fixed point, because the indirection can be two deep:
    ``note = _PREFIX`` and then ``note += repr(value)`` is the same message
    written as two statements, and the second one is not even a ``BinOp``.
    """
    bindings = _bindings(tree.body, deep=False) + _bindings(func.body, deep=True)
    names: set[str] = set()
    growing = True
    while growing:
        growing = False
        for targets, value in bindings:
            if not _is_text(value, frozenset(names)):
                continue
            fresh = set(targets) - names
            if fresh:
                names |= fresh
                growing = True
    return frozenset(names)


def _is_text(node: ast.AST, textual: frozenset[str] = frozenset()) -> bool:
    """Whether this expression is text: a literal, an f-string, or a name holding one."""
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str)
    return isinstance(node, ast.Name) and node.id in textual


def _message_form(
    node: ast.AST, builders: frozenset[str], textual: frozenset[str] = frozenset()
) -> str | None:
    """What kind of message-building this expression is, or ``None``.

    Seven shapes, because a rule that recognises only ``ast.JoinedStr`` leaves the
    other six spellings of the same cost unchallenged.

    ``repr()`` earns an arm of its own, and it is the one that catches what no
    text-shaped arm can: ``_ = sorted(map(repr, self._subject))`` above a passing
    ``is_empty`` builds no string at all, and is worse than an f-string, being
    ``O(n log n)`` over the subject. The justification is that ``repr`` is *purely
    presentational* -- nothing an assertion needs to decide its verdict comes from
    it -- so a call before the verdict is known can only be message work. That
    reasoning does not extend to ``sorted``, ``set`` or ``len``, which assertions
    legitimately use to reach a verdict, so they are not flagged and a caller who
    wants them for a message has to keep them below the ``return self``.
    """
    if (
        isinstance(node, ast.BinOp)
        and isinstance(node.op, ast.Add)
        and (_is_text(node.left, textual) or _is_text(node.right, textual))
    ):
        return "string concatenation"
    if (
        isinstance(node, ast.BinOp)
        and isinstance(node.op, ast.Mod)
        and _is_text(node.left, textual)
    ):
        return "%-formatting"
    if (
        isinstance(node, ast.AugAssign)
        and isinstance(node.op, ast.Add)
        and (_is_text(node.target, textual) or _is_text(node.value, textual))
    ):
        # `note = _PREFIX` then `note += repr(x)` is the same cost written as two
        # statements, and an `AugAssign` is not a `BinOp`, so it needs its own arm.
        return "string concatenation"
    if isinstance(node, ast.Call):
        target = _call_target(node)
        attribute = node.func.attr if isinstance(node.func, ast.Attribute) else ""
        if attribute in {"format", "join"}:
            return f"str.{attribute}()"
        if isinstance(node.func, ast.Name) and node.func.id == "repr":
            return "repr()"
        if target is not None and target[1] in builders:
            return f"a call to the message builder {target[1]}()"
    if isinstance(node, ast.Name) and (node.id == "repr" or node.id in builders):
        # Handed to something else rather than called: `sorted(map(repr, items))`
        # never spells `repr(...)`, so the call arm above cannot see it. A name
        # that is only useful for rendering is message work wherever it is
        # mentioned, not only where it is called.
        return "a reference to " + node.id
    return None


def _fstrings_outside_fail_calls(source: str) -> list[tuple[int, str]]:
    """Rule A, first arm: no f-string outside a ``_fail(...)`` argument, anywhere.

    Deliberately not folded into the second arm. This one applies to *every*
    function, not only to assertion bodies, and exempts only the names in
    :data:`MESSAGE_BUILDERS` -- so widening the rule below, which reads a derived
    and therefore larger exemption set, cannot quietly narrow this one.
    """
    tree = ast.parse(source)
    sheltered = _sheltered(tree)

    offenders: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.JoinedStr) or id(node) in sheltered:
            continue
        owner = _enclosing_function(tree, node)
        if owner in MESSAGE_BUILDERS:
            continue
        offenders.append((node.lineno, owner or "<module>"))
    return offenders


def _messages_built_while_still_passing(
    source: str, builders: frozenset[str]
) -> list[tuple[int, str, str]]:
    """Rule A, second arm: no message work in an assertion that may still pass.

    Scoped to functions that call ``_fail``, because those are the assertion
    bodies -- the place where a message costs a passing test something. Within
    one, everything up to and including the last happy exit is a cost the happy
    path pays; everything after it has already decided to fail.
    """
    tree = ast.parse(source)
    sheltered = _sheltered(tree)

    offenders: list[tuple[int, str, str]] = []
    for func, _ in _functions(tree):
        own = list(_own_nodes(func))
        if not any(_is_fail_call(node) for node in own):
            continue
        if func.name in builders:
            continue
        end = _happy_region_end(func)
        textual = _textual_names(tree, func)
        # One finding per message expression, not one per sub-node. `prefix +
        # repr(expected)` is a single mistake written two ways, and reporting the
        # concatenation and the `repr()` inside it separately would make a reader
        # hunt for a second violation that is not there. `_own_nodes` yields
        # parents before children, so the outermost form wins.
        covered: set[int] = set()
        for node in own:
            if id(node) in sheltered or id(node) in covered:
                continue
            form = _message_form(node, builders, textual)
            if form is None or not _on_the_happy_path(node, end):
                continue
            offenders.append((getattr(node, "lineno", 0), func.name, form))
            covered.update(id(inner) for inner in ast.walk(node))
    return sorted(offenders)


def test_no_message_is_built_outside_a_fail_call() -> None:
    """Rule A, first arm, over the whole library.

    An f-string passed as an argument is evaluated before the call, so a message
    assembled anywhere but inside ``_fail(...)`` is a message the happy path pays
    for and discards.
    """
    offenders: dict[str, list[tuple[int, str]]] = {}
    for name, source in _library_sources().items():
        found = _fstrings_outside_fail_calls(source)
        if found:
            offenders[name] = found
    assert not offenders, (
        f"f-strings outside a `_fail(...)` argument: {offenders}. "
        f"Format in the failure branch only."
    )


def test_no_message_is_built_while_the_assertion_may_still_pass() -> None:
    """Rule A, second arm: the forms an f-string scan cannot see.

    ``message = "to equal " + repr(expected)`` above the comparison costs a
    passing assertion exactly what the f-string would, and is the whole reason
    this arm exists: nothing else in the suite looks at it.
    """
    sources = _library_sources()
    builders = _message_builders(sources)
    offenders: dict[str, list[tuple[int, str, str]]] = {}
    for name, source in sources.items():
        found = _messages_built_while_still_passing(source, builders)
        if found:
            offenders[name] = found
    assert not offenders, (
        f"messages built before the assertion had failed: {offenders}. "
        f"Move the work below the `return self`, or into the `_fail(...)` "
        f"argument itself."
    )


# ---------------------------------------------------------------------------
# Rule B: the exemption, checked instead of promised
# ---------------------------------------------------------------------------
def _happy_calls(func: _Function) -> list[tuple[str, str]]:
    """What this function may call on a run that has not gone wrong yet."""
    sheltered = _sheltered(func)
    end = _happy_region_end(func)
    out: list[tuple[str, str]] = []
    for node in _own_nodes(func):
        if not isinstance(node, ast.Call) or id(node) in sheltered:
            continue
        if not _on_the_happy_path(node, end):
            continue
        target = _call_target(node)
        if target is not None:
            out.append(target)
    return out


#: One definition of a function, with the module and tree it came from.
type _Definition = tuple[str, ast.Module, _Function, ast.AST]


def _happy_path_reach(
    sources: Mapping[str, str],
) -> tuple[
    dict[tuple[str, str], list[_Definition]],
    dict[tuple[str, str], str],
    dict[tuple[str, str], list[str]],
]:
    """Everything a passing assertion may call, and the route to each of them.

    Returned as ``(definitions, seeds, routes)``: what the library defines, what
    an assertion body calls while it may still pass, and how the walk got to each
    function it can reach. Two rules read this -- rule B, which asks whether a
    *message builder* is down there, and the third arm of rule A, which asks
    whether anything down there *builds* one.
    """
    trees = {name: ast.parse(source) for name, source in sources.items()}

    definitions: dict[tuple[str, str], list[_Definition]] = {}
    for name, tree in trees.items():
        for func, parent in _functions(tree):
            kind = "method" if isinstance(parent, ast.ClassDef) else "function"
            definitions.setdefault((kind, func.name), []).append((name, tree, func, parent))

    graph: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for key, defs in definitions.items():
        graph[key] = {
            callee
            for _, _, func, _ in defs
            for callee in _happy_calls(func)
            if callee in definitions and (key[1], callee[1]) not in _EXEMPT_EDGES
        }

    seeds: dict[tuple[str, str], str] = {}
    for name, tree in trees.items():
        for func, _ in _functions(tree):
            if not any(_is_fail_call(node) for node in _own_nodes(func)):
                continue
            for callee in _happy_calls(func):
                if callee in definitions and (func.name, callee[1]) not in _EXEMPT_EDGES:
                    seeds.setdefault(callee, f"{name}:{func.name}")

    routes: dict[tuple[str, str], list[str]] = {key: [key[1]] for key in seeds}
    pending = list(seeds)
    while pending:
        current = pending.pop()
        for callee in graph.get(current, ()):
            if callee not in routes:
                routes[callee] = [*routes[current], callee[1]]
                pending.append(callee)
    return definitions, seeds, routes


def _builders_reachable_from_a_happy_path(
    sources: Mapping[str, str],
) -> list[str]:
    """Rule B: no message builder may be reachable from a passing assertion.

    Letting a named set of helpers build text anywhere is only safe if something
    checks where they are *called* from; on its own it is a promise. This walks
    the call graph instead: seed it with everything an assertion body calls while
    it may still pass, follow those functions through their own happy paths, and
    report any message builder the walk arrives at.

    Two-hop is the case that matters. Rule A sees ``format_value(x)`` written
    straight into an assertion body; only this sees an assertion calling a
    perfectly innocent-looking helper that calls ``format_value`` itself.
    """
    builders = _message_builders(sources)
    _, seeds, routes = _happy_path_reach(sources)
    return sorted(
        f"{seeds.get(_origin(routes, key), '?')} -> " + " -> ".join(routes[key])
        for key in routes
        if key[1] in builders
    )


def _origin(routes: Mapping[tuple[str, str], list[str]], key: tuple[str, str]) -> tuple[str, str]:
    """The seed a route started from, for the report."""
    first = routes[key][0]
    for candidate in routes:
        if candidate[1] == first and routes[candidate] == [first]:
            return candidate
    return key


def _messages_built_by_a_helper_method(
    sources: Mapping[str, str], subject_classes: frozenset[str]
) -> dict[str, list[tuple[str, str, str]]]:
    """Rule A, third arm: the same work, moved one call down.

    Arm 2 only reads functions that call ``_fail``, so the cheapest way past it is
    never an exotic idiom -- it is an ordinary private method::

        def _key_note(self, key):
            return "to contain key " + repr(key)

        def contains_key(self, key, ...):
            note = self._key_note(key)          # <- built on every passing call
            if key in self._subject:
                return Found(self, self._subject[key])

    Arm 2 skips ``_key_note`` (no ``_fail``); rule B does not report it (it is not
    a message builder, and ``repr`` is not one either). Without this arm that
    plant passes every other test in this repository, the allocation guard in
    ``tests/test_performance_invariants.py`` included.

    Scoped to methods of the subject classes, which is where the assertions live
    and where an extracted message goes. Module-level helpers are *not* covered,
    and deliberately: the same scan over every reachable function reports dozens
    of sites, and every one of them is a renderer doing its job or a pattern being
    compiled. Half the hole closed at no cost beats neither half closed at a cost
    nobody would pay.
    """
    builders = _message_builders(sources)
    definitions, _, routes = _happy_path_reach(sources)

    offenders: dict[str, list[tuple[str, str, str]]] = {}
    for key, route in routes.items():
        if key[1] in builders:
            continue
        for name, tree, func, parent in definitions.get(key, []):
            if not isinstance(parent, ast.ClassDef) or parent.name not in subject_classes:
                continue
            if any(_is_fail_call(node) for node in _own_nodes(func)):
                continue  # an assertion body; arm 2 already reads it
            sheltered = _sheltered(func)
            textual = _textual_names(tree, func)
            covered: set[int] = set()
            for node in _own_nodes(func):
                if id(node) in sheltered or id(node) in covered:
                    continue
                form = _message_form(node, builders, textual)
                if form is not None:
                    offenders.setdefault(name, []).append(
                        (f"{parent.name}.{func.name}", form, " -> ".join(route))
                    )
                    # One finding per expression, as in arm 2: the `repr()` inside
                    # `"key " + repr(k)` is the same mistake, not a second one.
                    covered.update(id(inner) for inner in ast.walk(node))
    return {name: sorted(set(found)) for name, found in offenders.items()}


_SUBJECT_CLASS_NAMES: Final = frozenset(cls.__name__ for cls in SUBJECT_CLASSES)


def test_no_helper_method_builds_a_message_for_an_assertion_that_may_still_pass() -> None:
    """Rule A, third arm: arm 2's scope, followed one call down.

    The message does not have to be written in the assertion. Put in a private
    method beside it and called above the branch, it costs a passing call exactly
    the same and is invisible to every other check in this file.
    """
    offenders = _messages_built_by_a_helper_method(_library_sources(), _SUBJECT_CLASS_NAMES)
    assert not offenders, (
        f"helper methods building messages for assertions that may still pass: "
        f"{offenders}. Move the call below the `return self`."
    )


def test_no_message_builder_is_reachable_from_a_happy_path() -> None:
    """Rule B: the exemption, earned rather than granted.

    A helper allowed to format anywhere -- whether it is named in
    :data:`MESSAGE_BUILDERS` or claims the exemption in its own docstring -- is
    only harmless while every route to it starts on a failure path. This is what
    checks that, for all of them at once.
    """
    offenders = _builders_reachable_from_a_happy_path(_library_sources())
    assert not offenders, (
        f"message builders reachable while an assertion may still pass: {offenders}. "
        f"Move the call below the `return self`, or give the helper a caller that "
        f"is already on the failure path."
    )


def test_every_exempt_edge_is_still_load_bearing() -> None:
    """An exemption nobody needs is an allow-list waiting to be extended.

    Each entry in :data:`_EXEMPT_EDGES` has to still be doing something: drop it
    and the violation it covers must come back. When one stops mattering it comes
    out of the dict, and this is what says so.
    """
    sources = _library_sources()
    stale: list[str] = []
    for edge, reason in _EXEMPT_EDGES.items():
        assert reason.strip(), f"{edge} is exempt without a reason"
        without = {key: value for key, value in _EXEMPT_EDGES.items() if key != edge}
        with pytest.MonkeyPatch.context() as patch:
            patch.setitem(globals(), "_EXEMPT_EDGES", without)
            if not _builders_reachable_from_a_happy_path(sources):
                stale.append(f"{edge[0]} -> {edge[1]}")
    assert not stale, f"these exemptions no longer cover anything and should go: {stale}"


# ---------------------------------------------------------------------------
# The rules, tested against the anti-patterns they exist to catch
# ---------------------------------------------------------------------------
def test_the_structural_check_actually_detects_the_anti_pattern() -> None:
    """A rule nobody can fail is not a rule."""
    anti_pattern = (
        "def is_equal_to(self, expected):\n"
        "    message = f'to equal {expected!r}'\n"
        "    if self._subject == expected:\n"
        "        return self\n"
        "    return self._fail(message)\n"
    )
    assert _fstrings_outside_fail_calls(anti_pattern) == [(2, "is_equal_to")]

    correct = (
        "def is_equal_to(self, expected):\n"
        "    if self._subject == expected:\n"
        "        return self\n"
        "    return self._fail(f'to equal {expected!r}')\n"
    )
    assert _fstrings_outside_fail_calls(correct) == []


@pytest.mark.parametrize(
    ("label", "line"),
    [
        ("concatenation", "    message = 'to equal ' + repr(expected)"),
        ("percent", "    message = 'to equal %r' % (expected,)"),
        ("format", "    message = 'to equal {}'.format(expected)"),
        ("join", "    message = ' '.join(['to equal', repr(expected)])"),
        ("builder call", "    message = rendered(expected)"),
    ],
)
def test_rule_a_sees_every_form_the_f_string_scan_missed(label: str, line: str) -> None:
    """The four idioms an f-string scan is blind to, plus a builder called early.

    ``grep -rn "concatenation rather than an f-string" src/`` is why this matters:
    a rule that only sees f-strings teaches a codebase to concatenate.
    """
    source = (
        "def is_equal_to(self, expected):\n"
        f"{line}\n"
        "    if self._subject == expected:\n"
        "        return self\n"
        "    return self._fail(message)\n"
    )
    found = _messages_built_while_still_passing(source, frozenset({"rendered"}))
    assert [(lineno, owner) for lineno, owner, _ in found] == [(2, "is_equal_to")], label


@pytest.mark.parametrize(
    ("label", "body"),
    [
        ("module constant", "    wanted = _TO_EQUAL + repr(expected)"),
        ("local constant", "    prefix = 'to equal '\n    wanted = prefix + repr(expected)"),
        ("aliased constant", "    wanted = _TO_EQUAL\n    wanted += repr(expected)"),
        ("constant template", "    wanted = _TEMPLATE % (expected,)"),
    ],
)
def test_rule_a_follows_the_wording_into_a_name(label: str, body: str) -> None:
    """Rule A follows the wording through the name that holds it.

    A rule asking for a string *literal* as an operand of the ``+`` sees almost
    none of this library, which keeps its wording in module constants. Without the
    indirection resolved, ``_TO_EQUAL + repr(expected)`` above the comparison is a
    message built on every passing call, standing one name away from a rule
    written to catch exactly that.
    """
    source = (
        '_TO_EQUAL = "to equal "\n'
        '_TEMPLATE = "to equal %r"\n'
        "\n"
        "def is_equal_to(self, expected):\n"
        f"{body}\n"
        "    if self._subject == expected:\n"
        "        return self\n"
        "    return self._fail(wanted)\n"
    )
    found = _messages_built_while_still_passing(source, frozenset())
    assert [owner for _, owner, _ in found] == ["is_equal_to"], label


@pytest.mark.parametrize(
    ("label", "line"),
    [
        ("concatenation", "    detail = 'was ' + repr(self._subject)"),
        ("builder call", "    detail = rendered(self._subject)"),
    ],
)
def test_rule_a_allows_the_same_work_once_the_assertion_has_failed(label: str, line: str) -> None:
    """The line that matters is the ``return self``, not the ``_fail(...)`` call.

    Assertions here do real work between the happy exit and the failure -- pick
    out the missing items, read the formatting options -- and that work is free.
    """
    source = (
        "def is_equal_to(self, expected):\n"
        "    if self._subject == expected:\n"
        "        return self\n"
        f"{line}\n"
        "    return self._fail(detail)\n"
    )
    assert _messages_built_while_still_passing(source, frozenset({"rendered"})) == [], label


def test_rule_a_allows_a_caller_bug_report() -> None:
    """A caller-bug ``ValueError`` may build its text: it only runs when it raises."""
    source = (
        "def contains_in_order(self, *items):\n"
        "    if not items:\n"
        "        raise ValueError('needs at least one item, got ' + repr(items))\n"
        "    if _ordered(self._subject, items):\n"
        "        return self\n"
        "    return self._fail('to contain them in order')\n"
    )
    assert _messages_built_while_still_passing(source, frozenset()) == []


def test_rule_a_follows_the_message_into_a_helper_method() -> None:
    """The third arm, on the shape that gets past every other check here.

    Nothing here is a message builder and nothing here is exotic. The whole trick
    is that the ``+`` sits in a method the assertion calls rather than in the
    assertion itself, which is one ordinary refactor away from any assertion in
    the library.
    """
    sources = {
        "_mapping.py": (
            "class MappingExpect:\n"
            "    def _key_note(self, key):\n"
            '        """Name the key that was wanted."""\n'
            "        return 'to contain key ' + repr(key)\n"
            "\n"
            "    def contains_key(self, key):\n"
            "        note = self._key_note(key)\n"
            "        if key in self._subject:\n"
            "            return self\n"
            "        return self._fail(note)\n"
        )
    }
    assert _messages_built_by_a_helper_method(sources, frozenset({"MappingExpect"})) == {
        "_mapping.py": [("MappingExpect._key_note", "string concatenation", "_key_note")]
    }


def test_rule_a_leaves_a_helper_method_alone_on_the_failure_path() -> None:
    """The same helper, called where it belongs, is free.

    This is the pair the third arm needs: a rule that reported the method itself
    would make every message helper in the library illegal, and the point is
    *where it is called from*, not what it contains.
    """
    sources = {
        "_mapping.py": (
            "class MappingExpect:\n"
            "    def _key_note(self, key):\n"
            '        """Name the key that was wanted."""\n'
            "        return 'to contain key ' + repr(key)\n"
            "\n"
            "    def contains_key(self, key):\n"
            "        if key in self._subject:\n"
            "            return self\n"
            "        return self._fail(self._key_note(key))\n"
        )
    }
    assert _messages_built_by_a_helper_method(sources, frozenset({"MappingExpect"})) == {}


def test_rule_b_catches_a_builder_reached_through_a_helper() -> None:
    """The hole rule A cannot close: one hop of indirection.

    ``_looks_empty`` is not a message-building expression, so rule A has nothing
    to say about the assertion. Rule B follows the call.
    """
    sources = {
        "_subject.py": (
            "class Expect:\n"
            "    def is_empty(self):\n"
            "        if _looks_empty(self._subject):\n"
            "            return self\n"
            "        return self._fail('to be empty')\n"
        ),
        "_helpers.py": (
            "def _looks_empty(value):\n"
            "    _ = _preview(value)\n"
            "    return not value\n"
            "\n"
            "def _preview(value):\n"
            '    """Render a value. Failure path only."""\n'
            "    return repr(value)\n"
        ),
    }
    assert _builders_reachable_from_a_happy_path(sources) == [
        "_subject.py:is_empty -> _looks_empty -> _preview"
    ]


def test_rule_b_is_quiet_when_the_helper_stays_off_the_happy_path() -> None:
    """Same two modules, with the builder called after the assertion has failed."""
    sources = {
        "_subject.py": (
            "class Expect:\n"
            "    def is_empty(self):\n"
            "        if _looks_empty(self._subject):\n"
            "            return self\n"
            "        return self._fail('to be empty, but was ' + _preview(self._subject))\n"
        ),
        "_helpers.py": (
            "def _looks_empty(value):\n"
            "    return not value\n"
            "\n"
            "def _preview(value):\n"
            '    """Render a value. Failure path only."""\n'
            "    return repr(value)\n"
        ),
    }
    assert _builders_reachable_from_a_happy_path(sources) == []


def test_the_builder_set_is_derived_and_not_empty() -> None:
    """Rule B is only as good as the set it checks; an empty one would pass.

    Derived from the "Failure path only." docstrings, so a helper written
    tomorrow is covered without anyone editing this file.
    """
    builders = _message_builders(_library_sources())
    assert len(builders) > 50
    assert "format_value" in builders
    assert "render_operand" in builders
    assert {"_clipped", "rendered"} <= builders
