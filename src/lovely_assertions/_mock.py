"""Assertions for ``unittest.mock`` mocks.

A mock answers every attribute. That is what a mock is *for*, and it is also why
an assertion made against one can be silently absent::

    fetch.was_called_once_with("/users")   # passes. asserts nothing.

The misspelling returns a child mock, calling it returns another one, and the
test goes green. ``unittest.mock`` knows this: ``NonCallableMock.__getattr__``
refuses any name beginning ``assert``, ``assret``, ``asert``, ``aseert`` or
``assrt``, plus a denylist of the assertion names with ``assert_`` stripped off.
The plain ``assert_called_once_wth`` is caught on a current interpreter.

A denylist catches the mistakes somebody thought of, and the shape of it says
how real the problem is. It does not catch a name borrowed from another
framework -- ``was_called_once_with``, ``verify_called_with``,
``toHaveBeenCalledWith`` all still return a child mock and pass -- and
``Mock(unsafe=True)`` turns the whole guard off. Nor can any denylist catch the
version of this that is not a typo at all: ``api.assert_not_called()`` passes
after ``api.get("/a")``, because the call went to the child and the parent was
never called.

``expect()`` needs no denylist. ``expect(fetch).was_called_once_wth("/users")``
is an ``AttributeError`` on a ``__slots__`` subject with a fixed catalogue, in
the test that wrote it, on the line that wrote it -- for every misspelling,
including the ones nobody has thought of yet. That is the first half of what this
module is for.

The second half is the messages. ``assert_called_once_with`` fails three
different ways -- never called, called with something else, called more than once
-- and reports all three as one sentence about the call count::

    Expected 'mock' to be called once. Called 3 times.
    Calls: [call('/users'), call('/other'), call('/users')].

Which of those calls matched? Which argument was wrong? mock does not say. Here
each of the three is its own message, argument differences go through the same
difference engine every other assertion uses, and the message names the calls
that *did* match -- the fact a reader otherwise has to work out by eye.

**Nothing here imports ``unittest.mock``**, at module level or inside a function.
It is not needed: recognising a mock is a question about a class (see
:func:`is_mock`), and asserting on one reads a single ordinary attribute,
``call_args_list``. A test session that never mentions a mock must not pay for
the import, and this way it cannot.

Four decisions worth knowing about.

**A call is compared as it was recorded.** ``assert_called_with`` on an
autospec'd mock normalises the call through the spec's signature first, so a
recorded ``fetch(1)`` matches an expected ``fetch(x=1)``. This does not: it
compares the positional arguments against the positional arguments and the
keyword arguments against the keyword arguments, and reports what it finds. That
is a deliberate divergence, for two reasons -- the normalisation reads a private
attribute of ``unittest.mock``, and a message that describes a call one way while
having matched it another is worse than one that shows what actually happened.
When it bites, the message says so precisely: ``keyword arguments: extra keys:
['x']``.

**``because`` collides with a keyword argument named ``because``.** The
argument-taking assertions are ``(*args, because="", **kwargs)``, so a call the
subject really made with ``because=`` cannot be spelled that way. ``because`` is
keyword-only on every assertion in the library and that wins; the escape hatch is
:attr:`MockExpect.calls`, which asserts on the recorded calls directly::

    expect(fetch).calls.contains(call("/users", because="audit"))

**Calls are counted with ``len(call_args_list)``, never ``call_count``.** The two
always agree in ``unittest.mock``, and reading one of them means the number in a
message and the listing under it cannot ever disagree.

**Only the mock's own calls are its calls.** ``call_args_list`` records calls to
this mock; calls to its children (``api.get(...)`` from ``expect(api)``) live in
``mock_calls`` and are a different question. ``expect(api.get)`` asks this one
about the child, and ``expect(api.mock_calls)`` -- an ordinary list -- asks the
sequence subject about the whole recording.

Two conventions, as everywhere else in the library. Rendering helpers use
concatenation, never f-strings: a message is only ever built inside a ``_fail``
call, so a passing assertion formats nothing. And every bound a message renders
within comes from :func:`~lovely_assertions._formatting.current_formatting`, read
in the failure branch and nowhere else -- reading it earlier would put a
``ContextVar`` lookup on the path of every assertion that passes.
"""

from types import FunctionType
from typing import TYPE_CHECKING, Any, Self, cast

