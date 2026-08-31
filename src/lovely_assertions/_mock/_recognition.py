"""What makes something a mock, without importing ``unittest.mock``.

A denylist of type names would miss every wrapper and every third-party double.
What is checked instead is the shape: the attributes a mock carries to record the
calls made against it. Anything that answers to those is one, whoever built it.

The one file of this package on the dispatch path, and the reason importing the
library never imports ``unittest.mock``: a session with no mocks in it should pay
nothing for the ones it does not have.
"""

from types import FunctionType

from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


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
