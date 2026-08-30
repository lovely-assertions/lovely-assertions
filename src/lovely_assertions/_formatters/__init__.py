"""How a value is rendered inside a failure message.

``repr`` is the right default and a poor one for domain objects: a message that
reads ``<myapp.orders.Order object at 0x10f3a2d90>`` gives the reader a memory
address in place of the thing they are trying to understand. FluentAssertions
answers that with registerable formatters, and this is the port.

Two registries, consulted in one order. **Scoped** formatters come first,
innermost scope outwards; then the **global** ones, in registration order; then
``repr``. The first formatter whose ``can_handle`` claims the value wins. Scoped
goes in front because that is the entire point of scoping: a block that needs a
different rendering must be able to get one without mutating configuration every
other test shares.

Three rules shape everything here.

**Nothing runs for a passing assertion.** :func:`format_value` is called from a
failure branch and from nowhere else, so it may read a ``ContextVar``, allocate
and format freely -- and a passing assertion pays for none of it.

**It never raises.** Formatters are user code, and user code has bugs. One that
throws is skipped exactly as if it had declined; a value nothing claims falls
back to ``repr``; a value whose ``repr`` also throws is named by its type.
Turning somebody's failing test into an error raised inside the assertion
library is the worst outcome available, and every rendering helper in the
library takes the same line.

**It formats with concatenation, never f-strings.** An f-string is evaluated
where it is written, so the library confines them to arguments of ``_fail`` --
the one call reached only once a failure is certain -- and a module with no
``_fail`` in it therefore has no f-strings at all. This is one of those modules;
``_diff`` is another.
"""

from lovely_assertions._exceptions import hide_internal_frames
from lovely_assertions._formatters._builtin import IterableFormatter, ObjectFormatter
from lovely_assertions._formatters._protocol import ValueFormatter
from lovely_assertions._formatters._registry import (
    FormatterToken,
    pop_formatters,
    push_formatters,
    register_formatter,
)
from lovely_assertions._formatters._render import format_value

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames

__all__ = [
    "FormatterToken",
    "IterableFormatter",
    "ObjectFormatter",
    "ValueFormatter",
    "format_value",
    "pop_formatters",
    "push_formatters",
    "register_formatter",
]