from lovely_assertions._core import Expect, Found
from lovely_assertions._diff import describe_difference
from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters import format_value
from lovely_assertions._formatting import current_formatting
from lovely_assertions._sequence import SequenceExpect
from lovely_assertions._text import clipped, count_of

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from lovely_assertions._formatting import FormattingOptions
    from lovely_assertions._occurrence import Occurrence

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = ["MockExpect", "is_mock"]

#: One level of a message's detail block, matching ``_diff.py``.
_INDENT = "  "

#: The names every ``unittest.mock`` mock carries, in the order they are asked
#: for. See :func:`is_mock` for where they are looked for and why there are five
#: of them rather than one.
#:
#: No leading underscore, for the reason ``_core.collect_failures`` has none: it
#: is read from outside this module, and an ordinary read beats a suppression.
#: This tuple is the canonical list; the unrolled chain in
#: :func:`answers_the_protocol` has to be kept in step with it. The module is
#: private, so nothing reaches the public surface either way, and it stays out of
#: ``__all__`` because it is not something the package re-exports.
MOCK_MARKERS = (
    "assert_called_with",
    "assert_any_call",
    "call_args_list",
    "mock_calls",
    "reset_mock",
)


#: The marker `_subjects._dispatch` tests before paying for the whole protocol.
#:
#: Read from the tuple rather than written out again, so there is still one list
#: of markers. Reading a module-level name is no more expensive than repeating
#: the literal, so keeping one list costs the dispatch path nothing.
FIRST_MOCK_MARKER = MOCK_MARKERS[0]


def answers_the_protocol(candidate: object, /) -> bool:
    """Whether ``candidate`` carries every name in :data:`MOCK_MARKERS`.

    Written out as a chain rather than as a loop over the tuple because this sits
    in ``expect()``'s dispatch: a generator expression would build a frame per
    call to ask a question ``and`` short-circuits for free. :data:`MOCK_MARKERS`
    stays the canonical list and the chain has to be kept in step with it -- an
    impostor missing any single one of those names has to be declined.
    """
    return (
        hasattr(candidate, "assert_called_with")
        and hasattr(candidate, "assert_any_call")
        and hasattr(candidate, "call_args_list")
        and hasattr(candidate, "mock_calls")
        and hasattr(candidate, "reset_mock")
    )


def is_mock(value: object, /) -> bool:
    """Whether ``value`` behaves like a ``unittest.mock`` mock. The dispatch predicate.

    **Asked of the class, not of the instance.** ``hasattr(mock, "wibble")`` is
    ``True`` -- that is the whole nature of a mock, and it makes an instance-level
    check useless. A mock's *class* is an ordinary class: ``NonCallableMock``
    builds a fresh subclass per instance so that magic methods set on one mock do
    not land on another, and attribute lookup on a class does not run the
    instance ``__getattr__`` that answers everything. So
    ``hasattr(type(mock), "assert_called_with")`` is ``True`` and
    ``hasattr(type(mock), "assert_called_once_wth")`` is ``False``, which is
    exactly the distinction that has to be drawn. It is also what keeps a
    ``call`` object out: ``call.anything`` builds a child call, so the instance
    answers every name and the class answers none of them.

    **Five names, not one.** ``assert_called_with`` alone would claim a
    hand-written spy that happens to offer one familiar method; the assertions
    here then read ``call_args_list`` off it and fail in a way that explains
    nothing. Something carrying all five is a mock in every sense this module
    needs, whichever package built it -- ``unittest.mock``, the ``mock`` backport
    on PyPI, or a project's own.

    **Duck-typed rather than ``isinstance``**, deliberately. The alternative,
    ``sys.modules.get("unittest.mock")`` followed by an ``isinstance`` -- the
    shape ``_subjects._lazy_module_subject`` uses for ``Decimal`` -- is exact for
    the standard library and blind to every mock built by anything else. It also
    claims things that are *in* ``unittest.mock`` and are not mocks: a ``call``
    object and a ``sentinel`` both live there.

    **One instance-level exception, and it is a narrow one.**
    ``create_autospec(some_function)`` does not return a mock at all: it returns
    a real function, built to carry the original's signature, with the whole mock
    protocol hung off it as *instance* attributes and a ``MagicMock`` behind
    them. Its class is ``function``, which declares none of the five. Autospec is
    the form the ``unittest.mock`` documentation recommends, so declining it
    would decline the recommended way to write the test -- and asking a function
    object about its attributes is safe in a way that asking an arbitrary object
    is not, because a function cannot define ``__getattr__`` and so cannot answer
    a name it does not have.

    Free on the path that matters. A non-mock fails on the first name, and
    ``hasattr`` for a missing attribute allocates nothing.
    """
    kind = type(value)
    if answers_the_protocol(kind):
        return True
    return kind is FunctionType and answers_the_protocol(value)


