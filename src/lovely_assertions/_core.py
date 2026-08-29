"""The assertion primitive, the generic subject, and the soft-assertion scopes.

Two rules govern everything here.

**Deferred formatting.** An assertion tests, and formats *only* in its failure
branch. A message is never passed as an argument to a helper, because an f-string
argument is evaluated even when the assertion passes::

    def is_equal_to(self, expected: object, *, because: str = "") -> Self:
        if self._subject == expected:
            return self
        return self._fail(f"to equal {expected!r}, but was {self._subject!r}", because)

An f-string anywhere in this module but inside a ``_fail`` call is therefore a
bug: it charges every passing assertion for a message nobody will ever read.

**Zero-cost happy path.** A passing assertion performs the comparison and
``return self``: no frame inspection, no message construction, no ``ContextVar``
read, no allocation. Only the failure path may do any of those.
"""

from contextvars import ContextVar
from types import TracebackType
from typing import TYPE_CHECKING, Any, Self, cast, overload, override

from lovely_assertions._diff import describe_difference, render_operand
from lovely_assertions._equivalence import compare, differs, equivalency
from lovely_assertions._exceptions import AssertionFailure, hide_internal_frames
from lovely_assertions._formatters import format_value, pop_formatters, push_formatters
from lovely_assertions._names import FALLBACK_SUBJECT_NAME, resolve_subject_name

if TYPE_CHECKING:
    from collections.abc import Callable, Container, Sequence
    from contextvars import Token
    from enum import Enum

    # The subjects this module's narrowing overloads name. They import *this*
    # file, so the import only runs for the checkers -- which resolve the cycle
    # without complaint -- and never at runtime. `enum` above is there for the
    # same reason: naming a type is not importing it, and importing this package
    # must not import `enum`.
    from lovely_assertions._bool import BoolExpect
    from lovely_assertions._enum import EnumExpect
    from lovely_assertions._equivalence import Equivalency
    from lovely_assertions._formatters import FormatterToken, ValueFormatter
    from lovely_assertions._string import StringExpect

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = ["Expect", "Found", "SoftScope", "soft_assertions"]


class _Collector:
    """The failure sink belonging to one soft scope.

    Split out from :class:`SoftScope` on purpose: the reporting primitive is a
    module-level function, and a plain record with public attributes lets it
    write there without anything reaching into another object's privates.
    """

    __slots__ = ("closed", "failures", "path")

    def __init__(self, path: str, /) -> None:
        self.path: str = path
        self.failures: list[str] = []
        #: Set when the scope that owns this collector has reported and gone.
        #:
        #: A task started inside an open block inherits a *copy of the context*,
        #: and a copy holds the same collector object. Nothing can reset a
        #: ContextVar in somebody else's context, so when that task fails an
        #: assertion after the block has exited, it routes into this list -- which
        #: nobody will ever read, and pytest prints `passed`.
        #:
        #: The collector can say so even where the routing cannot be reached. See
        #: :func:`_report`.
        self.closed: bool = False


#: The innermost active collector, or ``None`` for ordinary raising behaviour.
#: A ``ContextVar`` rather than a global: scopes are then isolated per thread and
#: per asyncio task, which is what makes soft assertions safe under a parallel
#: test runner. A global would let one test's scope swallow another test's
#: failures, and the swallowing is silent.
_ACTIVE_COLLECTOR: ContextVar["_Collector | None"] = ContextVar(
    "lovely_assertions.active_collector", default=None
)


def _render_failure(expectation: str, because: str, given: str | None = None) -> str:
    """Build ``Expected {name} {expectation}{because}.`` -- failure path only.

    An expectation may carry a detail block after its first line -- a diff, a list
    of nested failures. The sentence ends, and the reason attaches, at the end of
    the *first* line; the block follows. Appending the reason to the whole thing
    would leave ``... extra keys: ['id'] because the sync ran.``, hanging the
    reason off the last line of a diff.
    """
    # An explicit name also spares the frame walk, which is the expensive part.
    name = given or resolve_subject_name() or FALLBACK_SUBJECT_NAME
    collector = _ACTIVE_COLLECTOR.get()
    if collector is not None and collector.path:
        name = f"{collector.path}/{name}"
    sentence, newline, block = expectation.partition("\n")
    if because:
        # Users write it both ways; neither should read "because because".
        reason = because[8:].lstrip() if because[:8].casefold() == "because " else because
        sentence = f"{sentence} because {reason}"
    return f"Expected {name} {sentence}." + newline + block


def describe_predicate(predicate: object) -> str:
    """Name a predicate for a failure message. Failure path only."""
    name = getattr(predicate, "__name__", None)
    if isinstance(name, str) and name != "<lambda>":
        return name
    return "the predicate"


def collect_failures(
    inspector: "Callable[[Any], object]",
    subject: Any,  # noqa: ANN401  (whatever the caller handed to `expect`)
    /,
    predicate_form: str = "",
) -> list[str]:
    """Run ``inspector`` with failures collected rather than raised.

    Used by the inspector-taking assertions -- ``satisfies``, ``satisfies_any``,
    ``satisfies_none``, ``all_satisfy`` and ``satisfies_respectively`` -- and by
    nothing else, which is why the guard below lives here rather than at each of
    their call sites, where a newly added one could forget it. A non-assertion
    exception still propagates: a broken inspector is a bug in the test, not a
    finding about the subject.

    **A ``bool`` handed back is refused.** These take an *inspector*, which
    asserts on what it is given. Other methods on the same subjects take a
    *predicate*, which returns a verdict instead -- ``matches``, ``only_contains``,
    ``satisfies_in_any_order``, ``contains_matching`` and their neighbours all
    teach that lambda shape, so writing one here is a short step away and the
    checkers cannot see it: ``Callable[[T], object]`` accepts ``bool`` happily.
    An inspector that returns ``True`` or ``False`` has asserted nothing, so the
    call is unconditionally green -- the worst thing an assertion can be.

    ``predicate_form`` names the sibling that would have been right, where one
    exists. Two pointer comparisons on the happy path, and nothing built unless
    the guard fires.
    """
    collector = _Collector("")
    token = _ACTIVE_COLLECTOR.set(collector)
    try:
        outcome = inspector(subject)
    finally:
        _ACTIVE_COLLECTOR.reset(token)
    if outcome is True or outcome is False:
        raise TypeError(_predicate_not_inspector(outcome, predicate_form))
    return collector.failures


