"""What the fuzzers check, as plain functions.

Kept apart from the Atheris drivers so that the claims below are exercised on
every platform by ``tests/test_fuzzing.py``, not only on the one platform Atheris
has wheels for -- and so that a crash the fuzzer finds reduces to a single call
with a single argument.

Every function here takes bytes and returns ``None``. Raising is the failure
signal, and the message says which promise broke.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Final

from lovely_assertions import AssertionFailure, expect, formatting

if TYPE_CHECKING:
    from collections.abc import Callable

#: What a failing assertion is allowed to raise.
#:
#: ``AssertionFailure`` is the answer for a failed comparison. ``ValueError`` and
#: ``TypeError`` are the answer for a caller who misused the API -- a negative
#: size, a matcher where a value belongs -- and the fuzzer reaches those too,
#: because it is generating arguments rather than writing sensible ones.
#: ``RecursionError`` is the interpreter's, not the library's, and is reachable
#: by handing it a structure deeper than the stack.
PERMITTED: Final[tuple[type[BaseException], ...]] = (
    AssertionFailure,
    ValueError,
    TypeError,
    RecursionError,
)

#: A message longer than this is a message nobody reads, and the library promises
#: a bounded one. Generous on purpose: this is a bound, not a target, and a
#: difference block over a large value is legitimately long.
MAX_MESSAGE: Final = 100_000


def _guard(call: Callable[[], object], /, *, what: str) -> None:
    """Run ``call`` and hold it to the two promises every assertion makes.

    Whatever the subject is, the only ways out are a pass or one of
    :data:`PERMITTED` -- and the message a failure carries is bounded.
    """
    try:
        call()
    except PERMITTED as failure:
        text = str(failure)
        if len(text) > MAX_MESSAGE:
            message = f"{what}: message ran to {len(text)} characters, which is not bounded"
            raise AssertionError(message) from failure
    except Exception as unexpected:
        message = (
            f"{what}: raised {type(unexpected).__name__} rather than failing. "
            f"An assertion may fail; it may not turn a comparison into an error."
        )
        raise AssertionError(message) from unexpected


def _values(data: bytes, /) -> tuple[object, object]:
    """Two operands derived from one input, of deliberately mismatched shapes."""
    half = len(data) // 2
    left, right = data[:half], data[half:]
    shapes: Final[list[object]] = [
        left,
        left.decode("utf-8", "replace"),
        list(left),
        set(left),
        dict(enumerate(left)),
        tuple(left),
        len(left),
        float(len(left)) if left else math.nan,
        frozenset(left),
        [list(left), {"k": right.decode("utf-8", "replace")}],
    ]
    if not data:
        return None, None
    return shapes[data[0] % len(shapes)], shapes[data[-1] % len(shapes)]


def equality(data: bytes, /) -> None:
    """Comparing two arbitrary values fails; it does not error."""
    left, right = _values(data)
    _guard(lambda: expect(left).is_equal_to(right), what="is_equal_to")
    _guard(lambda: expect(left).is_not_equal_to(right), what="is_not_equal_to")
    _guard(lambda: expect(left).is_equivalent_to(right), what="is_equivalent_to")


def strings(data: bytes, /) -> None:
    """The string catalogue survives arbitrary text, at any width setting."""
    text = data.decode("utf-8", "replace")
    other = text[len(text) // 2 :]
    _guard(lambda: expect(text).is_equal_to(other), what="str.is_equal_to")
    _guard(lambda: expect(text).contains(other), what="contains")
    _guard(lambda: expect(text).starts_with(other), what="starts_with")
    _guard(lambda: expect(text).is_identifier(), what="is_identifier")
    _guard(lambda: expect(text).is_uuid(), what="is_uuid")
    # The clipping arithmetic is where a width and a code point interact, and a
    # narrow scope is the setting under which the hunk header was once
    # mis-shifted -- so the widths are part of the input rather than the default.
    width = 1 + (data[0] if data else 0) % 40
    with formatting(max_chars=width):
        _guard(lambda: expect(text).is_equal_to(other), what=f"is_equal_to @ max_chars={width}")


class _Unrenderable:
    """A value the library cannot print, in whichever way the input asks.

    Rendering is the library's own job: it happens while building a message, on
    the failure path, behind an explicit promise that running somebody else's
    ``__repr__`` never turns a failure into an error. Nothing this class does may
    escape as anything but an ``AssertionFailure``.
    """

    __slots__ = ("_kind", "_payload")

    def __init__(self, kind: int, payload: bytes, /) -> None:
        self._kind = kind
        self._payload = payload

    def __repr__(self) -> str:
        if self._kind & 1:
            message = "this repr refuses"
            raise RuntimeError(message)
        if self._kind & 2:
            message = "this repr refuses, recursively"
            raise RecursionError(message)
        if self._kind & 4:
            # Enormous rather than raising: the clip has to survive it too, and
            # a bounded message is the other half of the promise.
            return "x" * (1 + len(self._payload) * 997)
        if self._kind & 8:
            return "\x00\udcff" + self._payload.decode("utf-8", "surrogateescape")
        return self._payload.decode("utf-8", "replace")


class _Uncomparable:
    """A value that misbehaves when compared, rather than when printed.

    A different promise applies here, and the difference is the point. Asking
    ``is_equal_to`` to compare two values *is* the assertion, so a ``__eq__`` that
    raises propagates -- exactly as a bare ``assert a == b`` would, and the
    library does not pretend otherwise. The structural walk behind
    ``is_equivalent_to`` promises more: it runs the comparison itself, to describe
    a difference, and a comparison must never turn a difference into an error.
    """

    __slots__ = ("_kind", "_payload")

    def __init__(self, kind: int, payload: bytes, /) -> None:
        self._kind = kind
        self._payload = payload

    def __repr__(self) -> str:
        return "Uncomparable(" + repr(self._payload[:8]) + ")"

    def __eq__(self, other: object) -> bool:
        if self._kind & 1:
            message = "this eq refuses"
            raise RuntimeError(message)
        if self._kind & 2:
            # Neither equal nor unequal, which is what a Mock does.
            return NotImplemented
        return self is other

    def __hash__(self) -> int:
        if self._kind & 4:
            message = "this hash refuses"
            raise RuntimeError(message)
        return 0


def hostile_rendering(data: bytes, /) -> None:
    """A value the library cannot print still fails; it does not error."""
    if not data:
        return
    subject = _Unrenderable(data[0], data[1:])
    other = _Unrenderable(data[-1], data[1:][::-1])

    _guard(lambda: expect(subject).is_equal_to(other), what="unrenderable is_equal_to")
    _guard(lambda: expect([subject, other]).has_length(99), what="unrenderable has_length")
    _guard(lambda: expect({"k": subject}).is_equal_to({"k": 1}), what="unrenderable mapping")
    _guard(lambda: expect(subject).is_equivalent_to(other), what="unrenderable is_equivalent_to")
    _guard(lambda: expect(subject).is_instance_of(int), what="unrenderable is_instance_of")


def hostile_comparison(data: bytes, /) -> None:
    """The structural walk absorbs a comparison that refuses; the direct one does not.

    Only ``is_equivalent_to`` is held to the stricter promise here. The direct
    comparisons are allowed to propagate the subject's own exception, because
    performing that comparison is the whole of what they were asked to do -- and
    a fuzzer that called that a defect would be encoding a wish rather than the
    contract.
    """
    if not data:
        return
    subject = _Uncomparable(data[0], data[1:])
    other = _Uncomparable(data[-1], data[1:][::-1])

    _guard(lambda: expect(subject).is_equivalent_to(other), what="uncomparable is_equivalent_to")
    _guard(
        lambda: expect([subject]).is_equivalent_to([other]),
        what="uncomparable is_equivalent_to in a sequence",
    )
    _guard(
        lambda: expect({"k": subject}).is_equivalent_to({"k": other}),
        what="uncomparable is_equivalent_to in a mapping",
    )
