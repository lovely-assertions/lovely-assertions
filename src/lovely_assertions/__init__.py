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
__version__ = "0.1.0"  # x-release-please-version

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # To a checker the surface is exactly what it always was. The ``as`` is what
    # makes each of these a re-export rather than a private binding, and the
    # suppression is what stops `ruff --fix` from removing it -- without the alias
    # every name here answers `Any`.
    from lovely_assertions._bool import BoolExpect as BoolExpect
    from lovely_assertions._callable import CallableExpect as CallableExpect
    from lovely_assertions._callable import RaisedExpect as RaisedExpect
    from lovely_assertions._callable import expect_raises as expect_raises
    from lovely_assertions._collection import CollectionExpect as CollectionExpect
    from lovely_assertions._core import Expect as Expect
    from lovely_assertions._core import Found as Found
    from lovely_assertions._core import SoftScope as SoftScope
    from lovely_assertions._core import soft_assertions as soft_assertions
    from lovely_assertions._datetime import DateExpect as DateExpect
    from lovely_assertions._datetime import DateTimeExpect as DateTimeExpect
    from lovely_assertions._datetime import TimeDeltaExpect as TimeDeltaExpect
    from lovely_assertions._datetime import TimeExpect as TimeExpect
    from lovely_assertions._datetime import WithinDelta as WithinDelta
    from lovely_assertions._enum import EnumExpect as EnumExpect
    from lovely_assertions._equivalence import Equivalency as Equivalency
    from lovely_assertions._equivalence import close_within as close_within
    from lovely_assertions._equivalence import equivalency as equivalency
    from lovely_assertions._exceptions import AssertionFailure as AssertionFailure
    from lovely_assertions._formatters import (
        IterableFormatter as IterableFormatter,
    )
    from lovely_assertions._formatters import ObjectFormatter as ObjectFormatter
    from lovely_assertions._formatters import ValueFormatter as ValueFormatter
    from lovely_assertions._formatters import format_value as format_value
    from lovely_assertions._formatters import (
        register_formatter as register_formatter,
    )
    from lovely_assertions._formatting import (
        FormattingOptions as FormattingOptions,
    )
    from lovely_assertions._formatting import (
        current_formatting as current_formatting,
    )
    from lovely_assertions._formatting import formatting as formatting
    from lovely_assertions._mapping import MappingExpect as MappingExpect
    from lovely_assertions._matching import any_instance_of as any_instance_of
    from lovely_assertions._matching import anything as anything
    from lovely_assertions._matching import close_to as close_to
    from lovely_assertions._matching import containing as containing
    from lovely_assertions._matching import is_matcher as is_matcher
    from lovely_assertions._matching import matching as matching
    from lovely_assertions._matching import one_of as one_of
    from lovely_assertions._matching import string_containing as string_containing
    from lovely_assertions._matching import string_matching as string_matching
    from lovely_assertions._mock import MockExpect as MockExpect
    from lovely_assertions._mock import is_mock as is_mock
    from lovely_assertions._names import custom_assertion as custom_assertion
    from lovely_assertions._numeric import NumericExpect as NumericExpect
    from lovely_assertions._occurrence import Occurrence as Occurrence
    from lovely_assertions._occurrence import at_least as at_least
    from lovely_assertions._occurrence import at_most as at_most
    from lovely_assertions._occurrence import exactly as exactly
    from lovely_assertions._occurrence import less_than as less_than
    from lovely_assertions._occurrence import more_than as more_than
    from lovely_assertions._occurrence import once as once
    from lovely_assertions._occurrence import twice as twice
    from lovely_assertions._ordered import OrderedExpect as OrderedExpect
    from lovely_assertions._path import PathExpect as PathExpect
    from lovely_assertions._path import PurePathExpect as PurePathExpect
    from lovely_assertions._sequence import SequenceExpect as SequenceExpect
    from lovely_assertions._string import StringExpect as StringExpect
    from lovely_assertions._subjects import expect as expect
    from lovely_assertions._subjects import register as register
    from lovely_assertions._type import TypeExpect as TypeExpect
    from lovely_assertions._warnings import WarnedExpect as WarnedExpect
    from lovely_assertions._warnings import expect_warns as expect_warns