def _predicate_not_inspector(outcome: bool, predicate_form: str, /) -> str:
    """Explain the inspector/predicate mix-up. Failure path only."""
    remedy = (
        "use `" + predicate_form + "` to pass a predicate, or assert instead: "
        if predicate_form
        else "assert instead: "
    )
    return (
        "the callback returned "
        + repr(outcome)
        + " instead of asserting anything, so this would have passed whatever the "
        + "subject was. An inspector asserts; a predicate returns a verdict. "
        + remedy
        + "`lambda it: expect(it).is_positive()`"
    )


#: Guard for the composition assertions. Nothing to satisfy either passes
#: whatever the subject is or can never pass; both are bugs in the test.
_NEEDS_BRANCHES = "at least one alternative is required"


def _why_falsy(value: object, /) -> str:
    """Name the *kind* of falsy. Failure path only.

    A container says it is empty, a builtin shows its value, and anything else
    names the method that said no -- because a domain type's ``repr`` is an
    address, which explains nothing.
    """
    if value is None:
        return "it is None"
    kind = type(value)
    if hasattr(kind, "__len__"):
        return "it is an empty " + kind.__name__
    if kind.__module__ == "builtins":
        return "it is " + render_operand(value)
    return kind.__name__ + ".__bool__ returned False"


def _render_bullet(item: str, bullet: str, indent: str, /) -> list[str]:
    """One collected failure as a bullet, its own detail block indented under it.

    The full stop comes off the *sentence*, which is the first line and nothing
    else. Taking it off the whole message only ever reaches the last line, so a
    finding carrying a difference block would keep the full stop that a one-line
    finding beside it had just lost.
    """
    head, newline, block = item.partition("\n")
    lines = [bullet + head.removesuffix(".")]
    if newline:
        lines.extend(indent + line for line in block.splitlines())
    return lines


def _render_alternative(index: int, collected: list[str], /) -> str:
    """One branch's findings, indented under a numbered heading."""
    lines = ["  alternative " + str(index) + ":"]
    for item in collected:
        lines.extend(_render_bullet(item, "    - ", "      "))
    return "\n".join(lines)


def _render_findings(collected: list[str], /) -> str:
    """Lay collected failures out as a list, keeping each one's own block with it.

    A nested failure can run to several lines -- a difference block, most often --
    and the continuation lines have to sit under their bullet rather than flush
    against the margin, or the reader cannot tell which finding they belong to.
    ``_render_aggregate`` does the same for a soft scope.
    """
    lines: list[str] = []
    for item in collected:
        lines.extend(_render_bullet(item, "  - ", "    "))
    return "\n".join(lines)


def _render_aggregate(failures: list[str]) -> str:
    """Build the message a soft scope raises on the way out."""
    count = len(failures)
    noun = "assertion" if count == 1 else "assertions"
    lines = [f"{count} {noun} failed:"]
    for index, message in enumerate(failures, 1):
        # A message may run to several lines; its continuation is indented to sit
        # under the numbered item rather than under the list.
        head, newline, block = message.partition("\n")
        lines.append(f"  ({index}) {head}")
        if newline:
            lines.extend(f"      {line}" for line in block.splitlines())
    return "\n".join(lines)


#: Guard for the variadic assertions. A call with nothing to look for either
#: passes whatever the subject is -- a test that asserts nothing -- or could never
#: pass at all. Both are bugs in the test rather than findings about the subject,
#: so they are raised as a ``ValueError``, not collected as a failure.
_NEEDS_VALUES = "at least one value to look for is required"


class _AbsorbingSubject:
    """Stand-in returned when a *narrowing* assertion fails inside a soft scope.

    The narrowed subject does not exist -- there is nothing to assert on. Raising
    ``AttributeError`` would be noise, and letting the chain continue against the
    un-narrowed value would report a second failure derived from the first. So
    everything downstream is absorbed instead, and the soft report keeps one
    message per root cause.
    """

    __slots__ = ()

    def __getattr__(self, name: str) -> Any:  # noqa: ANN401  (absorbs every attribute)
        return self

    def __call__(self, *_args: object, **_kwargs: object) -> Any:  # noqa: ANN401  (absorbs calls)
        return self

    @override
    def __repr__(self) -> str:
        return "<lovely-assertions: narrowing failed, further assertions absorbed>"


_ABSORBING: Any = _AbsorbingSubject()

#: The default equivalence configuration, built once. It is immutable, so a
#: shared instance is safe, and building one per call would be an allocation
#: on the path of an assertion that is about to walk two graphs anyway.
_ANY_SHAPE = equivalency()


