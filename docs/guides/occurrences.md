# Counting occurrences

Several assertions take an `occurrences=` constraint, which turns *is it there*
into *is it there the right number of times*:

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
inheritance.

## Why not just count it yourself

The alternative is one line shorter and reports almost nothing:

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
objects: they count **in English** rather than printing an operator, which is why
`1` gets a singular:

```python
from lovely_assertions import expect, AssertionFailure, at_most, more_than

log = "retry\nretry\nok\n"
try:
    expect(log).contains("retry", occurrences=at_most(1))
except AssertionFailure as failure:
    print(failure)

try:
    expect(log).contains("retry", occurrences=more_than(2))
except AssertionFailure as failure:
    print(failure)
```

```text
Expected log to contain 'retry' at most once, but found 2.
Expected log to contain 'retry' more than twice, but found 2.
```

"at most 1 times" would be the tell that nobody read the output of the thing
whose entire job is to be read.

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

## A constraint nothing could fail is refused

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
count. If overlaps matter, a regular expression is the tool.

### A collection counts equal items

`occurrences=` over a collection counts items that compare equal, not appearances
of one object. Since `True == 1`, a list holding both counts two.

---

**See also:** [strings](strings.md) · [collections](collections.md) ·
[warnings](warnings.md) · [mocks](mocks.md)
