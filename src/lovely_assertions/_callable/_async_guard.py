"""Refusing a coroutine function handed to a synchronous assertion.

``expect(fetch).raises(...)`` on an ``async def`` would call it, get a coroutine,
and assert that building one raised nothing -- which is true and says nothing
about ``fetch``. It is refused instead.

The coroutine that was already built is closed on the way out. Leaving it would
print a "never awaited" warning from a line the caller cannot see, attached to a
test that failed for an entirely different reason.
"""

from collections.abc import Awaitable

from lovely_assertions._exceptions import hide_internal_frames

#: pytest reads ``__tracebackhide__`` from a frame's globals, so this one
#: assignment folds every frame of this module out of an assertion failure's
#: traceback while leaving them in place for a genuine error. See
#: :func:`lovely_assertions._exceptions.hide_internal_frames`.
__tracebackhide__ = hide_internal_frames


def is_awaitable(value: object, /) -> bool:
    """Whether ``value`` is awaitable.

    Deliberately a plain ``bool`` and not a ``TypeIs``: a narrowing return would
    re-type the caller's variable to ``Awaitable[Unknown]``, which is the one
    thing pyright's strict mode will not accept being passed on. Nothing
    downstream needs the narrowed type.
    """
    return isinstance(value, Awaitable)


def close_quietly(value: object, /) -> None:
    """Close a coroutine that will never be awaited.

    Without it the reader is handed a "coroutine was never awaited" warning from
    somewhere unrelated to the test that caused it. Takes ``object`` rather than
    narrowing to ``Coroutine`` on purpose: a parameterised generic is exactly the
    shape pyright calls partially unknown and mypy calls a redundant cast, and
    neither checker needs an opinion here. Anything without ``close`` -- a Future,
    a custom ``__await__`` -- is not ours to close anyway.
    """
    close = getattr(value, "close", None)
    if callable(close):
        close()


def reject_awaitable(returned: object, /) -> None:
    """Refuse a result that was never actually run.

    Calling an ``async def`` returns a coroutine without executing a line of its
    body, so a synchronous exception assertion sees no exception and reports
    success. Without this refusal ``expect(async_fn).does_not_raise()`` passes for
    a function that raises unconditionally -- a green test that asserts nothing,
    which is the one outcome this library exists to prevent.

    Raised, not reported: handing an async callable to a synchronous assertion is
    a mistake in the test, and an ``AssertionFailure`` would present it as a
    finding about the subject. The coroutine is closed on the way out so the
    reader is not also handed a "never awaited" warning from somewhere else
    entirely.
    """
    if not is_awaitable(returned):
        return
    close_quietly(returned)
    message = (
        "the callable returned a coroutine without running: an async callable "
        "cannot be asserted on synchronously. Await it and assert on the result, "
        "or assert on a lambda that runs it -- expect(lambda: asyncio.run(fn()))"
    )
    raise TypeError(message)