class Expect[T]:
    """A disposable, typed wrapper around the value under test.

    Built by :func:`~lovely_assertions.expect`, chained on, and thrown away. ``T``
    is the subject's type; it is what ``.subject`` re-exposes after an assertion
    has narrowed it.
    """

    #: ``_name`` is declared but deliberately not assigned in ``__init__``. An
    #: unassigned slot costs the wrapper one pointer and its construction
    #: nothing, where assigning it would put an attribute store on every subject
    #: ever built. The failure path reads it with a default instead.
    __slots__ = ("_name", "_subject")

    def __init__(self, subject: T, /) -> None:
        self._subject: T = subject

    @override
    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._subject!r})"

    # -- continuations -----------------------------------------------------
    @property
    def subject(self) -> T:
        """The value under test, re-typed by whatever narrowing has happened."""
        return self._subject

    @property
    def and_(self) -> Self:
        """Re-chain another assertion on the same subject. A typed no-op."""
        return self

    # -- the primitive -----------------------------------------------------
    def _fail(
        self, expectation: str, because: str = "", /, *, cause: BaseException | None = None
    ) -> Self:
        """Report a failed assertion. **Failure path only** -- never call this to test.

        Renders the message, then routes: append to the collector when a soft
        scope is active, otherwise raise. Returns ``Self`` so that a soft block
        keeps chaining past the failure instead of stopping at the first one.

        ``cause`` chains the raised failure onto an exception that is the reason
        for it -- the one an exception assertion caught, for instance. Without it
        the assertion message would replace the traceback the reader actually
        needs. Ignored in a soft scope, where nothing is raised to chain onto.
        """
        _report(expectation, because, cause, getattr(self, "_name", None))
        return self

    def _fail_narrowing(
        self, expectation: str, because: str = "", /, *, cause: BaseException | None = None
    ) -> Any:  # noqa: ANN401  (the narrowed subject does not exist; a stand-in stands in)
        """``_fail`` for assertions that were supposed to produce a *narrowed* subject.

        There is no narrowed subject to return, so a soft scope gets a stand-in
        that absorbs the rest of the chain rather than a wrapper whose static type
        is now a lie.
        """
        _report(expectation, because, cause, getattr(self, "_name", None))
        return _ABSORBING

    def described_as(self, name: str, /) -> Self:
        """Name this subject explicitly, instead of recovering it from the source.

        Subject recovery reads the statement that built the subject, which is the
        right answer almost always and no answer at all in two places: a loop,
        where every iteration names the same variable, and a helper, where the
        source names the helper's parameter rather than the caller's value.

            for index, row in enumerate(rows):
                expect(row).described_as(f"rows[{index}]").is_equal_to(...)

        ``expect(value, name=...)`` is the same thing said earlier.
        """
        self._name = name
        return self

    # -- truthiness ---------------------------------------------------------
    def is_truthy(self, *, because: str = "") -> Self:
        """Assert ``bool(subject)`` is true.

        Worth having over ``matches(bool)`` because Python is falsy in several
        unrelated ways and which one applies is the entire content of the failure:
        ``None``, a zero, an empty container, or a ``__bool__`` that said no.
        ``matches`` could only report that a predicate returned False.
        """
        if self._subject:
            return self
        return self._fail(f"to be truthy, but {_why_falsy(self._subject)}", because)

    def is_falsy(self, *, because: str = "") -> Self:
        """Assert ``bool(subject)`` is false.

        ``None``, a zero, an empty container and a ``__bool__`` that returned
        False all pass, so this says less than the assertion for the case you
        actually mean -- :meth:`is_none` where the value should be missing, an
        emptiness assertion where it is a container. :meth:`is_truthy` is the
        complement.
        """
        if not self._subject:
            return self
        return self._fail(f"to be falsy, but was {render_operand(self._subject)}", because)

    # -- composition (chaining is an AND; these are the other two) -----------
    def satisfies_any(self, *branches: "Callable[[Self], object]", because: str = "") -> Self:
        """Assert at least one branch holds.

        Chaining is an implicit AND; this and :meth:`satisfies_none` are the other
        two connectives. Each branch receives the subject itself, so it stays
        concretely typed -- a string subject autocompletes to string assertions
        inside the lambda, which a type-erased matcher object could never do.

        Branches run in order and stop at the first that holds, so a later branch
        is not evaluated once the assertion is settled. When none holds, the
        failure lists every branch's findings under its own number.

        Raises :class:`ValueError` when no branch is given: a call with nothing to
        satisfy asserts nothing at all.
        """
        if not branches:
            raise ValueError(_NEEDS_BRANCHES)
        findings: list[str] = []
        for index, branch in enumerate(branches, 1):
            collected = collect_failures(branch, self)
            if not collected:
                return self
            findings.append(_render_alternative(index, collected))
        return self._fail(
            f"to satisfy at least one of {len(branches)} alternatives, but none did\n"
            + "\n".join(findings),
            because,
        )

    def satisfies_none(self, *branches: "Callable[[Self], object]", because: str = "") -> Self:
        """Assert no branch holds -- the complement of :meth:`satisfies_any`.

        Branches run in order and stop at the first that holds, which is the one
        the failure names. Raises :class:`ValueError` when no branch is given.
        """
        if not branches:
            raise ValueError(_NEEDS_BRANCHES)
        for index, branch in enumerate(branches, 1):
            if not collect_failures(branch, self):
                return self._fail(
                    f"to satisfy none of {len(branches)} alternatives,"
                    f" but alternative {index} held",
                    because,
                )
        return self

    # -- equality ----------------------------------------------------------
    def is_equal_to(self, expected: object, /, *, because: str = "") -> Self:
        """Assert ``subject == expected``.

        The subject's own ``__eq__`` decides, with everything that implies: a NaN
        never equals itself, and a type with a lenient ``__eq__`` passes here
        where :meth:`is_equivalent_to`, which compares members rather than asking
        the type, would not.

        On failure the two reprs are followed by an account of *how* they differ --
        a unified diff for multi-line text, the first offending index for
        sequences, the keys that moved for mappings. That is the whole reason to
        prefer this over a bare ``assert a == b`` on a composite value, and it
        costs nothing until an assertion fails.
        """
        if self._subject == expected:
            return self
        return self._fail(
            f"to equal {render_operand(expected)}, but was {render_operand(self._subject)}"
            f"{describe_difference(self._subject, expected)}",
            because,
        )

    def is_not_equal_to(self, unexpected: object, /, *, because: str = "") -> Self:
        """Assert ``subject != unexpected``.

        Asks ``!=`` rather than negating ``==``, so a type that defines the two
        independently is taken at its word. The complement of :meth:`is_equal_to`,
        and it carries no difference block: there is nothing to explain about two
        values that were supposed to differ and did.
        """
        if self._subject != unexpected:
            return self
        return self._fail(f"not to equal {render_operand(unexpected)}", because)

    # -- structural equivalence ---------------------------------------------
    def is_equivalent_to(
        self,
        expected: object,
        /,
        *,
        options: "Equivalency | None" = None,
        because: str = "",
    ) -> Self:
        """Assert the subject matches ``expected`` member by member, recursively.

        Where :meth:`is_equal_to` asks the subject's ``__eq__``, this walks both
        graphs and compares what they are made of -- dataclasses, NamedTuples,
        attrs and pydantic models, mappings, collections, and anything with
        ``__slots__`` or a ``__dict__``. So two objects of unrelated types that
        carry the same values are equivalent, and a type that never defined
        ``__eq__`` can be compared at all::

            expect(response).is_equivalent_to(
                expected, options=equivalency().excluding("id", "created_at")
            )

        ``options`` is an immutable builder, so one configuration can be named at
        module scope and reused across a suite. Every difference is reported at
        once, each with the path that locates it -- ``address.city``,
        ``items[3]`` -- and those paths are exactly what
        :meth:`~lovely_assertions.Equivalency.excluding_path` accepts.

        **Ordering is strict by default**, which is the opposite of
        FluentAssertions and deliberate: in Python a ``list`` is ordered by
        definition and ``set`` exists for the other case, so a default that let
        ``[1, 2]`` match ``[2, 1]`` would pass tests that ought to fail. Say
        ``ignoring_order()`` when you mean it.
        """
        report = compare(self._subject, expected, options if options is not None else _ANY_SHAPE)
        if not report:
            return self
        return self._fail(f"to be equivalent to {render_operand(expected)}{report}", because)

    def is_not_equivalent_to(
        self,
        expected: object,
        /,
        *,
        options: "Equivalency | None" = None,
        because: str = "",
    ) -> Self:
        """Assert the subject differs from ``expected`` somewhere.

        The complement of :meth:`is_equivalent_to`, and it takes the same options
        -- asserting that two payloads differ *once the volatile fields are
        excluded* is the useful form, and it needs the same exclusions.

        Asked through :func:`~lovely_assertions._equivalence.differs` rather than
        :func:`~lovely_assertions._equivalence.compare`, because this is the one
        assertion whose **passing** branch is the expensive one: a report of every
        difference, built and then dropped unread. ``differs`` is the same walk
        stopped at the first disagreement.
        """
        if differs(self._subject, expected, options if options is not None else _ANY_SHAPE):
            return self
        return self._fail(f"not to be equivalent to {render_operand(expected)}", because)

    # -- identity ----------------------------------------------------------
    def is_same_as(self, expected: object, /, *, because: str = "") -> Self:
        """Assert ``subject is expected`` -- the same object, not merely an equal one.

        Use :meth:`is_equal_to` when equality is what you mean. Identity of small
        integers and short strings is an interpreter detail rather than a promise,
        so asserting it on them tests the interpreter and not the code.
        """
        if self._subject is expected:
            return self
        return self._fail(
            f"to be the same object as {render_operand(expected)},"
            f" but was {render_operand(self._subject)}",
            because,
        )

    def is_not_same_as(self, unexpected: object, /, *, because: str = "") -> Self:
        """Assert ``subject is not unexpected``.

        The complement of :meth:`is_same_as`. Two equal but distinct objects pass:
        this is about identity, so a copy is not the original.
        """
        if self._subject is not unexpected:
            return self
        return self._fail(f"not to be the same object as {render_operand(unexpected)}", because)

    # -- None (and the narrowing primitive) --------------------------------
    def is_none(self, *, because: str = "") -> Self:
        """Assert the subject is ``None``.

        Identity against ``None``, never ``== None``, so a type with a permissive
        ``__eq__`` cannot talk its way past. :meth:`is_not_none` is the
        complement, and it narrows the static type as well.
        """
        if self._subject is None:
            return self
        return self._fail(f"to be None, but was {render_operand(self._subject)}", because)

    def is_not_none[S](self: "Expect[S | None]", *, because: str = "") -> "Expect[S]":
        """Assert the subject is not ``None``, and hand back a subject typed without it.

        This is the narrowing primitive. It returns ``self``: the wrapper it
        hands back is the same object, so the assertion stays free, and the
        static widening is sound because ``self`` really is an ``Expect[S]`` once
        ``None`` is excluded.

        The re-typing lands on the **returned** subject, not on the caller's
        variable -- a ``TypeIs`` can only narrow a function's first positional
        argument, and ``expect()`` has captured the subject inside a wrapper.
        Re-bind to use it::

            name = expect(raw).is_not_none().subject   # str, guaranteed

        Note the deliberate omission: this does *not* re-specialise to
        ``StringExpect`` and friends. It could, statically -- but a user's own
        ``class Mine(Expect[str])`` would match that overload too and be handed
        back mislabelled. A sound widening beats a convenient lie.
        """
        if self._subject is not None:
            # Sound: `None` has just been excluded, so this same object *is* an
            # `Expect[S]`. The cast states what the checker cannot derive.
            return cast("Expect[S]", self)
        return cast("Expect[S]", self._fail_narrowing("not to be None, but it was", because))

    # -- membership ---------------------------------------------------------
    def is_one_of(self, *options: object, because: str = "") -> Self:
        """Assert the subject equals one of ``options``.

        Equality decides, so the options need be neither hashable nor of one
        type. Raises :class:`ValueError` when no option is given, since a call
        with nothing to look for could never pass. Reach for :meth:`is_in` when
        the alternatives are already a container rather than a literal list.
        """
        if not options:
            raise ValueError(_NEEDS_VALUES)
        if self._subject in options:
            return self
        return self._fail(
            "to be one of ("
            + ", ".join(format_value(option) for option in options)
            + ("," if len(options) == 1 else "")
            + f"), but was {render_operand(self._subject)}",
            because,
        )

    def is_in(self, container: "Container[object]", /, *, because: str = "") -> Self:
        """Assert the subject is contained in ``container``.

        The container's ``__contains__`` decides, which is worth remembering for
        the types that answer it their own way: a ``str`` matches substrings, and
        a ``range`` answers arithmetically without materialising anything. Use
        :meth:`is_one_of` to give the alternatives inline instead.
        """
        if self._subject in container:
            return self
        return self._fail(
            f"to be in {render_operand(container)}, but was {render_operand(self._subject)}",
            because,
        )

    def is_not_in(self, container: "Container[object]", /, *, because: str = "") -> Self:
        """Assert the subject is not contained in ``container``.

        The complement of :meth:`is_in`, asking the same ``__contains__``.
        """
        if self._subject not in container:
            return self
        return self._fail(
            f"not to be in {render_operand(container)}, but was {render_operand(self._subject)}",
            because,
        )

    # -- predicates ---------------------------------------------------------
    def matches(self, predicate: "Callable[[T], bool]", /, *, because: str = "") -> Self:
        """Assert ``predicate(subject)`` is true.

        The truth of the result decides, not its type, so a predicate returning a
        non-empty container passes. The failure can say no more than that the
        predicate said no, and names it by its ``__name__`` -- a lambda has none
        worth printing and is reported as the predicate. Where the *reason*
        matters, prefer :meth:`satisfies`, whose nested assertions each explain
        themselves.
        """
        if predicate(self._subject):
            return self
        return self._fail(
            f"to match {describe_predicate(predicate)},"
            f" but {render_operand(self._subject)} did not",
            because,
        )

    def satisfies(self, inspector: "Callable[[T], object]", /, *, because: str = "") -> Self:
        """Assert the subject satisfies the nested assertions in ``inspector``.

        Failures inside ``inspector`` are collected rather than raised one at a
        time, so a single call reports everything that was wrong with the subject,
        each finding on its own line. Any other exception propagates untouched: a
        broken inspector is a bug in the test, not a finding about the subject.

        The callback must *assert*, not return a verdict. One that hands back
        ``True`` or ``False`` has asserted nothing and would pass whatever the
        subject was, so it raises :class:`TypeError` and points at :meth:`matches`
        instead.
        """
        collected = collect_failures(inspector, self._subject, "matches")
        if not collected:
            return self
        return self._fail(
            "to satisfy the inspection\n" + _render_findings(collected),
            because,
        )

    # -- type ---------------------------------------------------------------
    # The three narrowing methods below carry the head of the `expect()` overload
    # table, so that what you continue on is the subject `expect()` really builds.
    # Declaring `Expect[S]` instead would withhold a catalogue the object already
    # has: `expect(raw).as_type(str).starts_with(..)` would be a checker error
    # against a genuine `StringExpect` -- this library's whole claim, that the
    # checker knows which assertions a subject has, failing at the exact point it
    # is meant to pay off.
    #
    # `Enum` leads, as it does in `expect()` and for the same reason: a `StrEnum`
    # member's class *is* a `str` subclass, so `type[str]` would otherwise claim
    # `type[Colour]` and promise a catalogue the runtime does not build.
    #
    # **There is deliberately no `int` or `float` entry**, though it is the one a
    # reader will look for first. `bool` is a subclass of `int`, and `expect()`
    # sends a `bool` to `BoolExpect`, which is not a `NumericExpect` -- so
    # `is_instance_of(int)` on `True` really does hand back a `BoolExpect`, and
    # declaring `NumericExpect` would make `expect(flag).is_instance_of(int)
    # .which.is_positive()` type-check and then raise `AttributeError`. A checker
    # that green-lights a crash is worse than one that withholds a method, so
    # that call is declared `Expect[int]` and the numeric catalogue is reached by
    # asserting on `.subject` instead. The same objection rules out a
    # re-specialised `is_not_none`.
    #
    # What the entries that *are* here promise, exactly: the type **argument**
    # decides the subject. The value's own type decides nothing, so
    # `as_type(str)` on a value that happens to be a `StrEnum` member is declared
    # `StringExpect` and built as an `EnumExpect`. That gap belongs to the
    # dispatch rather than to this table: `expect(x)` for an `x: str` holding a
    # `StrEnum` member also answers `StringExpect` statically and builds an
    # `EnumExpect`. Closing it needs the dispatch to build from the named type
    # rather than from the value.
    #
    # The table also stops at the scalars: `date`, `Path`, `Decimal` and the rest
    # fall to the bare overload, which is unhelpful rather than wrong. Each entry
    # added here is another copy of the table `expect()` already declares, and so
    # one more place the two halves can drift apart.
    #
    # **A leading entry claims every argument that is not a named type.** A mock
    # is the case that shows up in real suites -- typeshed puts an `Any` in
    # `NonCallableMock`'s MRO, so `type[Mock]` satisfies `type[Enum]`, the same
    # divergence `expect()` has one level down. It is not the only case, and the
    # wider one matters more: an argument annotated `type[Any]`, or the bare
    # `type`, also satisfies `type[Enum]`, so a dynamically-typed call site reads
    # `EnumExpect` where it would otherwise read `Expect`. Measured, on this
    # table: pyright answers `EnumExpect[Any]` for `type[Any]` and
    # `EnumExpect[Unknown]` for `type`; mypy answers `Any` for the first and
    # `EnumExpect[Never]` for the second.
    #
    # That is a real cost and it is paid on purpose. No ordering avoids it --
    # whichever entry leads is the one a `type[Any]` lands on, and putting `bool`
    # or `str` first would be worse, since those flatten `V` to `bool` or `str`
    # where `Enum` at least leaves `.subject` alone. Nor can it be pinned by a
    # type-checking test: the two checkers disagree about the answer, so an
    # `assert_type` written for one fails the other.
    @overload
    def is_instance_of[S: "Enum"](
        self, expected_type: type[S], /, *, because: str = ...
    ) -> "Found[Self, S, EnumExpect[S]]": ...
    @overload
    def is_instance_of(
        self, expected_type: type[bool], /, *, because: str = ...
    ) -> "Found[Self, bool, BoolExpect]": ...
    @overload
    def is_instance_of(
        self, expected_type: type[str], /, *, because: str = ...
    ) -> "Found[Self, str, StringExpect]": ...
    @overload
    def is_instance_of[S](
        self, expected_type: type[S], /, *, because: str = ...
    ) -> "Found[Self, S]": ...
    def is_instance_of(self, expected_type: type[Any], /, *, because: str = "") -> Any:
        """Assert ``isinstance(subject, expected_type)``; continue with ``.which``.

        A subclass counts; use :meth:`is_exactly_instance_of` where it must not.
        Returns a :class:`Found`, so ``.and_`` goes on asserting about the
        original subject while ``.which`` continues on the same value re-typed --
        and re-dispatched, so ``.which`` after ``is_instance_of(str)`` carries the
        string catalogue. Inside a soft scope a failure here has no narrowed
        subject to hand back, so the rest of the chain is absorbed and one failure
        is reported rather than a second derived from it.
        """
        subject = self._subject
        if isinstance(subject, expected_type):
            return Found(self, subject, expected_type)
        return self._fail_narrowing(
            f"to be an instance of {expected_type.__name__}, but was {type(subject).__name__}",
            because,
        )

    def is_not_instance_of(self, unexpected_type: type[object], /, *, because: str = "") -> Self:
        """Assert the subject is not an instance of ``unexpected_type``.

        A subclass *is* an instance, so a subject of a subclass fails here. Use
        :meth:`is_not_exactly_instance_of` to rule out only the exact type. Does
        not narrow: there is nothing to continue on but the original subject, so
        it returns ``self``.
        """
        if not isinstance(self._subject, unexpected_type):
            return self
        return self._fail(
            f"not to be an instance of {unexpected_type.__name__},"
            f" but was {type(self._subject).__name__}",
            because,
        )

    @overload
    def is_exactly_instance_of[S: "Enum"](
        self, expected_type: type[S], /, *, because: str = ...
    ) -> "Found[Self, S, EnumExpect[S]]": ...
    @overload
    def is_exactly_instance_of(
        self, expected_type: type[bool], /, *, because: str = ...
    ) -> "Found[Self, bool, BoolExpect]": ...
    @overload
    def is_exactly_instance_of(
        self, expected_type: type[str], /, *, because: str = ...
    ) -> "Found[Self, str, StringExpect]": ...
    @overload
    def is_exactly_instance_of[S](
        self, expected_type: type[S], /, *, because: str = ...
    ) -> "Found[Self, S]": ...
    def is_exactly_instance_of(self, expected_type: type[Any], /, *, because: str = "") -> Any:
        """Assert ``type(subject) is expected_type`` -- a subclass does not count.

        Use :meth:`is_instance_of` where a subclass should pass. This is the one
        narrowing method whose declaration has no gap in it at all: an exact type
        leaves no room for a subclass with a subject of its own, so ``.which`` is
        the subject ``expect()`` builds, never a near relative.
        """
        subject = self._subject
        subject_type = type(subject)
        if subject_type is expected_type:
            return Found(self, subject)
        return self._fail_narrowing(
            f"to be exactly {expected_type.__name__}, but was {subject_type.__name__}",
            because,
        )

    def is_not_exactly_instance_of(
        self, unexpected_type: type[object], /, *, because: str = ""
    ) -> Self:
        """Assert ``type(subject) is not unexpected_type``.

        A subclass of ``unexpected_type`` passes, which is the whole difference
        from :meth:`is_not_instance_of`.
        """
        if type(self._subject) is not unexpected_type:
            return self
        return self._fail(f"not to be exactly {unexpected_type.__name__}", because)

    @overload
    def as_type[S: "Enum"](
        self, expected_type: type[S], /, *, because: str = ...
    ) -> "EnumExpect[S]": ...
    @overload
    def as_type(self, expected_type: type[bool], /, *, because: str = ...) -> "BoolExpect": ...
    @overload
    def as_type(self, expected_type: type[str], /, *, because: str = ...) -> "StringExpect": ...
    @overload
    def as_type[S](self, expected_type: type[S], /, *, because: str = ...) -> "Expect[S]": ...
    def as_type(self, expected_type: type[Any], /, *, because: str = "") -> Any:
        """Assert the subject's type and continue on the narrowed value.

        Sugar for ``is_instance_of(t).which``, for when the type check is a step
        on the way somewhere rather than the point of the assertion. Its overloads
        are that sugar read through: entry for entry, they are what
        :meth:`is_instance_of` promises with ``.which`` already applied. The
        original subject is gone from the chain, so use :meth:`is_instance_of` and
        ``.and_`` where you still have something to say about it.
        """
        return self.is_instance_of(expected_type, because=because).which