#: Which module defines each public name. Read on first access and never again:
#: the value is bound into this module's globals, so the second use of a name is
#: an ordinary attribute lookup.
#:
#: This is what makes ``import lovely_assertions`` cost almost nothing. A suite
#: that asserts about strings and numbers never loads the path subject, the mock
#: subject or the warning machinery -- and one that imports the package to read
#: ``__version__`` loads none of it at all.
_HOME: dict[str, str] = {
    "AssertionFailure": "lovely_assertions._exceptions",
    "BoolExpect": "lovely_assertions._bool",
    "CallableExpect": "lovely_assertions._callable",
    "CollectionExpect": "lovely_assertions._collection",
    "DateExpect": "lovely_assertions._datetime",
    "DateTimeExpect": "lovely_assertions._datetime",
    "EnumExpect": "lovely_assertions._enum",
    "Equivalency": "lovely_assertions._equivalence",
    "Expect": "lovely_assertions._core",
    "FormattingOptions": "lovely_assertions._formatting",
    "Found": "lovely_assertions._core",
    "IterableFormatter": "lovely_assertions._formatters",
    "MappingExpect": "lovely_assertions._mapping",
    "MockExpect": "lovely_assertions._mock",
    "NumericExpect": "lovely_assertions._numeric",
    "ObjectFormatter": "lovely_assertions._formatters",
    "Occurrence": "lovely_assertions._occurrence",
    "OrderedExpect": "lovely_assertions._ordered",
    "PathExpect": "lovely_assertions._path",
    "PurePathExpect": "lovely_assertions._path",
    "RaisedExpect": "lovely_assertions._callable",
    "SequenceExpect": "lovely_assertions._sequence",
    "SoftScope": "lovely_assertions._core",
    "StringExpect": "lovely_assertions._string",
    "TimeDeltaExpect": "lovely_assertions._datetime",
    "TimeExpect": "lovely_assertions._datetime",
    "TypeExpect": "lovely_assertions._type",
    "ValueFormatter": "lovely_assertions._formatters",
    "WarnedExpect": "lovely_assertions._warnings",
    "WithinDelta": "lovely_assertions._datetime",
    "any_instance_of": "lovely_assertions._matching",
    "anything": "lovely_assertions._matching",
    "at_least": "lovely_assertions._occurrence",
    "at_most": "lovely_assertions._occurrence",
    "close_to": "lovely_assertions._matching",
    "close_within": "lovely_assertions._equivalence",
    "containing": "lovely_assertions._matching",
    "current_formatting": "lovely_assertions._formatting",
    "custom_assertion": "lovely_assertions._names",
    "equivalency": "lovely_assertions._equivalence",
    "exactly": "lovely_assertions._occurrence",
    "expect": "lovely_assertions._subjects",
    "expect_raises": "lovely_assertions._callable",
    "expect_warns": "lovely_assertions._warnings",
    "format_value": "lovely_assertions._formatters",
    "formatting": "lovely_assertions._formatting",
    "is_matcher": "lovely_assertions._matching",
    "is_mock": "lovely_assertions._mock",
    "less_than": "lovely_assertions._occurrence",
    "matching": "lovely_assertions._matching",
    "more_than": "lovely_assertions._occurrence",
    "once": "lovely_assertions._occurrence",
    "one_of": "lovely_assertions._matching",
    "register": "lovely_assertions._subjects",
    "register_formatter": "lovely_assertions._formatters",
    "soft_assertions": "lovely_assertions._core",
    "string_containing": "lovely_assertions._matching",
    "string_matching": "lovely_assertions._matching",
    "twice": "lovely_assertions._occurrence",
}


def __getattr__(name: str) -> Any:  # noqa: ANN401  (the surface has no one shape)
    """Import the module that defines ``name``, and bind it here for next time."""
    from importlib import import_module  # noqa: PLC0415  (kept off import time)

    home = _HOME.get(name)
    if home is None:
        message = "module " + __name__ + " has no attribute " + repr(name)
        raise AttributeError(message)
    value = getattr(import_module(home), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """The public surface, whether or not it has been reached for yet."""
    return sorted(__all__)


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
