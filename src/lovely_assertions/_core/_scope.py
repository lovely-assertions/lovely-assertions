"""Gathering several failures into one report instead of stopping at the first.

The worst failure mode this library has is a scope left open: every assertion
after it collects instead of raising, and a suite goes green while asserting
nothing. So the scope is a context manager that cannot be opened twice, cannot
be exited out of order, and cannot be exited from a different context than the
one that opened it -- and each of those refusals says which happened.
"""

from types import TracebackType
from typing import TYPE_CHECKING, Self, override

from lovely_assertions._core._rendering import note_collected, render_aggregate
from lovely_assertions._core._routing import ACTIVE_COLLECTOR, Collector
from lovely_assertions._exceptions import AssertionFailure, hide_internal_frames
from lovely_assertions._formatters import (
    FormatterToken,
    ValueFormatter,
    pop_formatters,
    push_formatters,
)

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
if TYPE_CHECKING:
    from contextvars import Token

__tracebackhide__ = hide_internal_frames


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


#: The singular form, because "1 assertions" reads as a message nobody looked at
#: -- the same rule :func:`~lovely_assertions._text.count_of` exists for.


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
        self._collector = Collector(name or "")
        self._parent: Collector | None = None
        self._token: Token[Collector | None] | None = None
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
        parent = ACTIVE_COLLECTOR.get()
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
        self._token = ACTIVE_COLLECTOR.set(self._collector)
        return self

    def _leave(self, token: "Token[Collector | None] | None", /) -> str:
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
        was_routed_here = ACTIVE_COLLECTOR.get() is self._collector
        try:
            ACTIVE_COLLECTOR.reset(token)
        except ValueError:
            # Made in another thread or task. That context is not this one and is
            # not ours to repair -- switching the routing off here would kill a
            # scope this one never opened.
            return _FOREIGN_CONTEXT
        if was_routed_here:
            return ""
            # Same context, wrong order: a scope opened after this one is still open,
            # so what the token just restored is a collector that has already ended.
        ACTIVE_COLLECTOR.set(None)
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
            note_collected(exc, self._collector.failures)
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
        raise AssertionFailure(render_aggregate(collected))