class Found[P, V, A = Expect[V]]:
    """The result of an assertion that *found* a value inside the subject.

    ``P`` is the subject the assertion was made on and ``V`` the value that was
    found: ``.and_`` goes back to the first, ``.which`` descends into the second,
    and ``.subject`` hands the found value over untyped by any wrapper.

    ``A`` is what ``.which`` hands back. It defaults to ``Expect[V]``, so the
    plain ``Found[Self, V]`` that most producers write means an ordinary subject.
    A producer that knows better says so: :meth:`Expect.is_instance_of` returns
    ``Found[Self, str, StringExpect]`` for ``type[str]``, because that is the
    object ``expect()`` builds, and declaring ``Expect[str]`` would withhold the
    string catalogue from a value that has it.

    **Why a type parameter rather than an overloaded ``which``.** The obvious
    shape is three overloaded properties differing in the ``self`` type.
    pyright refuses it outright -- ``Argument of type "property" cannot be
    assigned to parameter "func" of type "_F@overload"``, plus a
    ``reportRedeclaration`` per stub -- and then evaluates the attribute as
    ``Any``, which is a worse declaration than the one it would have replaced.
    The parameter moves the choice to the producer, which is the only place that
    knows the answer anyway: ``which`` sees a value, and a value's type is not
    what decides its subject here (see :meth:`Expect.is_instance_of`).
    """

    __slots__ = ("_named_type", "_parent", "_value")

    def __init__(self, parent: P, value: V, named_type: type[Any] | None = None, /) -> None:
        self._parent: P = parent
        self._value: V = value
        #: The type the *caller* named, where they named one. See :attr:`which`.
        self._named_type: type[Any] | None = named_type

    @override
    def __repr__(self) -> str:
        return f"Found({self._value!r})"

    @property
    def and_(self) -> P:
        """Continue asserting on the original subject."""
        return self._parent

    @property
    def which(self) -> A:
        """Continue asserting on the value that was found.

        The ``cast`` is where the declaration and the dispatch meet. ``expect()``
        answers ``Expect[V]`` for an unconstrained ``V`` and can answer nothing
        better from here -- the producer's overload is what knows ``A``. The cast
        itself costs one call and allocates nothing; a continuation is not an
        assertion, so the no-allocation rule that governs a passing assertion does
        not reach here, and the ``expect()`` dispatch this wraps dwarfs it anyway.

        **Where the caller named a type, that type decides**, and not the value.
        ``expect(colour).as_type(str)`` is a checker-visible promise of a
        ``StringExpect``, and dispatching on the value instead would break it for
        exactly one shape: a ``StrEnum`` member *is* a ``str``, but ``expect()``
        answers ``EnumExpect`` for it, on purpose. ``.starts_with(...)`` would
        then type-check under both checkers and raise ``AttributeError`` at
        runtime -- the one thing this library exists to prevent. The type the
        caller wrote is the one they meant, so
        :func:`~lovely_assertions._subjects.subject_for` is asked about that type
        and the runtime stays in step with the overloads. Where no type was named,
        the value is dispatched as ``expect()`` would dispatch it.
        """
        # Imported here rather than at module scope: `_subjects` imports this module.
        from lovely_assertions._subjects import expect, subject_for  # noqa: PLC0415

        named = self._named_type
        if named is not None:
            factory = subject_for(named)
            if factory is not None:
                return cast("A", factory(self._value))
        return cast("A", expect(self._value))

    @property
    def whose_value(self) -> A:
        """The mapping-flavoured spelling of :attr:`which`; the same object.

        ``expect(rows).contains_key("id").whose_value.is_equal_to(7)`` reads the way
        the assertion is meant, where ``.which`` would leave the reader working out
        what "which" refers to.
        """
        return self.which

    @property
    def subject(self) -> V:
        """The value that was found, re-typed."""
        return self._value


