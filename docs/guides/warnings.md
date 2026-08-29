# Warnings

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

**Callable** — `expect(fn).warns(...)`, beside `raises`.

## Why this exists next to `pytest.warns`

Stated plainly, because the honest answer is "not for every case".
`pytest.warns` is one line, already in the file, and needs no import. Three
things it cannot do:

**It does not show you what *was* warned.** It tells you the warning you asked
for did not fire — which you already knew — and says nothing about the four that
did, which is the information that ends the investigation. When the warning you
asked for did not fire, the failure lists the warnings that *were*, each with the
file and line its `stacklevel` pointed at:

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

## Nothing was warned

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

Note the subject reads as the **warning category** rather than `the value` —
unlike an exception handle, which has no name to recover.

`with_message`, `.which` and `.where` complete the set.

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

### Warnings outside the category come back out

A warning that is not the category you asked for is re-issued when the block
exits, so your suite's own warning filters still see it. If those filters are set
to error, it can raise there.

### `stacklevel` decides the reported location

The file and line in a message are where `stacklevel` pointed. In the callable
form, a `stacklevel` of 1 can point at the library rather than at your code —
that is your warning's setting, not this library's choice.

### Exception messages ignore `formatting(max_chars=...)`; warning messages honour it

A deliberate asymmetry: an exception's message is the primary evidence and is
shown whole.

---

**See also:** [exceptions](exceptions.md) · [occurrences](occurrences.md) ·
[soft assertions](soft-assertions.md)
