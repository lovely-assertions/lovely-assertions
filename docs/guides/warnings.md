# Warnings

Assert that a call warns — as a `with` block or on a callable — count the
warnings it issues, and assert that nothing warned at all.

Two forms, mirroring [exceptions](exceptions.md).

**Context manager** — where `pytest.warns` sits:

```python
import warnings

from lovely_assertions import expect_warns


def parse_date(text: str) -> None:
    warnings.warn("use parse_iso instead", DeprecationWarning, stacklevel=2)


with expect_warns(DeprecationWarning) as warned:
    parse_date("16/03/2024")

warned.with_message_containing("parse_iso")
print("warned as required")
```

```text
warned as required
```

**Callable** — for a thunk you already have, beside `raises`:

```python
import warnings

from lovely_assertions import expect


def legacy() -> None:
    warnings.warn("use parse_iso instead", DeprecationWarning, stacklevel=2)


expect(legacy).warns(DeprecationWarning).with_message_containing("parse_iso")
print("warned as required")
```

```text
warned as required
```

Reach for it when you already have a thunk and want the whole assertion to read
as one expression. `expect_warns` is the primary spelling; hand `expect()` the
function that warns and the location a failure reports moves — see the
`stacklevel` gotcha below.

## Why this exists next to `pytest.warns`

Stated plainly, because the honest answer is "not for every case".
`pytest.warns` is one line, already in the file, and needs no import. Three
things it cannot do:

**It does not show you what *was* warned.** It tells you your warning did not
fire — which you already knew. Here the failure lists the ones that did, each
with the file and line its `stacklevel` pointed at:

```python
import re
import warnings

from lovely_assertions import expect_warns, AssertionFailure


def parse_date(text: str) -> None:
    warnings.warn("use parse_iso instead", DeprecationWarning, stacklevel=2)


try:
    with expect_warns(UserWarning):
        parse_date("16/03/2024")
except AssertionFailure as failure:
    print(re.sub(r"at \S+:\d+", "at <file>:<line>", str(failure)))
```

```text
Expected UserWarning to be warned, but the warnings issued were DeprecationWarning('use parse_iso instead') at <file>:<line>.
```

(The substitution is only so this page can quote a stable result — a real failure
gives you the actual path and line number.)

**It cannot be collected.** `pytest.warns` raises, so it ends the test at the
first finding. Everything here reports through the same machinery as the rest of
the library, so an active [`soft_assertions()`](soft-assertions.md) scope gathers
a failed warning assertion alongside the rest and the block runs to the end.

**It cannot count:**

```python
import re
import warnings

from lovely_assertions import expect_warns, AssertionFailure, exactly


def parse_date(text: str) -> None:
    warnings.warn("use parse_iso instead", DeprecationWarning, stacklevel=2)


try:
    with expect_warns(DeprecationWarning, occurrences=exactly(3)):
        parse_date("a")
        parse_date("b")
except AssertionFailure as failure:
    print(re.sub(r"at \S+:\d+", "at <file>:<line>", str(failure)))
```

```text
Expected DeprecationWarning to be warned exactly 3 times, but found 2: DeprecationWarning('use parse_iso instead') at <file>:<line>, DeprecationWarning('use parse_iso instead') at <file>:<line>.
```

`occurrences=` takes the same constraints as everywhere else — see
[Counting occurrences](occurrences.md). A test that cares whether a deprecation
fired once or once per row has no spelling for that in `pytest.warns`.

## When the warning never fired

```python
from lovely_assertions import expect_warns, AssertionFailure

try:
    with expect_warns(DeprecationWarning):
        pass
except AssertionFailure as failure:
    print(failure)
```

```text
Expected DeprecationWarning to be warned, but nothing was warned.
```

## Asserting on the warnings

The handle is a subject over **all** the captured warnings of that category —
`warned.subject` is a tuple, not a single warning. Its assertions therefore ask
for *some* captured warning: `with_message_containing` passes as soon as one
matches, which is what you want when a call warns more than once.

```python
import warnings

from lovely_assertions import expect_warns, AssertionFailure


def parse_date(text: str) -> None:
    warnings.warn("use parse_iso instead", DeprecationWarning, stacklevel=2)


with expect_warns(DeprecationWarning) as warned:
    parse_date("16/03/2024")

try:
    warned.with_message_containing("use parse_rfc instead")
except AssertionFailure as failure:
    print(failure)
```

```text
Expected DeprecationWarning to have a message containing 'use parse_rfc instead', but the message was 'use parse_iso instead'.
```

In the block form the message names the **warning category**: there is no
`expect(...)` call for a name to be read out of, and `DeprecationWarning` says
more than `the value`, which is what an exception block falls back to. Reached
through the callable form, the name is the callable you handed `expect()`.

| | Asserts |
|---|---|
| `with_message(pattern)` | some captured warning's `str()` **matches the regex** `pattern` (a search, not a full match) |
| `with_message_containing(text)` | some captured warning's message contains `text` |
| `where(predicate)` | some captured warning satisfies `predicate`, which is handed the warning typed as the category you asked for |
| `.which` | the same subject — `warns` already made the warnings the subject, so there is nothing to descend into; it exists so the chain reads aloud |
| `.subject` | the tuple of captured warnings |

## Asserting that nothing warned

The thing `pytest.warns` cannot express at all:

```python
from lovely_assertions import expect

expect(lambda: None).does_not_warn()
print("nothing warned")
```

```text
nothing warned
```

Without it, that assertion is written out by hand around a `catch_warnings` block
every time it is wanted.

`does_not_warn(SomeCategory)` narrows it to one category.

## Gotchas

### Your filters do not apply inside the block

Capture runs with `always`, so a `DeprecationWarning` the interpreter ignores by
default is still captured, and `-W error` does not turn the warning under test
into an exception. A test that says "this call deprecates" should not have to
know how the suite is configured. `pytest.warns` does the same.

### Warnings outside the category come back out

A warning that is not the category you asked for is re-issued when the block
exits, so your suite's own warning filters still see it. If those filters are set
to error, it can raise there.

### `stacklevel` decides the reported location

The file and line in a message are where `stacklevel` pointed, and the code that
issued the warning chooses it — not this library.

The case worth knowing: `warnings.warn(..., stacklevel=2)` names the *caller* of
the function that warned. Hand `expect()` that function itself and the caller is
this library's invocation of it, so the failure points at a file inside
`lovely_assertions` rather than at your test. It looks like a bug and is not one:
the frame a warning names is chosen by the code that issued it. Wrapping the call
instead — `expect(lambda: parse_date("16/03/2024"))` — puts your own line back,
and `expect_warns` has no such frame in between at all.

### Exception messages ignore `formatting(max_chars=...)`; warning messages honour it

A deliberate asymmetry. An exception's message is the primary evidence, so it is
not subject to your display settings: it carries its own fixed ceiling, and past
it the rendering is clipped with a note giving the length it had in full — not
the number of characters dropped. That ceiling is what `max_chars` defaults to,
so the difference only shows once you move the bound. A warning's message is
ordinary rendered output and honours `formatting(max_chars=...)` like any other
value.

---

**See also:** [exceptions](exceptions.md) · [occurrences](occurrences.md) ·
[soft assertions](soft-assertions.md)