class MockExpect(Expect[Any]):
    """Assertions about how a mock was called.

    The subject is a mock, and its type is ``Any``: a mock stands in for
    something, and pinning it to a class would be a claim about the thing it
    stands in for rather than about the mock. Everything on
    :class:`~lovely_assertions.Expect` still applies, so ``.subject`` hands the
    mock back and ``satisfies`` runs an inspection over it.

    The catalogue is deliberately the ``unittest.mock`` one, renamed to read as an
    expectation rather than as a command::

        assert_called()            -> was_called()
        assert_not_called()        -> was_not_called()
        assert_called_once()       -> was_called_once()
        assert_called_with(...)    -> was_called_with(...)
        assert_called_once_with()  -> was_called_once_with(...)
        assert_any_call(...)       -> was_ever_called_with(...)
        (nothing)                  -> was_never_called_with(...)
        call_count == n            -> has_call_count(n)
        assert_has_calls([...])    -> calls.contains_in_order(...)

    Two of those rows are worth a second look. ``was_never_called_with`` has no
    counterpart in ``unittest.mock`` at all, and it is the assertion a test
    actually wants when it is guarding against a call that must not happen.
    ``assert_has_calls`` is not reimplemented because :attr:`calls` already hands
    the whole ordered catalogue of
    :class:`~lovely_assertions.SequenceExpect` to the recorded calls, with
    messages that name the position where the expected order broke.
    """

    __slots__ = ()

    # -- how often -----------------------------------------------------------
    def was_called(self, *, because: str = "") -> Self:
        """Assert the mock was called at least once."""
        if self._subject.call_args_list:
            return self
        return self._fail(f"to have been called, but {self._how_it_was_called()}", because)

    def was_not_called(self, *, because: str = "") -> Self:
        """Assert the mock was never called.

        The failure lists the calls, which is the half ``assert_not_called``
        leaves out: knowing that something was called three times is no use
        without knowing what it was called with.
        """
        if not self._subject.call_args_list:
            return self
        return self._fail(f"not to have been called, but {self._how_it_was_called()}", because)

    def was_called_once(self, *, because: str = "") -> Self:
        """Assert the mock was called exactly once, whatever the arguments."""
        if len(self._subject.call_args_list) == 1:
            return self
        return self._fail(f"to have been called once, but {self._how_it_was_called()}", because)

    def has_call_count(self, expected: "int | Occurrence", /, *, because: str = "") -> Self:
        """Assert how many times the mock was called.

        Takes a plain count or an occurrence constraint, so both of these read as
        what they mean::

            expect(fetch).has_call_count(3)
            expect(fetch).has_call_count(at_least(2))

        ``has_call_count(3)`` and ``has_call_count(exactly(3))`` are the same
        assertion and produce the same message; the constraint is what buys
        "at least", "at most" and the rest without a method each.

        The count is the mock's *own* calls. Calls that went to its children are
        recorded on the parent's ``mock_calls`` and are not counted here.
        """
        count = len(self._subject.call_args_list)
        if isinstance(expected, int):
            if count == expected:
                return self
            return self._fail(
                f"to have been called exactly {count_of(expected, 'time')},"
                f" but {self._how_it_was_called()}",
                because,
            )
        if expected.allows(count):
            return self
        return self._fail(
            f"to have been called {expected.describe()}, but {self._how_it_was_called()}",
            because,
        )

    # -- with what -----------------------------------------------------------
    def was_called_with(self, *args: object, because: str = "", **kwargs: object) -> Self:
        """Assert the **most recent** call was made with these arguments.

        The same rule ``assert_called_with`` follows, and the same trap: earlier
        calls are not looked at. That trap is why the failure says so. When an
        earlier call *did* match, the message names it -- otherwise the reader is
        left staring at two identical-looking argument lists wondering why the
        assertion failed.

        ``because`` is keyword-only, and therefore shadows a keyword argument of
        the same name that the subject itself may have been called with; see the
        module docstring for the escape hatch. Reach for
        :meth:`was_ever_called_with` when the call under test need not be the last
        one.
        """
        recorded: Sequence[Any] = self._subject.call_args_list
        if recorded and _matches(recorded[-1], args, kwargs):
            return self
        if not recorded:
            return self._fail(
                f"to have been called with {_wanted(args, kwargs)},"
                f" but {self._how_it_was_called()}",
                because,
            )
        return self._fail(
            f"to have been called with {_wanted(args, kwargs)},"
            f" but was {_last_clause(len(recorded))} {_render_call(recorded[-1], _options())}"
            + _describe_call_difference(recorded[-1], args, kwargs)
            + _earlier_matches_note(recorded, args, kwargs),
            because,
        )

    def was_called_once_with(self, *args: object, because: str = "", **kwargs: object) -> Self:
        """Assert the mock was called exactly once, and with these arguments.

        Three different bugs fail this assertion, and each gets its own message:
        it was never called, it was called once with something else, or it was
        called more than once. ``assert_called_once_with`` reports all three as
        the same sentence about the count, which is the single worst message in
        the module it comes from.
        """
        recorded: Sequence[Any] = self._subject.call_args_list
        if len(recorded) == 1 and _matches(recorded[0], args, kwargs):
            return self
        if not recorded:
            return self._fail(
                f"to have been called once with {_wanted(args, kwargs)},"
                f" but {self._how_it_was_called()}",
                because,
            )
        if len(recorded) == 1:
            return self._fail(
                f"to have been called once with {_wanted(args, kwargs)},"
                f" but was called with {_render_call(recorded[0], _options())}"
                + _describe_call_difference(recorded[0], args, kwargs),
                because,
            )
        return self._fail(
            f"to have been called once with {_wanted(args, kwargs)},"
            f" but {self._how_it_was_called()}" + _which_matched(recorded, args, kwargs),
            because,
        )

    def was_ever_called_with(self, *args: object, because: str = "", **kwargs: object) -> Self:
        """Assert some call -- any of them -- was made with these arguments.

        ``assert_any_call``, and the assertion to reach for when the call under
        test is one of several and its position is not the point. The failure
        shows the calls that were made and picks the nearest of them to explain,
        because "none of these four matched" is a fact the reader already had.
        """
        recorded: Sequence[Any] = self._subject.call_args_list
        for one in recorded:
            if _matches(one, args, kwargs):
                return self
        if not recorded:
            return self._fail(
                f"to have been called with {_wanted(args, kwargs)} at some point,"
                f" but {self._how_it_was_called()}",
                because,
            )
        if len(recorded) == 1:
            return self._fail(
                f"to have been called with {_wanted(args, kwargs)} at some point,"
                f" but its only call was {_render_call(recorded[0], _options())}"
                + _describe_call_difference(recorded[0], args, kwargs),
                because,
            )
        return self._fail(
            f"to have been called with {_wanted(args, kwargs)} at some point,"
            f" but none of its {count_of(len(recorded), 'call')} was:"
            f" {_render_calls(recorded, _options())}" + _nearest_note(recorded, args, kwargs),
            because,
        )

    def was_never_called_with(self, *args: object, because: str = "", **kwargs: object) -> Self:
        """Assert no call was made with these arguments.

        ``unittest.mock`` has nothing for this, which is why a test that means
        "the cache must not be refetched" usually ends up asserting a call count
        instead -- and passes for the wrong reason the day an unrelated call is
        added. The failure names the calls that were made with those arguments.
        """
        recorded: Sequence[Any] = self._subject.call_args_list
        for one in recorded:
            if _matches(one, args, kwargs):
                break
        else:
            return self
        # Past the branch, so the list the message needs is built where it is
        # read. Building it first and testing it for emptiness instead would put
        # a comprehension and a list allocation on the branch that *passes*.
        matched = [index for index, one in enumerate(recorded, 1) if _matches(one, args, kwargs)]
        options = _options()
        return self._fail(
            f"never to have been called with {_wanted(args, kwargs)},"
            f" but {_call_numbers(matched, options)}"
            f" {'was' if len(matched) == 1 else 'were'}:"
            f" {_render_calls(recorded, options)}",
            because,
        )

    # -- continuations -------------------------------------------------------
    @property
    def calls(self) -> "SequenceExpect[Any]":
        """The recorded calls, as a sequence subject.

            expect(fetch).calls.has_length(2)
            expect(fetch).calls.contains_in_order(call("/a"), call("/b"))

        A property rather than a method because it makes no claim and cannot
        fail: a mock that was never called has an empty list of calls, which is
        an answer rather than a failure. :meth:`last_call` is a method for the
        opposite reason.

        The elements are ``unittest.mock`` ``call`` objects, kept as they were
        recorded rather than converted into something friendlier. Three reasons.
        ``call(...)`` is the vocabulary every mock user already writes, and it
        compares the way they expect -- ``call(1) == ((1,), {})``. Its ``repr``
        is the call that produced it, so a failure message can be pasted back
        into a test. And handing back the mock's own list is what makes
        ``contains_in_order`` a better ``assert_has_calls`` rather than a second,
        subtly different one.

        A name given with ``described_as`` or ``expect(..., name=...)`` carries
        over, exactly as it does through ``extracting``.
        """
        recorded: Sequence[Any] = self._subject.call_args_list
        derived: SequenceExpect[Any] = SequenceExpect(recorded)
        return self._carrying_name(derived)

    def last_call(self, *, because: str = "") -> "Found[Self, Any]":
        """Assert the mock was called, and continue on its most recent call.

            expect(fetch).last_call().which.subject.args

        A method rather than a property, unlike :attr:`calls`: this one asserts
        something -- that there *is* a last call -- and every assertion in the
        library takes a ``because``, which a property cannot.

        ``.which`` descends into the call itself, ``.and_`` goes back to the mock.
        The found value is the recorded ``call`` object, so ``.which.subject.args``
        and ``.which.subject.kwargs`` are its two halves.
        """
        recorded: Sequence[Any] = self._subject.call_args_list
        if recorded:
            found: Any = recorded[-1]
            return Found(self, found)
        return cast(
            "Found[Self, Any]",
            self._fail_narrowing(f"to have been called, but {self._how_it_was_called()}", because),
        )

    # -- internals -----------------------------------------------------------
    def _carrying_name[D: "Expect[Any]"](self, derived: D, /) -> D:
        """Hand an explicit subject name on to a subject derived from this one.

        The same five lines as
        :meth:`~lovely_assertions._collection.CollectionExpect._carrying_name`
        and for the same reason: a derived wrapper is a new object with no name,
        and an explicit name has to survive at least as well as a recovered one
        or naming the subject stops being worth doing. It is duplicated rather
        than shared because the shared home would be ``Expect`` itself, and that
        is a change to a module this one does not own.
        """
        name = getattr(self, "_name", None)
        return derived if name is None else derived.described_as(name)

    def _how_it_was_called(self) -> str:
        """The ``but ...`` half of a message about the call count. Failure path only.

        One helper for every count-shaped failure, so ``was_not_called``,
        ``was_called_once`` and ``has_call_count`` cannot drift into three
        different accounts of the same fact. No f-string: the message is built
        inside the ``_fail`` call, so a passing assertion formats nothing.
        """
        recorded: Sequence[Any] = self._subject.call_args_list
        if not recorded:
            return "it was never called"
        options = _options()
        return (
            "it was called "
            + count_of(len(recorded), "time")
            + ": "
            + _render_calls(recorded, options)
        )