#: Refused re-entry: ``with scope: with scope:`` on one scope object. A scope
#: object *is* one collector and one path, so entering one inside itself has no
#: meaning to implement: its name would compose with its own, and it would hand
#: its failures to itself. It is a hard error rather than a curiosity because of
#: what an unchecked second ``__enter__`` would do -- overwrite the token that
#: puts the routing back, so the outer ``__exit__`` finds nothing to reset and
#: leaves the collector *active for the rest of the thread*. Every failing
#: assertion after that goes into a sink nobody reads, which under a test runner
#: is a whole file of tests passing without asserting anything.
#:
#: Re-*use* stays legal, because a closed scope has nothing to alias:
#: :meth:`SoftScope.__enter__` recomputes the path and starts the block empty.
_ALREADY_OPEN = (
    "this soft-assertion scope is already open. A scope object is not reentrant:"
    " nesting it inside itself would compose its name with its own and hand its"
    " failures to itself. Open a second scope for the inner block:"
    " `with soft_assertions('inner'):`"
)

#: Left without ever having been opened -- a bare ``__exit__``, or a second one.
#: There is no routing to restore, and reporting an aggregate for a block that
#: never ran would invent a result.
_NOT_OPEN = (
    "this soft-assertion scope is not open, so there is nothing to leave."
    " `__exit__` ran without a matching `__enter__`, or ran twice"
)

