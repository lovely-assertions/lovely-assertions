# Counting occurrences

Several assertions take an `occurrences=` constraint, which turns *is it there*
into *is it there the right number of times*. You build the constraint with
`exactly`, `at_least`, `at_most` and their neighbours, and pass it in.

```python
from lovely_assertions import expect, exactly

log = "retry\nretry\nok\n"
expect(log).contains("retry", occurrences=exactly(2))
print("counted")
```

```text
counted
```

## The constraints

| | Passes when the count is |
|---|---|
| `exactly(n)` | exactly `n` |
| `at_least(n)` | `n` or more |
| `at_most(n)` | `n` or fewer |
| `more_than(n)` | strictly more than `n` |
| `less_than(n)` | strictly fewer than `n` |
| `once` | exactly 1 |
| `twice` | exactly 2 |

`once` and `twice` are **values, not factories** — write `occurrences=once`, not
`once()`.

They all satisfy `Occurrence`, an exported `Protocol` with two methods:
`allows(count) -> bool` decides, and `describe() -> str` returns the middle of
the sentence (`"exactly 3 times"`). Anything with those two methods works
wherever `occurrences=` is accepted, so a constraint of your own needs no
inheritance:

```python
from lovely_assertions import expect, AssertionFailure


class Between:
    __slots__ = ("_high", "_low")

    def __init__(self, low: int, high: int) -> None:
        self._low, self._high = low, high

    def allows(self, count: int, /) -> bool:
        return self._low <= count <= self._high

    def describe(self) -> str:
        return f"between {self._low} and {self._high} times"


log = "retry\nretry\nok\n"
try:
    expect(log).contains("retry", occurrences=Between(3, 5))
except AssertionFailure as failure:
    print(failure)
```

```text
Expected log to contain 'retry' between 3 and 5 times, but found 2.
```

Nothing checks the object up front — `Occurrence` is deliberately not
`runtime_checkable`, and a constraint is used the moment it is passed. A missing
`allows` is an `AttributeError` raised where you wrote the call, not an
assertion failure.

## Why not just count it yourself

The alternative is a few characters shorter and reports almost nothing:

```python
from lovely_assertions import expect, AssertionFailure

log = "retry\nretry\nok\n"
try:
    expect(log.count("retry")).is_equal_to(3)
except AssertionFailure as failure:
    print(failure)
```

```text
Expected log.count("retry") to equal 3, but was 2.
```

Its subject is an integer, so the failure has lost the *thing under test* and the
*haystack*; the needle survives only because it happens to sit inside the
recovered expression. Compare:

```python
from lovely_assertions import expect, AssertionFailure, exactly

log = "retry\nretry\nok\n"
try:
    expect(log).contains("retry", occurrences=exactly(3))
except AssertionFailure as failure:
    print(failure)
```

```text
Expected log to contain 'retry' exactly 3 times, but found 2.
```

All three are still there. That sentence is the entire design brief for these
objects: they count **in English** rather than printing an operator, so `1` and
`2` read as words:

```python
from lovely_assertions import expect, AssertionFailure, at_most, less_than, more_than

log = "retry\nretry\nok\n"
try:
    expect(log).contains("retry", occurrences=at_most(1))
except AssertionFailure as failure:
    print(failure)

try:
    expect(log).contains("retry", occurrences=more_than(2))
except AssertionFailure as failure:
    print(failure)

try:
    expect(log).contains("retry", occurrences=less_than(1))
except AssertionFailure as failure:
    print(failure)
```

```text
Expected log to contain 'retry' at most once, but found 2.
Expected log to contain 'retry' more than twice, but found 2.
Expected log to contain 'retry' less than 1 time, but found 2.
```

`less_than` is the exception and stays numeric: "less than once" is not English.

## They are values

Immutable, hashable, equal when built the same way, with a `repr` that is the
call that made them:

```python
from lovely_assertions import exactly, once, at_least

print(repr(exactly(3)))
print(repr(once))
print(exactly(1) == once)
```

```text
exactly(3)
exactly(1)
True
```

So you can build one at module scope and share it across a suite — which only
works because a test cannot quietly change it. `__setattr__` refuses.

Note that `once` *is* `exactly(1)`: they are the same constraint, and `once` is
the spelling that reads better in a call.

## A constraint nothing could fail — or nothing could pass — is refused

```python
from lovely_assertions import at_least

try:
    at_least(0)
except ValueError as error:
    print(error)
```

```text
at_least(0) holds for every count, so it asserts nothing; use more_than(0) for 'it appears', or drop the constraint entirely
```

A count is a natural number — `str.count` and `len` do not return `-1` — so
`at_least(0)` holds for every possible count and asserts nothing at all. That is
a bug in the test rather than a finding about a subject, so it raises where you
wrote it, and the message names both fixes.

`less_than(0)` is the mirror, and is refused the same way: no count is below
zero, so no subject could ever satisfy it.

```python
from lovely_assertions import less_than

try:
    less_than(0)
except ValueError as error:
    print(error)
```

```text
less_than(0) holds for no count, so it can never pass; use exactly(0), at_most(0) or less_than(1) for 'it never appears'
```

A negative count is refused for the same reason:

```python
from lovely_assertions import exactly

try:
    exactly(-1)
except ValueError as error:
    print(error)
```

```text
an occurrence count cannot be negative, but was -1
```

The boundary cases that *are* kept are the ones that mean something:
`exactly(0)`, `at_most(0)` and `less_than(1)` all say "it never appears";
`more_than(0)` says "it appears".

## Gotchas

### `at_least(3)` and `more_than(2)` accept the same counts

They are not the same object and do not compare equal, and they read differently
in a message — "at least 3 times" versus "more than twice". Pick the one that
matches how you would say it out loud.

### String counting is non-overlapping

`"aaa".count("aa")` is `1` in Python, not `2`, and `occurrences=` uses that same
count. Switching to the regex form of `matches` changes nothing: `re` counts
non-overlapping matches too, each scan resuming past the match it just made. A
lookahead is what asks for the other count — it consumes nothing, so the scan
advances by one character and matches at index 0 *and* at index 1:

```python
from lovely_assertions import expect, AssertionFailure, exactly

letters = "aaa"
try:
    expect(letters).matches(r"aa", occurrences=exactly(2))
except AssertionFailure as failure:
    print(failure)

expect(letters).matches(r"(?=aa)", occurrences=exactly(2))
print("the lookahead counts two")

noise = "abc"
try:
    expect(noise).matches(r"x*", occurrences=exactly(1))
except AssertionFailure as failure:
    print(failure)
```

```text
Expected letters to match the regular expression 'aa' exactly twice, but found 1.
the lookahead counts two
Expected noise to match the regular expression 'x*' exactly once, but found 4.
```

**Quantify the pattern when the count is the point.** A pattern that can match
nothing matches everywhere: `x*` succeeds at every position the scan reaches, so
the count above is one empty match before each character and one at the end. It
reports where the scan stopped, not how many `x`s were there.

### A collection counts equal items

`occurrences=` over a collection counts items that *are* the value or compare
equal to it — Python's own membership rule — not appearances of one object.
Since `True == 1`, a list holding both counts two; and a list holding a NaN
counts *that* NaN once, though a NaN equals nothing, itself included.

---

**See also:** [strings](strings.md) · [collections](collections.md) ·
[mappings](mappings.md) · [warnings](warnings.md) · [mocks](mocks.md)
