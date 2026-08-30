"""Rich differences between two values that were supposed to be equal.

pytest's assert rewriting already prints a serviceable diff for ``assert a == b``.
This package exists for the cases where it does not help: a multi-line string
flattened into one escaped ``repr``, a mapping of twenty keys of which one holds
the wrong value, a record of twelve fields of which one holds the wrong value,
two collections with the same items in a different order, two values that render
identically and still are not equal.

One entry point, :func:`describe_difference`, called on the failure path only and
appended to a message that already carries both ``repr``\\ s. It therefore says
only what those reprs cannot: *where* the two values part company.

Three rules shape everything here.

**It never raises.** A subject whose ``repr`` or ``__eq__`` blows up must still
produce an assertion *failure*, not an error inside the assertion library. Every
path degrades to ``""``.

**It is bounded, and the bounds are a scope rather than four constants.** Ten
items, twenty diff lines, a hundred and twenty characters per value, two levels of
nesting -- whatever is left out is counted in the message rather than dropped
silently. Those four numbers live as the defaults on
:class:`~lovely_assertions.FormattingOptions` and are read through
:func:`~lovely_assertions.current_formatting` at each point of use, so the reader
whose failing row is the four hundredth can ask to see it::

    with formatting(max_items=100):
        expect(rows).is_equal_to(expected)

Reading them is a ``ContextVar`` lookup, which a *passing* assertion must never
pay for, so every one of those reads has to stay where the whole of this package
already lives: on the failure path.

**It formats with concatenation, never f-strings.** Nothing here runs on the happy
path, but the package's rule is that a message is never built outside the argument
list of a ``_fail(...)`` call -- Python evaluates arguments eagerly, so an f-string
one line too early costs every passing assertion in every suite -- and a rule with
no exceptions is worth more than the syntax it costs.

The engine is one file per kind of thing being compared -- text, sequences,
mappings, sets, records -- over a shared bottom of leaf operations that know
nothing about any of them. No copy of those four legibility bounds is kept
anywhere in it: a second source of truth is one the two would drift apart from.

A few modules do hold a constant, and they are of a different kind. They bound
what the *engine* may cost while a test is already failing -- how much text
``difflib`` may be handed, how many unhashable items may be paired off -- and a
caller who could raise one could hang a red test run, so none of them is offered.
Each lives with the code that spends it.

Every module here is private and the package is entered only through this file.
A name that crosses from one module to the next carries no underscore, because
pyright strict refuses to import one that does; a name read only where it is
written keeps it. The underscore on the package is what keeps all of it private.
"""

from lovely_assertions._diff._dispatch import describe_difference
from lovely_assertions._diff._primitives import render_operand, stable_order
from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = ["describe_difference", "render_operand", "stable_order"]