#: Scopes left in the wrong order -- only reachable by calling ``__enter__`` and
#: ``__exit__`` by hand, since a ``with`` statement cannot do it.
_OUT_OF_ORDER = (
    "soft-assertion scopes were left out of order: a scope opened inside this one"
    " is still open. Failure routing has been switched off rather than left"
    " pointing at a scope that has ended -- leave scopes in the order they were"
    " opened"
)

#: Opened in one thread or task and left in another. The token belongs to the
#: context that made it, and ``ContextVar.reset`` says so with a ``ValueError``
#: that names neither the scope nor the mistake.
_FOREIGN_CONTEXT = (
    "this soft-assertion scope was opened in a different thread or task than the"
    " one leaving it. A scope belongs to the context that opened it: open and"
    " leave it in the same one"
)


class SoftScope:
    """Collects assertion failures instead of raising them, one scope at a time.

    Scopes nest. Their names compose into a context path that prefixes the subject
    name, so a failure reads ``Expected Test1/Test2/items to be empty ...``. A
    nested scope hands its failures to its parent on the way out; only the
    outermost scope raises, which is what lets nesting group without truncating.

    A scope object is **not reentrant** and belongs to the **context that opened
    it**; it *is* reusable once closed. Those three sentences are one rule --
    exactly one ``__enter__`` is live at a time, in one context -- and it is
    enforced rather than documented, because the failure mode of breaking it is
    the worst this library has: a collector left active swallows every later
    failure in that thread silently. Anything :meth:`__exit__` cannot restore
    exactly, it switches off instead (see :meth:`_leave`), and reports as a
    ``RuntimeError`` naming the misuse -- a caller bug, not a finding about a
    value, so it is raised rather than collected.
    """

    __slots__ = (
        "_collector",
        "_formatters",
        "_formatters_token",
        "_name",
        "_parent",
        "_token",
    )

    def __init__(
        self,
        name: str | None = None,
        /,
        *,
        formatters: "tuple[ValueFormatter, ...]" = (),
    ) -> None:
        self._name: str | None = name
        self._collector = _Collector(name or "")
        self._parent: _Collector | None = None
        self._token: Token[_Collector | None] | None = None
        self._formatters: tuple[ValueFormatter, ...] = formatters
        self._formatters_token: FormatterToken | None = None

    @override
    def __repr__(self) -> str:
        return f"SoftScope({self._name!r}, failures={len(self._collector.failures)})"

    @property
    def name(self) -> str | None:
        """This scope's own name, or ``None`` for an anonymous scope."""
        return self._name

    @property
    def path(self) -> str:
        """``/``-joined names of this scope and its ancestors, anonymous ones dropped."""
        return self._collector.path

    def discard(self) -> list[str]:
        """Take the collected messages **without raising**, emptying the scope.

        Returns the rendered failure sentences in the order they were collected,
        and leaves the scope open and collecting. A block that discards
        everything it collected leaves quietly: there is nothing left to report
        on the way out.
        """
        collected = self._collector.failures[:]
        self._collector.failures.clear()
        return collected

    def __enter__(self) -> Self:
        """Open the block: route failures here, and start it empty.

        The steps are ordered by what has to be undone. Pushing formatters can
        refuse a bad one, and a ``__enter__`` that raises is never paired with an
        ``__exit__`` -- so it goes *before* the routing switch, and a refusal
        leaves nothing behind to leak.
        """
        if self._token is not None:
            raise RuntimeError(_ALREADY_OPEN)
        # Re-opened, so it is a live sink again: a scope object is reusable once
        # it has closed, and `closed` is the flag that says which it is.
        self._collector.closed = False
        if self._formatters:
            self._formatters_token = push_formatters(self._formatters)
        parent = _ACTIVE_COLLECTOR.get()
        self._parent = parent
        parent_path = parent.path if parent is not None else ""
        if parent_path and self._name:
            self._collector.path = parent_path + "/" + self._name
        else:
            self._collector.path = self._name or parent_path
        # A block starts empty. Failures a raising body held back stay readable
        # through `discard()` until the scope is opened again; carrying them into
        # the next block would report them under the wrong one. Tested rather
        # than cleared outright: a scope opens with nothing in it almost always,
        # and a truth test is a fraction of the call it skips.
        failures = self._collector.failures
        if failures:
            failures.clear()
        self._token = _ACTIVE_COLLECTOR.set(self._collector)
        return self

    def _leave(self, token: "Token[_Collector | None] | None", /) -> str:
        """Put failure routing back the way this scope found it.

        Returns the misuse it had to repair, or ``""`` when the scope closed the
        way it opened. It never raises: a scope that cannot restore the routing
        exactly still has to leave it somewhere safe, and *whether* to report the
        misuse is :meth:`__exit__`'s call, since an exception may already be in
        flight.

        The safe direction is **no collector**. An active collector that outlives
        its scope swallows every later failure in silence; no collector at all
        merely makes them raise, which is loud and right. So a token that no
        longer matches what the routing holds is not trusted to restore a
        collector that may itself have ended -- reaching for it is what turns one
        mistake into a process-wide one.
        """
        if token is None:
            return _NOT_OPEN
        # Asked before the reset, which consumes the token, and *not* used to
        # choose between two resets: a task created inside an open scope inherits
        # a copy of the context, so the collector can be this scope's own here
        # while the token still belongs to the context that made it. Only `reset`
        # itself can tell those apart, so every path goes through the one call.
        was_routed_here = _ACTIVE_COLLECTOR.get() is self._collector
        try:
            _ACTIVE_COLLECTOR.reset(token)
        except ValueError:
            # Made in another thread or task. That context is not this one and is
            # not ours to repair -- switching the routing off here would kill a
            # scope this one never opened.
            return _FOREIGN_CONTEXT
        if was_routed_here:
            return ""
        # Same context, wrong order: a scope opened after this one is still open,
        # so what the token just restored is a collector that has already ended.
        _ACTIVE_COLLECTOR.set(None)
        return _OUT_OF_ORDER

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
        /,
    ) -> None:
        token = self._token
        # Cleared first, and unconditionally: whatever happens below, this scope
        # is closed, and a spent token must never be reset a second time.
        self._token = None
        parent = self._parent
        self._parent = None
        formatters_token = self._formatters_token
        self._formatters_token = None
        # Routing before rendering: it is the one piece of state whose loss is
        # silent, so it is restored before anything that could raise.
        misuse = self._leave(token)
        if formatters_token is not None and misuse is not _FOREIGN_CONTEXT:
            # A foreign token would only raise the same ValueError `_leave` just
            # refused to let through; that context keeps its own formatters.
            pop_formatters(formatters_token)
        if exc is not None:
            # A real error is the more urgent signal. Do not bury it under an
            # aggregate of assertion failures collected before it happened -- nor
            # under a report about the scope itself, now that the routing, which
            # is the part that had to be repaired, is repaired.
            #
            # Not buried, and not thrown away either. Whatever failed before the
            # error was still a finding, and dropping it in silence is how a block
            # that found four problems reports one unrelated exception and none of
            # them. PEP 678 notes are exactly this: attached to the exception the
            # reader is already being shown, under it, changing nothing about
            # which exception propagates. pytest renders them.
            # Read, not taken: `discard()` empties the scope, and a body that
            # raises *keeps* its failures -- they stay readable through
            # `discard()` for a caller holding the scope. The note is for the
            # caller who is not, which is nearly all of them.
            _note_collected(exc, self._collector.failures)
            self._collector.closed = True
            return
        if exc_type is not None:  # pragma: no cover - an exception with no value
            return
        self._collector.closed = True
        if misuse:
            raise RuntimeError(misuse)
        collected = self.discard()
        if not collected:
            return
        if parent is not None:
            parent.failures.extend(collected)
            return
        raise AssertionFailure(_render_aggregate(collected))