# ---------------------------------------------------------------------------
# Matching -- these run on the happy path, so they allocate nothing beyond what
# the question itself requires.
# ---------------------------------------------------------------------------
def _matches(
    recorded: "Sequence[Any]", args: "tuple[object, ...]", kwargs: "Mapping[str, object]", /
) -> bool:
    """Whether one recorded call was made with exactly these arguments.

    A recorded call is a ``(args, kwargs)`` pair, or a ``(name, args, kwargs)``
    triple when it came from ``mock_calls``; the last two entries are the
    arguments either way, so it is indexed from the end. Indexed rather than read
    through the ``.args``/``.kwargs`` properties so that a call recorded as a
    plain tuple -- by a mock this module did not build -- compares the same way,
    and so that nothing is allocated to ask the question.

    No signature normalisation: see the module docstring.

    The result is coerced, as ``_diff._equal`` coerces its own: the subject is a
    mock and both operands come back as ``Any``, so without it the declared
    ``bool`` would be a promise nothing checked. The ``and`` still short-circuits.
    """
    return bool(recorded[-2] == args and recorded[-1] == kwargs)


# ---------------------------------------------------------------------------
# Rendering helpers -- failure path only.
#
# None of them may use an f-string: an f-string is a message, and a message is
# only ever built inside the `_fail` call itself, so that a passing assertion
# formats nothing. They concatenate and join instead.
# ---------------------------------------------------------------------------
def _options() -> "FormattingOptions":
    """The bounds in force. **Failure path only** -- it reads a ``ContextVar``."""
    return current_formatting()


