# Exceptions

Two forms, both landing on the same subject. Use whichever fits the call.

**Context manager** — the primary one, where `pytest.raises` sits:

```python
from lovely_assertions import expect_raises


def parse_port(text: str) -> int:
    return int(text)


with expect_raises(ValueError) as caught:
    parse_port("nope")

caught.with_message_containing("invalid literal")
print("caught and inspected")
```

```text
caught and inspected
```

Assert on `caught` *after* the block, never inside it. Inside, the exception does
not exist yet: an assertion written after the raising call never runs at all, so
the test passes with that check never made, and one that is reachable raises a
`RuntimeError` saying the exception is only available once the block has
finished.

**Callable** — the assertion does the calling, so the subject is a zero-argument
callable; wrap anything that needs arguments in a lambda:

```python
from lovely_assertions import expect


def parse_timeout(text: str) -> float:
    return float(text)


expect(lambda: parse_timeout("nope")).raises(ValueError)
print("raised as required")
```

```text
raised as required
```

> Full signatures: [`RaisedExpect[E]`](../reference/assertions.md#raisedexpecte)
> and [`CallableExpect`](../reference/assertions.md#callableexpect).

## What the failures tell you

Two ways this goes wrong, and the message says which.

**The wrong exception was raised** — and the message shows you what *did* come
out, which is the fact that ends the investigation:

```python
from lovely_assertions import expect_raises, AssertionFailure


def parse_port(text: str) -> int:
    return int(text)


try:
    with expect_raises(KeyError):
        parse_port("nope")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected KeyError to be raised, but ValueError("invalid literal for int() with base 10: 'nope'") was raised instead.
```

When this happens, the assertion failure is **chained onto the real exception**,
so its traceback survives next to the message instead of being replaced by it.

**Nothing was raised at all:**

```python
from lovely_assertions import expect_raises, AssertionFailure


def parse_port() -> int:
    return 8080


try:
    with expect_raises(ValueError):
        parse_port()
except AssertionFailure as failure:
    print(failure)
```

```text
Expected ValueError to be raised, but nothing was raised.
```

The callable form goes one better and tells you what the call returned instead —
often the clue you need:

```python
from lovely_assertions import expect, AssertionFailure


def parse_port() -> int:
    return 8080


try:
    expect(parse_port).raises(ValueError)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected parse_port to raise ValueError, but nothing was raised (the call returned 8080).
```

## Asserting on the exception

The handle from `expect_raises` is a subject over the exception:

| | Asserts |
|---|---|
| `with_message(pattern)` | `str(exception)` **matches the regex** `pattern` (a search, not a full match) |
| `with_message_containing(text)` | `str(exception)` contains `text` |
| `where(predicate)` | the exception satisfies `predicate`, typed with the exception type you asked for — for the attributes a specific exception carries, `errno` or `status_code` |
| `with_cause(Type)` | the cause is an instance of `Type` — `__cause__` if set, otherwise `__context__` — **and the cause becomes the subject**, so what you chain after this asserts on the inner exception |
| `with_cause_exactly(Type)` | the cause is exactly `Type`, looked up the same way, and it takes over as the subject too |
| `with_note(text)` | the exception carries that note |
| `with_note_matching(pattern)` | a note matches the pattern |
| `has_no_notes()` | there are none |
| `.which` | the same subject, spelled so the chain reads aloud — `raises(ValueError).which.with_message("...")`. Optional: the generic catalogue is already there |
| `.subject` | the exception itself |

### Messages

```python
from lovely_assertions import expect_raises, AssertionFailure


def parse_port(text: str) -> int:
    return int(text)


with expect_raises(ValueError) as caught:
    parse_port("nope")

try:
    caught.with_message_containing("no such file")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected the value to have a message containing 'no such file', but the message was "invalid literal for int() with base 10: 'nope'".
```

**Name the handle if you want a better sentence.** The subject there is the
exception, and the library has no expression to recover for it, so it says
`the value`. `described_as` fixes it:

```python
from lovely_assertions import expect_raises, AssertionFailure


def parse_port(text: str) -> int:
    return int(text)


with expect_raises(ValueError) as caught:
    parse_port("nope")

try:
    caught.described_as("the parse error").with_message("^boom")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected the parse error to have a message matching '^boom', but the message was "invalid literal for int() with base 10: 'nope'".
```

### Attributes

`where` takes a predicate over the exception, typed with the type you asked for.
It is where the attributes a specific exception carries get asserted on:

```python
from lovely_assertions import expect_raises, AssertionFailure


class HttpError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


def fetch() -> None:
    raise HttpError(503)


def is_retryable(error: HttpError) -> bool:
    return error.status_code == 429


with expect_raises(HttpError) as caught:
    fetch()

caught.where(lambda error: error.status_code >= 500)

try:
    caught.where(is_retryable)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected the value to satisfy is_retryable, but HttpError('HTTP 503') did not.
```

### Causes

`with_cause` asserts what the exception was raised from — and continues on the
cause, so everything chained after it is about the inner exception:

```python
from lovely_assertions import expect_raises, AssertionFailure


def load_config() -> None:
    try:
        raise KeyError("DATABASE_URL")
    except KeyError as missing:
        raise ValueError("configuration is incomplete") from missing


with expect_raises(ValueError) as caught:
    load_config()

try:
    # The message checked here is the KeyError's, not the ValueError's.
    caught.with_cause(KeyError).with_message_containing("configuration")
except AssertionFailure as failure:
    print(failure)

try:
    caught.with_cause(TypeError)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected the value to have a message containing 'configuration', but the message was "'DATABASE_URL'".
Expected the value to have a cause of type TypeError, but __cause__ was KeyError('DATABASE_URL').
```

`raise X from Y` sets `__cause__`. A bare `raise X` inside an `except` block sets
only `__context__` — the implicit chaining Python does for you — and that is far
more common in code nobody wrote with a test in mind. So both cause assertions
read `__cause__` first and fall back to `__context__`, and the failure names
which of the two it ended up looking at:

```python
from lovely_assertions import expect_raises, AssertionFailure


def load_config() -> None:
    try:
        raise KeyError("DATABASE_URL")
    except KeyError:
        raise RuntimeError("configuration is incomplete")


with expect_raises(RuntimeError) as caught:
    load_config()

caught.with_cause(KeyError)  # passes: __cause__ is None, __context__ is the KeyError

try:
    caught.with_cause(TypeError)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected the value to have a cause of type TypeError, but __context__ was KeyError('DATABASE_URL').
```

`raise X from None` suppresses the context, and the failure says so rather than
reporting a bare absence.

### Notes

```python
from lovely_assertions import expect_raises, AssertionFailure


def charge() -> None:
    error = ValueError("card declined")
    error.add_note("retry after 30s")
    raise error


with expect_raises(ValueError) as caught:
    charge()

caught.with_note("retry after 30s")

try:
    caught.with_note("contact support")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected the value to carry the note 'contact support', but its only note was 'retry after 30s'.
```

## Subclasses: `raises` versus `raises_exactly`

`expect_raises(ValueError)` and `raises(ValueError)` accept a subclass, as
`except` does. When only the exact type will do:

```python
from lovely_assertions import expect, expect_raises, AssertionFailure


class ConfigError(ValueError):
    pass


def load() -> None:
    raise ConfigError("bad")


expect(load).raises(ValueError)

try:
    expect(load).raises_exactly(ValueError)
except AssertionFailure as failure:
    print(failure)

with expect_raises(ValueError) as caught:
    load()

try:
    caught.is_exactly_instance_of(ValueError)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected load to raise exactly ValueError, but raised ConfigError('bad').
Expected the value to be exactly ValueError, but was ConfigError.
```

There is no `expect_raises_exactly`. With the block form, catch the base type and
pin the exact one on the handle, as the second half of that example does.

## Asserting that nothing is raised

```python
from lovely_assertions import expect, AssertionFailure


def parse_port() -> int:
    return int("nope")


try:
    expect(parse_port).does_not_raise()
except AssertionFailure as failure:
    print(failure)
```

```text
Expected parse_port not to raise, but raised ValueError("invalid literal for int() with base 10: 'nope'").
```

Worth having over just calling the function: the failure is an assertion failure
naming what you expected, rather than a raw traceback a reader has to interpret
as "this was not supposed to happen".

`does_not_raise(SomeType)` narrows it to one type — and lets every *other*
exception through, so the test errors rather than fails. That is usually what you
want, but it is worth knowing which of the two you are asking for.

## Gotchas

### A `BaseException` that is not an `Exception` passes through

Anything outside `Exception` — `KeyboardInterrupt`, `SystemExit`,
`asyncio.CancelledError`, a `BaseException` subclass of your own — travels when
you did not ask for it, through both forms and through `does_not_raise()` alike.
The rule is `isinstance(exc, Exception)` and nothing narrower, so a
`CancelledError` crossing one of these assertions errors the test rather than
failing it with a wrong-type message.

Name it and it is caught like anything else — `expect(shutdown).raises(SystemExit)`
works, and so does `does_not_raise(KeyboardInterrupt)` — because a type you named
is the subject of the test rather than an interruption of it.

### `async def` is refused by the callable form

Handing a coroutine function to `raises`, `raises_exactly` or `does_not_raise`
raises `TypeError` where you wrote it. A coroutine that is never awaited would not
raise anything, so the assertion would pass silently — which is the failure mode
worth refusing loudly.

The block form has no such guard. Calling an `async def` inside
`with expect_raises(...)` only builds a coroutine, so you get `but nothing was
raised` instead of the `TypeError`. Await the call, or run it:
`expect(lambda: asyncio.run(fetch())).raises(ValueError)`.

### A generator function is not drained

Calling one returns a generator without running its body, so nothing raises. Wrap
it: `expect(lambda: list(rows())).raises(ValueError)`.

### Soft scopes

Every assertion here reports through the same machinery as the rest of the
library, so an active [`soft_assertions()`](soft-assertions.md) scope collects
them alongside everything else.

With one wrinkle: if the `expect_raises` itself fails inside a scope, there is no
exception left to assert about, so every later assertion on that handle is
skipped. You get the one root cause rather than a cascade derived from it.

---

**See also:** [warnings](warnings.md) · [soft assertions](soft-assertions.md) ·
[any value](any-value.md)
