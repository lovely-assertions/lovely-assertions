"""Fluent, strictly-typed assertions for Python tests.

``lovely-assertions`` competes with pytest's ``assert`` rewriting on the two axes
where it has nothing to offer: **typed discoverability** -- ``expect(x).`` proposes
only the assertions that are valid for ``x`` -- and **real narrowing** --
``expect(raw).is_not_none().subject`` is a ``str`` as far as the type checker is
concerned.

::

    from lovely_assertions import expect

    expect(order.total).is_greater_than(0, because="an empty basket cannot ship")
    expect(response.headers).contains_key("etag")

:func:`expect` chooses the subject type from the value, so only the assertions
that make sense for it are offered; every assertion returns a subject, so they
chain; every failure is a sentence naming the bug rather than a diff to interpret.
``because=`` is appended to that sentence and is never interpolated into it.

Around that: :func:`soft_assertions` gathers several failures into one report
instead of stopping at the first, :func:`expect_raises` and :func:`expect_warns`
put an exception or a warning under the same fluent API, :func:`formatting` widens
how much a message may print for one block, and :func:`register_formatter` decides
how a domain type reads inside one. :func:`register` attaches a subject class to
a type of your own, and :func:`custom_assertion` marks an assertion you wrote so
its failures still name the caller's variable rather than a local of yours.

Zero runtime dependencies, Python 3.13+, ``py.typed``.
"""

#: The distribution's version, and the only place it is written down.
#:
#: A string literal rather than a call to ``importlib.metadata.version()``: that
#: reads the installed distribution's metadata off disk, which costs more than
#: everything else this package does at import time and would be paid by every
#: program that imports it to run one assertion. The build backend reads this very
#: line to version the wheel, so the string here and the distribution's recorded
#: version cannot disagree.
#:
#: The trailing marker is not decoration: release-please's generic updater rewrites
#: the line carrying it, which is how the version derived from the commit log lands
#: here rather than being typed by hand. Remove it and releases silently stop
#: bumping this file while still tagging.
#:
#: It reads ``0.0.0`` because nothing has been published to PyPI yet, and this
#: line records the last *released* version rather than the next one. The release
#: pull request is where the next one is proposed.
__version__ = "0.0.0"  # x-release-please-version

from lovely_assertions._core import Expect, Found, SoftScope, soft_assertions
from lovely_assertions._equivalence import Equivalency, close_within, equivalency
from lovely_assertions._exceptions import AssertionFailure
from lovely_assertions._formatters import (
    IterableFormatter,
    ObjectFormatter,
    ValueFormatter,
    format_value,
    register_formatter,
)
from lovely_assertions._formatting import FormattingOptions, current_formatting, formatting

# `_matching` wires itself up at import time: a subject that refuses
# `expect(<a matcher>)` and says where the matcher belongs instead, and a formatter
# that renders matchers inside a failure message. Neither happens unless something
# imports the module, so re-exporting the matchers here is what installs both for
# every user.
from lovely_assertions._matching import (
    any_instance_of,
    anything,
    close_to,
    containing,
    is_matcher,
    matching,
    one_of,
    string_containing,
    string_matching,
)
from lovely_assertions._names import custom_assertion
from lovely_assertions._occurrence import (
    Occurrence,
    at_least,
    at_most,
    exactly,
    less_than,
    more_than,
    once,
    twice,
)
from lovely_assertions._subjects import (
    BoolExpect,
    CallableExpect,
    CollectionExpect,
    DateExpect,
    DateTimeExpect,
    EnumExpect,
    MappingExpect,
    MockExpect,
    NumericExpect,
    OrderedExpect,
    PathExpect,
    PurePathExpect,
    RaisedExpect,
    SequenceExpect,
    StringExpect,
    TimeDeltaExpect,
    TimeExpect,
    TypeExpect,
    WithinDelta,
    expect,
    expect_raises,
    is_mock,
    register,
)
from lovely_assertions._warnings import WarnedExpect, expect_warns

__all__ = [
    "AssertionFailure",
    "BoolExpect",
    "CallableExpect",
    "CollectionExpect",
    "DateExpect",
    "DateTimeExpect",
    "EnumExpect",
    "Equivalency",
    "Expect",
    "FormattingOptions",
    "Found",
    "IterableFormatter",
    "MappingExpect",
    "MockExpect",
    "NumericExpect",
    "ObjectFormatter",
    "Occurrence",
    "OrderedExpect",
    "PathExpect",
    "PurePathExpect",
    "RaisedExpect",
    "SequenceExpect",
    "SoftScope",
    "StringExpect",
    "TimeDeltaExpect",
    "TimeExpect",
    "TypeExpect",
    "ValueFormatter",
    "WarnedExpect",
    "WithinDelta",
    "any_instance_of",
    "anything",
    "at_least",
    "at_most",
    "close_to",
    "close_within",
    "containing",
    "current_formatting",
    "custom_assertion",
    "equivalency",
    "exactly",
    "expect",
    "expect_raises",
    "expect_warns",
    "format_value",
    "formatting",
    "is_matcher",
    "is_mock",
    "less_than",
    "matching",
    "more_than",
    "once",
    "one_of",
    "register",
    "register_formatter",
    "soft_assertions",
    "string_containing",
    "string_matching",
    "twice",
]
