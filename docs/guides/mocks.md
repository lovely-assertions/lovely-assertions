# Mocks

`expect(some_mock, as_=MockExpect)` gives you a `MockExpect`. Three reasons to
prefer it over `unittest.mock`'s own assertions: **a misspelling is caught**,
**the failure says which call was wrong**, and — for an `AsyncMock` —
**a coroutine nobody awaited stops passing silently**.

> **Write `as_=MockExpect`.** A plain `expect(fetch)` builds the right subject at
> runtime, and every example here would work without it — but a type checker
> reads `TypeExpect` and rejects the mock assertions. That is not an oversight;
> the reason is in [the gotcha below](#statically-expectmock-is-not-a-mockexpect).
> Naming the subject class costs one keyword and keeps your suite green under a
> strict checker.

> Full signatures: [`MockExpect`](../reference/assertions.md#mockexpect) and
> [`AsyncMockExpect`](../reference/assertions.md#asyncmockexpect).

## The catalogue

```python
from unittest.mock import Mock

from lovely_assertions import expect, MockExpect

fetch = Mock()
fetch("/users")
fetch("/orders", retries=2)

expect(fetch, as_=MockExpect).has_call_count(2).was_called_with("/orders", retries=2)
```

| | Asserts |
|---|---|
| `was_called()` | at least once |
| `was_not_called()` | never |
| `was_called_once()` | exactly once, any arguments |
| `was_called_with(...)` | the **last** call used these arguments |
| `was_called_once_with(...)` | called exactly once, with these |
| `was_ever_called_with(...)` | **some** call used these |
| `was_never_called_with(...)` | no call did |
| `has_call_count(n)` | called exactly `n` times — or takes an [occurrence](occurrences.md), so `has_call_count(at_least(2))` reads as it sounds |
| `.calls` | a sequence subject over every recorded call |
| `.last_call()` | asserts there was one, and continues on it with `.which` |

Note the difference between `was_called_with` (the last call) and
`was_ever_called_with` (any call) — the distinction `assert_called_with` and
`assert_any_call` make, with names that say which is which.

A failure names the mock and lists what it actually recorded:

```python
from unittest.mock import Mock

from lovely_assertions import expect, MockExpect, AssertionFailure

fetch = Mock()
fetch("/users")
fetch("/orders", retries=2)

try:
    expect(fetch, as_=MockExpect).was_not_called()
except AssertionFailure as failure:
    print(failure)
```

```text
Expected fetch not to have been called, but it was called 2 times: [('/users'), ('/orders', retries=2)].
```

## Why not `unittest.mock`'s own assertions

### A misspelling passes

A mock answers every attribute. That is what a mock is *for*, and it is also why
an assertion made against one can be silently absent:

<!-- docs-test: skip - the point is that this passes while asserting nothing -->

```python
fetch.assert_called_once_wth("/users")  # passes. asserts nothing.
```

`unittest.mock` knows this and defends with a **denylist**: `__getattr__` refuses
any name beginning `assert`, `assret`, `asert`, `aseert` or `assrt`, plus the
assertion names with `assert_` stripped off — `called_once_with`, `not_called`
and the rest. So the common typo above is caught on a current interpreter.

A denylist catches the mistakes somebody thought of. It does not catch a name
borrowed from another framework — `was_called_once_with`, `verify_called_with`,
`toHaveBeenCalledWith` all return a child mock and pass — and `Mock(unsafe=True)`
turns the guard off entirely.

`expect()` needs no denylist:

<!-- docs-test: expect-error - a misspelling, which the checker rejects too -- that is the point of the example -->

```python
from unittest.mock import Mock

from lovely_assertions import expect, MockExpect

fetch = Mock()
try:
    expect(fetch, as_=MockExpect).was_called_once_wth("/users")
except AttributeError as error:
    print(error)
```

```text
'MockExpect' object has no attribute 'was_called_once_wth'
```

An `AttributeError` on a `__slots__` subject with a fixed catalogue, in the test
that wrote it, on the line that wrote it — for **every** misspelling, including
the ones nobody has thought of yet.

One mistake this does not fix, because it is not a spelling mistake: after
`api.get("/a")`, `api.assert_not_called()` passes — and so does
`expect(api, as_=MockExpect).was_not_called()`. Every assertion here reads the
mock's own recorded calls, and that call went to the *child*. Ask the child,
`expect(api.get, as_=MockExpect)`, or the whole recording, `expect(api.mock_calls)`.

### The failure says which call was wrong

`assert_called_once_with` fails three different ways — never called, called with
something else, called more than once — and two of them come back as the same
sentence about the count. Here each is its own message.

**Called with the wrong arguments**, and the difference goes through the same
engine as every other comparison:

```python
from unittest.mock import Mock

from lovely_assertions import expect, MockExpect, AssertionFailure

fetch = Mock()
fetch("/users")
fetch("/orders", retries=2)

try:
    expect(fetch, as_=MockExpect).was_called_with("/nope")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected fetch to have been called with ('/nope'), but was last called with ('/orders', retries=2).
  positional arguments:
    first difference at index 0: '/orders' instead of '/nope'
  keyword arguments:
    extra keys: ['retries']
```

**Called the right way but the wrong number of times** — and it says so
explicitly, rather than leaving you to compare argument lists by eye:

```python
from unittest.mock import Mock

from lovely_assertions import expect, MockExpect, AssertionFailure

fetch = Mock()
fetch("/users")
fetch("/orders", retries=2)

try:
    expect(fetch, as_=MockExpect).was_called_once_with("/users")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected fetch to have been called once with ('/users'), but it was called 2 times: [('/users'), ('/orders', retries=2)].
  call 1 was made with those arguments; it is the call count that is wrong
```

That last line is the fact `unittest.mock` never tells you.

**Never called with those arguments**, with the closest attempt named:

```python
from unittest.mock import Mock

from lovely_assertions import expect, MockExpect, AssertionFailure

fetch = Mock()
fetch("/users")
fetch("/orders", retries=2)

try:
    expect(fetch, as_=MockExpect).was_ever_called_with("/nope")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected fetch to have been called with ('/nope') at some point, but none of its 2 calls was: [('/users'), ('/orders', retries=2)].
  the closest was call 1:
    positional arguments:
      first difference at index 0: '/users' instead of '/nope'
```

## Async mocks

An `AsyncMock` records two different things, and a test almost always means the
second. *Calling* it appends to the call recording and hands back a coroutine;
*awaiting* that coroutine is what runs the body and appends to the await
recording.

Code that builds a coroutine and drops it — a missing `await`, a task nobody
gathered, a `TaskGroup` that exited before the work started — leaves the first
recording full and the second empty. Every assertion about **calls** passes in
that state, here and in `unittest.mock` both:

```python
from unittest.mock import AsyncMock

from lovely_assertions import expect, MockExpect

publish = AsyncMock()
publish("order.placed")  # the coroutine is built, and nobody awaits it

expect(publish, as_=MockExpect).was_called_once_with("order.placed")
print("passed, and the work never ran")
```

```text
passed, and the work never ran
```

That is not wrong — it *was* called. It is simply not what the test meant, and
nothing in the call catalogue can say so. `AsyncMockExpect` is the other half:

```python
from unittest.mock import AsyncMock

from lovely_assertions import expect, AsyncMockExpect, AssertionFailure

publish = AsyncMock()
publish("order.placed")

try:
    expect(publish, as_=AsyncMockExpect).was_awaited()
except AssertionFailure as failure:
    print(failure)
```

```text
Expected publish to have been awaited, but it was called once with ('order.placed') and never awaited.
```

Compare what `unittest.mock` prints for that same state:

```python
from unittest.mock import AsyncMock

publish = AsyncMock()
publish("order.placed")

try:
    publish.assert_awaited_once()
except AssertionError as failure:
    print(failure)
```

```text
Expected mock to have been awaited once. Awaited 0 times.
```

It never mentions that the mock *was* called, or with what — which is the entire
bug. It prints the same sentence for a mock that was never called at all, so the
two failures a reader most needs to tell apart look identical.

### The await catalogue

`expect()` hands you an `AsyncMockExpect` for anything that records awaits: an
`AsyncMock`, a `Mock(spec=some_async_function)`, or the async members of an
autospecced class. It is a `MockExpect` with one more catalogue on it, so
everything in the table above still applies.

| | Asserts |
|---|---|
| `was_awaited()` | at least once |
| `was_not_awaited()` | never — and passes for a mock that was never called |
| `was_awaited_once()` | exactly once, any arguments |
| `was_awaited_with(...)` | the **last** await used these arguments |
| `was_awaited_once_with(...)` | awaited exactly once, with these |
| `was_ever_awaited_with(...)` | **some** await used these |
| `was_never_awaited_with(...)` | no await did |
| `has_await_count(n)` | awaited exactly `n` times — or takes an [occurrence](occurrences.md) |
| `.awaits` | a sequence subject over every recorded await |
| `.last_await()` | asserts there was one, and continues on it with `.which` |

The two counts can disagree, and that they can is the point:

```python
import asyncio
from unittest.mock import AsyncMock

from lovely_assertions import expect, AsyncMockExpect, AssertionFailure

publish = AsyncMock()


async def drain() -> None:
    await publish("a")
    await publish("b")
    publish("c")  # built, never awaited


asyncio.run(drain())

expect(publish, as_=AsyncMockExpect).has_call_count(3).has_await_count(2)

try:
    expect(publish, as_=AsyncMockExpect).has_await_count(3)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected publish to have been awaited exactly 3 times, but it was awaited 2 times: [('a'), ('b')].
```

`was_never_awaited_with` is worth a second look. Its call-side twin fails on a
dry run that *builds* the forbidden request; this one passes, because no work was
done — which is usually the honest answer.

### Dropping a coroutine warns, and that is worth keeping

Every example above builds a coroutine and never awaits it, which is the state
under test — and Python says so, on stderr, whenever the garbage collector gets
to one:

```text
RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
```

That warning is CPython's, not the library's, and it fires wherever the collector
happens to run rather than on the line that caused it. In a suite that turns
warnings into errors it will land on an unrelated test. Where you are
deliberately constructing this state, close the coroutine — `publish("x").close()`
— which changes nothing the mock recorded and keeps the warning off your other
tests.

Treat the warning as a second signal rather than noise: on a test you did *not*
mean to write this way, it is telling you the same thing `was_awaited` would.

### A plain `Mock` has no await assertions

That is deliberate, and it is enforced by both type checkers rather than by a
runtime guard. A synchronous `Mock` keeps no await recording — and because a mock
answers every attribute with a child mock, an await assertion pointed at one
would compare against that child and *pass*. So the catalogue lives on the
subject that can answer it:

<!-- docs-test: expect-error - a Mock subject has no await assertions, which is the point of the section -->

```python
from unittest.mock import Mock

from lovely_assertions import expect, MockExpect

try:
    expect(Mock(), as_=MockExpect).was_awaited()
except AttributeError as error:
    print(error)
```

```text
'MockExpect' object has no attribute 'was_awaited'
```

Both checkers reject that line, and at runtime it is an `AttributeError` on the
line that wrote it — exactly as a misspelling is.

## Asserting on the calls themselves

`.calls` gives you a [sequence subject](sequences.md) over the recorded calls, so
the whole ordered catalogue applies:

```python
from unittest.mock import Mock

from lovely_assertions import expect, MockExpect, AssertionFailure

fetch = Mock()
fetch("/users")
fetch("/orders", retries=2)

expect(fetch, as_=MockExpect).calls.has_length(2)

try:
    expect(fetch, as_=MockExpect).calls.has_length(9)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected fetch to have length 9, but had 2: [call('/users'), call('/orders', retries=2)].
```

## Matchers in call arguments

Recorded arguments are compared, so [matchers](matchers.md) work:

```python
from unittest.mock import Mock

from lovely_assertions import expect, MockExpect, any_instance_of, one_of, AssertionFailure

fetch = Mock()
fetch("/users", retries=3)

try:
    expect(fetch, as_=MockExpect).was_called_with(any_instance_of(str), retries=one_of(0, 1))
except AssertionFailure as failure:
    print(failure)
```

```text
Expected fetch to have been called with (<any str>, retries=<one of 0, 1>), but was called with ('/users', retries=3).
  keyword arguments:
    values differ at key 'retries': 3 instead of <one of 0, 1>
```

## `is_mock`

```python
from unittest.mock import Mock

from lovely_assertions import is_mock

print(is_mock(Mock()), is_mock(3))
```

```text
True False
```

It asks the **class**, not the instance — so a hand-rolled spy that builds its
markers in `__init__` is not recognised.

One narrow exception, and it exists because the standard library needs it:
`create_autospec(some_function)` does not return a mock at all. It returns a real
function with the mock protocol hung off it as *instance* attributes, so that
call is checked on the instance too. Nothing else is.

## Gotchas

### Statically, `expect(mock)` is not a `MockExpect`

At runtime it is. To a type checker it is not, and the mock assertions are
errors. This is not an oversight: typeshed puts an `Any` in `NonCallableMock`'s
MRO, so a mock is assignable to *every* parameter type. An overload written for
mocks would have to lead the chain to be reached at all, and one that leads it
overlaps most of the others — a pile of suppressions for an answer that only
helps where a parameter is *declared* `Mock`. The full reasoning is in
[Typed dispatch](../concepts/typed-dispatch.md#the-one-place-the-two-halves-do-not-agree).

**`expect(fetch, as_=MockExpect)` is the typed route**, and it is what every
example on this page uses.

The same holds for `AsyncMockExpect`, and there it costs more than tidiness:
naming the subject is the *only* place a checker sees that a synchronous `Mock`
has no `was_awaited`. Written as `expect(fetch)`, both the await assertions and
their absence are invisible to it.

### `as_=AsyncMockExpect` on a synchronous mock is refused, not answered

`as_=` overrides inference, and **no checker can refuse it here**: the subject's
value is `Any`, so pointing the async subject at a plain `Mock` type-checks. The
runtime will not answer it either, which is the point — a mock replies to every
attribute, so `await_args_list` on a synchronous one is a child mock standing in
for a list, and an assertion that merely tested it for truth would pass having
compared nothing.

Every await assertion reads that recording's *length* rather than its truth, so
the misuse surfaces instead: a `Mock` has no `__len__` and you get a `TypeError`,
a `MagicMock` answers `0` and the assertion fails. Neither is a silent green.

The lesson generalises — `as_=` is a claim you are making, not one the library
verifies. It is the same trade `register()` makes, and the reason `expect()`'s own
inference is the route to prefer wherever your annotations reach.

### No signature normalisation

`unittest.mock`'s own assertions on an autospec'd mock normalise arguments
against the real signature, so `f(1)` and `f(x=1)` match. These do not — they
compare what was recorded. An autospec'd mock's own assertion can therefore pass
where `expect()` fails.

### A call argument named `because`

`because` is keyword-only on every assertion in the library, so a call the mock
really made with `because=` cannot be spelled here: the value is taken as the
failure reason, and the assertion then fails reporting the recorded `because=`
as a keyword argument it did not expect. Assert on the recording instead, with
`unittest.mock`'s own `call` —
`expect(fetch, as_=MockExpect).calls.contains(call("/users", because="audit"))`.

### `unittest.mock` is never imported

Not at module level and not inside a function. Recognising a mock is a question
about a class, and asserting on one reads a single ordinary attribute. A test
session that never mentions a mock does not pay for the import.

### A `MagicMock` does not get a collection subject

It defines `__len__` and `__contains__`, so it looks like a collection. The
dispatch checks for a mock first, deliberately.

---

**See also:** [matchers](matchers.md) · [sequences](sequences.md) ·
[typed dispatch](../concepts/typed-dispatch.md)