def _render_call(recorded: "Sequence[Any]", options: "FormattingOptions", /) -> str:
    """One call's arguments, in the shape they were written at the call site.

    ``('/users', timeout=3)`` -- the parentheses of a call, not of a tuple, which
    is why a single positional argument does not get a trailing comma. Values go
    through ``format_value`` rather than through the call object's own ``repr``,
    so a registered formatter is consulted for an argument the way it is for
    every other value in a message.
    """
    return _render_arguments(recorded[-2], recorded[-1], options)


def _render_arguments(
    args: "Sequence[Any]", kwargs: "Mapping[str, Any]", options: "FormattingOptions", /
) -> str:
    """:func:`_render_call` for a pair that is not a recorded call object."""
    limit = options.max_items
    shown: list[str] = []
    for value in args:
        if len(shown) == limit:
            break
        shown.append(clipped(format_value(value), options.max_chars))
    for name, value in kwargs.items():
        if len(shown) == limit:
            break
        shown.append(name + "=" + clipped(format_value(value), options.max_chars))
    elided = len(args) + len(kwargs) - len(shown)
    if elided > 0:
        shown.append("... (" + str(elided) + " more)")
    return "(" + ", ".join(shown) + ")"


def _wanted(args: "tuple[object, ...]", kwargs: "Mapping[str, object]", /) -> str:
    """The arguments an assertion asked for, as they read after "called with".

    ``()`` is correct and reads as nothing at all in the middle of a sentence, so
    the empty call gets words instead: "called with no arguments" is a claim, and
    "called with ()" is a typo waiting to be reported as one.
    """
    if not args and not kwargs:
        return "no arguments"
    return _render_arguments(args, kwargs, _options())


