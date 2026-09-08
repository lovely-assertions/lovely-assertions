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
-- and answers them in two shapes, neither of which says what the reader needs.

Two of the three come back as the same sentence about the count, mentioning no
arguments at all::

    Expected 'mock' to be called once. Called 3 times.
    Calls: [call('/users'), call('/other'), call('/users')].

Which of those three calls matched? It does not say, and that is the difference
between "called the right thing twice too often" and "called three wrong things".

The third comes back in a different shape, and only when there was exactly one
call::

    expected call not found.
    Expected: mock('/a')
      Actual: mock('/b')

Two call lines, and the differing argument is left for the reader to spot. There
is no count here and no listing, so the two shapes never appear together: a wrong
argument on a mock called twice is reported purely as a count.

Here each of the three is its own message, argument differences go through the
same difference engine every other assertion uses, and the message names the
calls that *did* match -- the fact a reader otherwise has to work out by eye.

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

**A mock that records awaits gets a subject of its own.** Calling an
``AsyncMock`` and never awaiting the coroutine it returns satisfies every
assertion on the call side -- here and in ``unittest.mock`` both -- and says
nothing about whether the work ran. :mod:`lovely_assertions._mock._awaiting` asks
the same questions of ``await_args_list``, and
:class:`~lovely_assertions.AsyncMockExpect` is where the two catalogues meet. A
synchronous mock is never handed that subject: it keeps no such list, and a mock
answers every attribute, so an await assertion pointed at one would compare
against a child mock and pass.

One file per question: what makes something a mock, how a call is rendered,
whether one matches, why one did not, how often it was called, what it was called
with, whether it was awaited -- and the subjects those serve.
"""

from typing import TYPE_CHECKING, Any

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._mock._recognition import is_async_mock, is_mock

if TYPE_CHECKING:
    # The redundant-looking ``as`` is what marks this a re-export, so a checker
    # reads the real signature here rather than taking ``Any`` from the
    # ``__getattr__`` below.
    from lovely_assertions._mock._subject import AsyncMockExpect as AsyncMockExpect
    from lovely_assertions._mock._subject import MockExpect as MockExpect

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = ["AsyncMockExpect", "MockExpect", "is_async_mock", "is_mock"]


def __getattr__(name: str) -> Any:  # noqa: ANN401  (two names, and both are classes)
    """Bind a mock subject on first use, and not before.

    The dispatcher reaches :mod:`lovely_assertions._mock._recognition` through
    this package to decide whether a value *is* a mock, and that question is
    asked of every value handed to ``expect()``. Importing a subject here would
    therefore load the whole family -- both subjects, the counting, the argument
    matching, the awaiting and the rendering -- to compare two integers.
    Deferring it is what keeps recognising a mock cheaper than being one.

    Both names resolve out of the same module, so a session that asserts on one
    kind of mock pays for the other's class object and nothing more: the seams
    are shared, and the async subject is its base list.
    """
    if name not in {"AsyncMockExpect", "MockExpect"}:
        message = "module " + __name__ + " has no attribute " + repr(name)
        raise AttributeError(message)
    from lovely_assertions._mock import _subject  # noqa: PLC0415  (the point)

    value = getattr(_subject, name)
    globals()[name] = value
    return value