def _note_collected(error: BaseException, collected: "Sequence[str]", /) -> None:
    """Attach a scope's collected failures to the error that cut it short.

    Called only when something is already propagating out of the block, so it
    must not raise and must not change what propagates. ``add_note`` does
    neither: it appends to a list the traceback machinery prints under the
    exception, and every renderer that matters -- CPython's own and pytest's --
    shows it.
    """
    if not collected:
        return
    error.add_note(
        _NOTED_HEADING
        if len(collected) == 1
        else str(len(collected)) + " assertions had already failed in this scope:"
    )
    for position, failure in enumerate(collected, 1):
        # The head already ends in its full stop; a failure with a detail block
        # keeps it on the first line, which is where the sentence ends.
        head, newline, block = failure.partition("\n")
        error.add_note("  (" + str(position) + ") " + head)
        if newline:
            for line in block.splitlines():
                error.add_note("      " + line)


#: The singular form, because "1 assertions" reads as a message nobody looked at
#: -- the same rule :func:`~lovely_assertions._text.count_of` exists for.
_NOTED_HEADING = "1 assertion had already failed in this scope:"


def soft_assertions(
    name: str | None = None, /, *, formatters: "tuple[ValueFormatter, ...]" = ()
) -> SoftScope:
    """Open a soft-assertion scope; failures inside it aggregate instead of raising.

    On exit the scope raises a single :class:`AssertionFailure` listing every
    failure it collected. A non-assertion exception raised inside the block
    propagates untouched, carrying whatever had already failed as notes attached
    to it, and :meth:`SoftScope.discard` takes the collected messages without
    raising at all.

    ``name`` prefixes the subject name in every failure the block collects, and
    nested scopes compose their names with ``/``. A nested scope hands its
    failures up to the scope containing it, so only the outermost one raises.

    ``formatters`` scopes value formatters to the block, overriding the globally
    registered ones for as long as it runs. It is the only sanctioned way to
    change rendering per test: global registration is write-once at import,
    because assertion state that a test can mutate stops being safe the moment
    the runner goes parallel.

    A block reports everything that was wrong with the payload, not the first
    thing::

        >>> with soft_assertions("payload") as scope:
        ...     _ = expect(1).is_equal_to(2)
        ...     _ = expect(3).is_greater_than(4)
        ...     collected = scope.discard()
        >>> len(collected)
        2
    """
    return SoftScope(name, formatters=formatters)


def _report(
    expectation: str,
    because: str,
    cause: BaseException | None = None,
    name: str | None = None,
) -> None:
    """Render and route a failure. Failure path only."""
    message = _render_failure(expectation, because, name)
    collector = _ACTIVE_COLLECTOR.get()
    if collector is None or collector.closed:
        # A closed collector is reachable only from a context that copied it and
        # outlived the block -- see `_Collector.closed`. Raising is the loud,
        # correct answer: the failure is real, and there is no report left to
        # join. One attribute read, on the failure path.
        raise AssertionFailure(message) from cause
    collector.failures.append(message)