def _render_calls(recorded: "Sequence[Any]", options: "FormattingOptions", /) -> str:
    """Every recorded call, truncated like every other collection in a message."""
    limit = options.max_items
    shown: list[str] = []
    for one in recorded:
        if len(shown) == limit:
            break
        shown.append(_render_call(one, options))
    elided = len(recorded) - len(shown)
    if elided > 0:
        return "[" + ", ".join(shown) + ", ... (" + str(elided) + " more)]"
    return "[" + ", ".join(shown) + "]"


def _last_clause(total: int, /) -> str:
    """``"called with"`` for a single call, ``"last called with"`` for several.

    "last called with" in front of the only call there is reads as though the
    assertion had ignored the others, which is the very confusion these messages
    exist to remove.
    """
    if total == 1:
        return "called with"
    return "last called with"


def _describe_call_difference(
    recorded: "Sequence[Any]", args: "tuple[object, ...]", kwargs: "Mapping[str, object]", /
) -> str:
    """How a recorded call differs from the one that was expected.

    The whole point of routing this through
    :func:`~lovely_assertions._diff.describe_difference` rather than printing two
    argument lists: one wrong keyword out of six is reported as *that keyword*,
    the way a mapping comparison reports it, instead of leaving the reader to
    diff two lines by eye.

    Each half is asked only when it actually differs. ``describe_difference`` is
    written for two values that are already known to be unequal, and given two
    equal ones it would report -- correctly for its own contract, absurdly here --
    that they render alike and are not equal.
    """
    block = ""
    if recorded[-2] != args:
        positional = describe_difference(recorded[-2], args)
        if positional:
            block += "\n" + _INDENT + "positional arguments:" + _deepen(positional)
    if recorded[-1] != kwargs:
        keyword = describe_difference(recorded[-1], kwargs)
        if keyword:
            block += "\n" + _INDENT + "keyword arguments:" + _deepen(keyword)
    return block


def _deepen(block: str, /) -> str:
    """Indent a nested block one level under the line that introduces it."""
    return block.replace("\n", "\n" + _INDENT)


def _earlier_matches_note(
    recorded: "Sequence[Any]", args: "tuple[object, ...]", kwargs: "Mapping[str, object]", /
) -> str:
    """Name the earlier calls that matched, when ``was_called_with`` failed on the last.

    This is the line ``assert_called_with`` never prints and the reader always
    needs. "Expected: fetch('/users') / Actual: fetch('/other')" sends somebody
    hunting for a call that is right there in the recording -- it was simply not
    the last one, and that is a fact about the assertion rather than about the
    code under test.
    """
    matched = [index for index, one in enumerate(recorded[:-1], 1) if _matches(one, args, kwargs)]
    if not matched:
        return ""
    options = _options()
    return (
        "\n"
        + _INDENT
        + _call_numbers(matched, options)
        + (" was" if len(matched) == 1 else " were")
        + " made with those arguments; only the last call is checked"
    )


def _which_matched(
    recorded: "Sequence[Any]", args: "tuple[object, ...]", kwargs: "Mapping[str, object]", /
) -> str:
    """Which of several calls matched, for a failed ``was_called_once_with``.

    "Called 3 times" leaves two very different bugs looking identical: the code
    called the right thing three times when it should have called it once, or it
    called three different things and none of them was right. This line says
    which.
    """
    matched = [index for index, one in enumerate(recorded, 1) if _matches(one, args, kwargs)]
    options = _options()
    if not matched:
        return "\n" + _INDENT + "none of those calls was made with those arguments"
    return (
        "\n"
        + _INDENT
        + _call_numbers(matched, options)
        + (" was" if len(matched) == 1 else " were")
        + " made with those arguments; it is the call count that is wrong"
    )


def _nearest_note(
    recorded: "Sequence[Any]", args: "tuple[object, ...]", kwargs: "Mapping[str, object]", /
) -> str:
    """Explain the recorded call that came closest to the one that was expected.

    A heuristic, and only ever a choice of *which* call to explain -- it decides
    nothing about whether the assertion passed. The distance is the number of
    argument slots that disagree: positions that hold different values, positions
    one side does not have at all, keywords only one side passed, and keywords
    both passed with different values. The first call with the lowest score wins,
    so a tie keeps the order the calls were made in.
    """
    nearest = 0
    best = -1
    for index, one in enumerate(recorded):
        score = _distance(one, args, kwargs)
        if best < 0 or score < best:
            nearest, best = index, score
    difference = _describe_call_difference(recorded[nearest], args, kwargs)
    if not difference:
        return ""
    return "\n" + _INDENT + "the closest was call " + str(nearest + 1) + ":" + _deepen(difference)


def _distance(
    recorded: "Sequence[Any]", args: "tuple[object, ...]", kwargs: "Mapping[str, object]", /
) -> int:
    """How many argument slots one recorded call disagrees with the expected one in."""
    recorded_args: Sequence[Any] = recorded[-2]
    recorded_kwargs: Mapping[str, Any] = recorded[-1]
    score = abs(len(recorded_args) - len(args))
    score += sum(1 for left, right in zip(recorded_args, args, strict=False) if left != right)
    score += len(set(recorded_kwargs).symmetric_difference(kwargs))
    score += sum(
        1 for name, value in recorded_kwargs.items() if name in kwargs and value != kwargs[name]
    )
    return score


def _call_numbers(indices: list[int], options: "FormattingOptions", /) -> str:
    """``"call 2"`` or ``"calls 1 and 3"`` -- the calls a note is about.

    Numbered from one and in the order they were made, which is the order the
    listing beside them prints, so "call 2" can be counted off it. Truncated like
    every other listing: a mock called a thousand times must not put a thousand
    numbers in a message.
    """
    noun = "call " if len(indices) == 1 else "calls "
    limit = options.max_items
    shown = [str(index) for index in indices[:limit]]
    elided = len(indices) - len(shown)
    if elided > 0:
        return noun + ", ".join(shown) + ", ... (" + str(elided) + " more)"
    if len(shown) == 1:
        return noun + shown[0]
    return noun + ", ".join(shown[:-1]) + " and " + shown[-1]
